"""Fixed panel accounting, durable records, score composition and selection."""
from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import time

from .authority import AuthorityError, canonical, digest, FAMILIES


def combine_lengths(candidate, length_summaries, complete):
    """Equal one-third weight per original length, with exceptional evidence."""
    listed = dict(length_summaries)
    if set(listed) != {128, 512, 2048}:
        complete = False
    values = [listed[n] for n in (128, 512, 2048) if n in listed]
    has_undefined = any(v["status"] == "undefined_loss" for v in values)
    has_infinite = any(v["status"] == "infinite_loss" or v["infinite_loss_count"] > 0 for v in values)
    status = ("incomplete" if not complete else "undefined_loss" if has_undefined else
              "infinite_loss" if has_infinite else "ok")
    if status == "ok":
        losses = [v["loss"] for v in values]
        if not all(type(x) in (int, float) and math.isfinite(x) for x in losses):
            raise ValueError("finite summary loss required")
        try:
            loss = math.fsum(x / 3 for x in losses)
            if not math.isfinite(loss):
                raise OverflowError
        except OverflowError:
            loss = float(sum(Fraction(float(x)) for x in losses) / 3)
    else:
        loss = None
    return dict(candidate=candidate, status=status, loss=loss,
                infinite_loss_count=sum(v["infinite_loss_count"] for v in values),
                has_infinite=has_infinite, has_undefined=has_undefined,
                query_count=sum(v["query_count"] for v in values), complete=complete)


def select_family(family, combined, costs, hashes):
    """Only complete finite configurations enter the exact comparison."""
    cost = {v["candidate"]: v["standalone_total_seconds"] for v in costs}
    choices = [v for v in combined if v["candidate"].startswith(family + ":") and
               v["complete"] and v["status"] == "ok" and math.isfinite(v["loss"])]
    if not choices:
        return None
    return min(choices, key=lambda v: (v["loss"], cost[v["candidate"]],
                                       hashes[v["candidate"]]))["candidate"]


def _recorded_partial(candidate, scores, complete):
    """Retain observed score counts/exception flags without inventing a loss."""
    flat = [score for length in (128, 512, 2048) for score in scores[length]]
    return dict(candidate=candidate, status="incomplete", loss=None,
                infinite_loss_count=sum(bool(row.get("infinite_loss")) for row in flat),
                has_infinite=any(row.get("loss_status") == "infinite_loss" or
                                 row.get("infinite_loss") for row in flat),
                has_undefined=any(row.get("loss_status") == "undefined_loss" for row in flat),
                query_count=len(flat), complete=complete)


def _ref(path, root, kind):
    raw = path.read_bytes()
    return dict(kind=kind, path=str(path.relative_to(root)), sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw))


def _append(path, value):
    with path.open("ab") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()


def _interval(intervals, owner, operation, start, status="completed"):
    end = time.monotonic()
    if intervals and start > intervals[-1]["end"]:
        intervals.append(dict(start=intervals[-1]["end"], end=start, owner="common",
                              operation="accounted_gap", status="completed"))
    intervals.append(dict(start=start, end=end, owner=owner, operation=operation, status=status))
    return end


def _costs(candidates, intervals, completed):
    result = []
    for candidate in candidates:
        cid = candidate["id"]
        relevant = [i for i, row in enumerate(intervals)
                    if row["owner"] in ("common", candidate["family"], cid)]
        direct = sum(intervals[i]["end"] - intervals[i]["start"] for i in relevant
                     if intervals[i]["owner"] == cid)
        family = sum(intervals[i]["end"] - intervals[i]["start"] for i in relevant
                     if intervals[i]["owner"] == candidate["family"])
        common = sum(intervals[i]["end"] - intervals[i]["start"] for i in relevant
                     if intervals[i]["owner"] == "common")
        result.append(dict(candidate=cid, complete=cid in completed, direct_seconds=direct,
                           family_encoding_seconds=family, common_seconds=common,
                           standalone_total_seconds=direct + family + common, intervals=relevant))
    return result


def terminal_costs(candidates, intervals, completed):
    """Recompute standalone charges from an exact contiguous allocation partition."""
    if not intervals or type(intervals) is not list:
        raise ValueError("terminal interval partition missing")
    owners = {"common", "jet", "bank"} | {c["id"] for c in candidates}
    previous = None
    for row in intervals:
        if (type(row) is not dict or set(row) != {"start", "end", "owner", "operation", "status"} or
                type(row["start"]) not in (int, float) or type(row["end"]) not in (int, float) or
                not math.isfinite(row["start"]) or not math.isfinite(row["end"]) or
                row["end"] < row["start"] or
                (previous is not None and row["start"] != previous) or
                row["owner"] not in owners or type(row["operation"]) is not str or
                not row["operation"] or row["status"] not in ("completed", "failed")):
            raise ValueError("terminal interval partition malformed")
        previous = row["end"]
    return _costs(candidates, intervals, completed)


def compose_terminal_intervals(allocation_start, program_end, worker_intervals, binding=False):
    """Preserve attributed worker work and charge both wrapper tails as common."""
    if binding:
        return [dict(start=allocation_start, end=program_end, owner="common",
                     operation="binding_program", status="completed")]
    if not worker_intervals or worker_intervals[0]["start"] < allocation_start or \
            worker_intervals[-1]["end"] > program_end:
        raise ValueError("worker interval outside original allocation")
    result = []
    if allocation_start < worker_intervals[0]["start"]:
        result.append(dict(start=allocation_start, end=worker_intervals[0]["start"],
                           owner="common", operation="authority_import_startup", status="completed"))
    result.extend(worker_intervals)
    if worker_intervals[-1]["end"] < program_end:
        result.append(dict(start=worker_intervals[-1]["end"], end=program_end,
                           owner="common", operation="supervisor_run_commit", status="completed"))
    return result


def execute(plan, backend, checkpoint):
    """Run all fixed entries; preserve attempted work and stop on infrastructure error.

    The caller has completed worker authority and post-import baseline. Backend
    is a concrete instance, allowing a controlled source-only test double.
    """
    output = Path(plan["execution"]["output"])
    start = time.monotonic()
    files = {name: output / (name + ".jsonl") for name in ("snapshots", "requests", "scores")}
    for path in files.values():
        path.touch(exist_ok=True)
    counts = Counter({name: 0 for name in ("snapshots_attempted", "snapshots_completed",
                                          "requests_attempted", "requests_completed",
                                          "worker_reads", "worker_factors", "predictions_scored",
                                          "quarantined_histories", "fallback_rows")})
    intervals = []
    rows = {c["id"]: {length: [] for length in (128, 512, 2048)} for c in plan["candidates"]}
    failure = None
    ordinal = 0
    completed = set()
    prepared = None
    known_entries = getattr(backend, "entries", [])
    current_candidate = None
    current_entry = None
    active_request_ordinal = None
    phase = "prepare"
    scored = set()
    from validation.kernel_stage_a import authority as a_authority
    event_path = output / "monitor-events.jsonl"
    deadline = plan["execution"]["boundary"]["deadline_monotonic"]
    candidate_seconds = plan["execution"]["limits"]["candidate_seconds"]
    intervals.append(dict(start=start, end=time.monotonic(), owner="common",
                          operation="startup", status="completed"))

    def check():
        checkpoint()
        if time.monotonic() >= deadline:
            raise TimeoutError("original outer deadline")
        if current_candidate is not None and time.monotonic() >= backend.candidate_deadline:
            raise TimeoutError("candidate deadline")

    try:
        check(); t = time.monotonic()
        prepared = backend.prepare()
        _interval(intervals, "common", "prepare", t)
        entries = prepared["entries"]
        known_entries = entries
        if len(entries) != 96:
            raise ValueError("full96 panel required")
        snapshots_by_family = {}
        for candidate in plan["candidates"]:
            family = candidate["family"]
            current_candidate = candidate
            cid = candidate["id"]
            candidate_start = time.monotonic()
            backend.candidate_deadline = min(deadline, candidate_start + candidate_seconds)
            a_authority.event(event_path, "candidate_start", candidate=cid)
            if family not in snapshots_by_family:
                phase = "encode"
                snapshots = []
                for entry in entries:
                    current_entry = entry
                    check()
                    if counts["snapshots_attempted"] >= 192:
                        raise ValueError("snapshot ceiling")
                    counts["snapshots_attempted"] += 1
                    t = time.monotonic()
                    snapshot = backend.encode(family, entry)
                    _interval(intervals, family, "encode", t)
                    counts["snapshots_completed"] += 1
                    _append(files["snapshots"], snapshot["record"])
                    if snapshot["record"]["trigger"] is not None:
                        counts["quarantined_histories"] += 1
                    snapshots.append(snapshot)
                snapshots_by_family[family] = snapshots
            for entry, snapshot in zip(entries, snapshots_by_family[family]):
                    current_entry = entry
                    active_request_ordinal = None
                    check()
                    trigger = snapshot["record"]["trigger"]
                    if trigger is None:
                        if counts["requests_attempted"] >= 576:
                            raise ValueError("request ceiling")
                        phase = "transport"
                        active_request_ordinal = ordinal
                        request = dict(version=1, ordinal=ordinal, candidate=cid,
                                       history_id=entry["episode_id"], query_ids=entry["query_ids"],
                                       request=None, stdout=None, stderr=None, returncode=None,
                                       status="attempted", reader_seconds=None, failure=None)
                        def append_attempt(ref):
                            request["request"] = ref
                            _append(files["requests"], request)
                        backend.on_attempt = append_attempt
                        counts["requests_attempted"] += 1
                        t = time.monotonic()
                        read = backend.read(candidate, entry, snapshot)
                        _interval(intervals, cid, "read", t)
                        counts["requests_completed"] += 1
                        counts["worker_reads"] += read["counts"].get("read", 0)
                        counts["worker_factors"] += read["counts"].get("factor", 0)
                        request.update(status="completed", request=read["request"],
                                       stdout=read["stdout"], stderr=read["stderr"],
                                       returncode=0, reader_seconds=read["seconds"])
                        _append(files["requests"], request)
                        ordinal += 1
                        numeric = read["numeric"]
                    else:
                        numeric = None
                    phase = "score"
                    t = time.monotonic()
                    scores = backend.score(candidate, entry, numeric, trigger)
                    _interval(intervals, cid, "score", t)
                    if len(scores) != 8:
                        raise ValueError("eight query scores required")
                    for score in scores:
                        _append(files["scores"], dict(version=1, candidate=cid,
                               length=entry["length"], snapshot_hash=snapshot["record"]["snapshot_hash"],
                               request_ordinal=active_request_ordinal, score=score))
                        rows[cid][entry["length"]].append(score)
                        counts["predictions_scored"] += 1
                        counts["fallback_rows"] += bool(score["fallback"])
                    scored.add((cid, entry["episode_id"]))
            check()
            a_authority.event(event_path, "candidate_end", candidate=cid)
            current_candidate = None
            completed.add(cid)
            phase = "finalize"
        if (counts["snapshots_completed"] != 192 or counts["predictions_scored"] != 4608 or
                counts["requests_completed"] + 3 * counts["quarantined_histories"] != 576 or
                counts["worker_reads"] != counts["requests_completed"] or counts["worker_factors"] != 0):
            raise ValueError("fixed panel counts mismatch")
        if any(len(rows[c["id"]][length]) != 256 for c in plan["candidates"]
               for length in (128, 512, 2048)):
            raise ValueError("per-candidate full96/Q8 inventory mismatch")
    except Exception as exc:
        from .production import DecodeError
        if isinstance(exc, DecodeError):
            phase = "decode"
        if "t" in locals() and (not intervals or intervals[-1]["end"] <= t):
            owner = ("common" if phase in ("prepare", "finalize") else
                     current_candidate["family"] if phase == "encode" and current_candidate else
                     current_candidate["id"] if current_candidate else "common")
            _interval(intervals, owner, phase, t, "failed")
        remaining = ([dict(candidate=c["id"], history_id=e["episode_id"],
                           query_ids=e["query_ids"])
                      for c in plan["candidates"] for e in known_entries
                      if (c["id"], e["episode_id"]) not in scored])
        stopped_ordinal = active_request_ordinal if phase in ("transport", "decode", "score") else None
        failure = dict(phase=phase, candidate=current_candidate["id"] if current_candidate else None,
                       history_id=current_entry["episode_id"] if current_entry else None,
                       ordinal=stopped_ordinal,
                       exception_type=type(exc).__name__, message=str(exc), monotonic=time.monotonic(),
                       raw=[], remaining=remaining)
        if phase in ("transport", "decode") and "request" in locals() and request["status"] == "attempted" and request["request"] is not None:
            request["status"] = "failed"
            # The request journal cannot include its own final byte hash.
            request["failure"] = dict(failure)
            for field, suffix in (("stdout", "jsonl"), ("stderr", "stderr")):
                path = output / f"reader-{ordinal:03}.{suffix}"
                if path.is_file():
                    request[field] = _ref(path, output, "bytes")
            _append(files["requests"], request)
        raw = [_ref(path, output, "bytes") for path in files.values() if path.exists()]
        raw.extend(_ref(path, output, "bytes") for path in sorted(output.glob("request-*.json")))
        raw.extend(_ref(path, output, "bytes") for path in sorted(output.glob("reader-*")))
        failure["raw"] = raw
    summaries = []
    combined = []
    for candidate in plan["candidates"]:
        cid = candidate["id"]
        if cid in completed:
            try:
                from famjet.eval.metrics import aggregate_scores
                length_summaries = []
                for length in (128, 512, 2048):
                    summary = aggregate_scores(rows[cid][length])
                    summaries.append(dict(candidate=cid, length=length, summary=summary))
                    length_summaries.append((length, summary))
                combined.append(combine_lengths(cid, length_summaries, True))
                continue
            except Exception as exc:
                if failure is None:
                    failure = dict(phase="finalize", candidate=cid, history_id=None, ordinal=None,
                                   exception_type=type(exc).__name__, message=str(exc),
                                   monotonic=time.monotonic(),
                                   raw=[_ref(path, output, "bytes") for path in files.values()],
                                   remaining=[])
        combined.append(_recorded_partial(cid, rows[cid], cid in completed))
    finalization = dict(start=intervals[-1]["end"], end=time.monotonic(), owner="common",
                        operation="finalize", status="completed" if failure is None else "failed")
    intervals.append(finalization)
    costs = _costs(plan["candidates"], intervals, completed)
    hashes = {c["id"]: c["config_sha256"] for c in plan["candidates"]}
    selection = {family: select_family(family, combined, costs, hashes) if failure is None else None
                 for family in ("jet", "bank")}
    exclusions = [dict(candidate=v["candidate"], reason=v["status"]) for v in combined
                  if v["status"] != "ok"]
    end = time.monotonic()
    finalization["end"] = end
    costs = _costs(plan["candidates"], intervals, completed)
    return dict(version=2, cost_scope="worker_provisional", completion="PENDING_TERMINAL",
                plan_sha256=digest(plan),
                status="INFRA_STOP" if failure is not None else "COMPLETED",
                counts=dict(counts), resolved_panel_config=(
                    prepared.get("resolved_panel_config") if prepared else
                    getattr(backend, "resolved_ref", None)),
                snapshots=_ref(files["snapshots"], output, "jsonl"),
                requests=_ref(files["requests"], output, "jsonl"),
                scores=_ref(files["scores"], output, "jsonl"), failure=failure,
                summaries=summaries, combined=combined, costs=costs, intervals=intervals,
                campaign_seconds=end - start, selection=selection, exclusions=exclusions,
                start_monotonic=start, end_monotonic=end,
                source_manifest=plan["execution"]["source_manifest"])
