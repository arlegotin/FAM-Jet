"""Prospective Stage B launcher: complete sealed authority precedes science."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from . import authority


def _atomic_json(path, value):
    _atomic_bytes(path, authority.canonical(value))


def _atomic_bytes(path, raw):
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", suffix=".tmp",
                                         delete=False) as stream:
            name = stream.name
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        name = None
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)


def _ref(path, root, kind):
    raw = path.read_bytes()
    return dict(kind=kind, path=str(path.relative_to(root)),
                sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def _failure(exc, phase):
    return dict(phase=phase, candidate=None, history_id=None, ordinal=None,
                exception_type=type(exc).__name__, message=str(exc), monotonic=time.monotonic(),
                raw=[], remaining=[])


def _write_infra_stop(plan, out, exc, result=None, phase="authority"):
    """Retain known completed work when a later worker commitment fails."""
    if result is not None:
        body = dict(result)
        failure = _failure(exc, "finalize")
        failure["raw"] = [body[key] for key in ("snapshots", "requests", "scores")]
        body.update(status="INFRA_STOP", completion="PENDING_TERMINAL", failure=failure,
                    selection={"jet": None, "bank": None})
        _atomic_json(out / "stage-b.json", body)
        return
    for name in ("snapshots", "requests", "scores"):
        (out / (name + ".jsonl")).touch(exist_ok=True)
    counts = {k: 0 for k in ("snapshots_attempted", "snapshots_completed", "requests_attempted",
                              "requests_completed", "worker_reads", "worker_factors", "predictions_scored",
                              "quarantined_histories", "fallback_rows")}
    failure = _failure(exc, phase)
    combined = [dict(candidate=c["id"], status="incomplete", loss=None, infinite_loss_count=0,
                     has_infinite=False, has_undefined=False, query_count=0, complete=False)
                for c in plan["candidates"]]
    costs = [dict(candidate=c["id"], complete=False, direct_seconds=0.,
                  family_encoding_seconds=0., common_seconds=0., standalone_total_seconds=0.,
                  intervals=[]) for c in plan["candidates"]]
    stamp = time.monotonic()
    body = dict(version=2, cost_scope="worker_provisional", completion="PENDING_TERMINAL",
                plan_sha256=authority.digest(plan), status="INFRA_STOP",
                counts=counts, resolved_panel_config=None,
                snapshots=_ref(out / "snapshots.jsonl", out, "jsonl"),
                requests=_ref(out / "requests.jsonl", out, "jsonl"),
                scores=_ref(out / "scores.jsonl", out, "jsonl"), failure=failure,
                summaries=[], combined=combined, costs=costs, intervals=[], campaign_seconds=0.,
                selection={"jet": None, "bank": None},
                exclusions=[dict(candidate=c["id"], reason="incomplete") for c in plan["candidates"]],
                start_monotonic=stamp, end_monotonic=stamp,
                source_manifest=plan["execution"]["source_manifest"])
    _atomic_json(out / "stage-b.json", body)


def _worker(plan, root):
    out = Path(plan["execution"]["output"])
    events = out / "monitor-events.jsonl"
    result = None
    phase = "authority"
    try:
        deadline = authority.verify_worker(plan, root, events)
        phase = "prepare"
        import torch
        from famjet.eval import isolation  # noqa: F401 - import before baseline
        from famjet.eval.metrics import score_predictions, aggregate_scores  # noqa: F401
        from validation.kernel_stage_a.monitor import record_baseline
        from .production import Backend
        from .driver import execute

        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        record_baseline(events, deadline=deadline)
        if plan["release"]["scope"] == "binding":
            _atomic_json(out / "binding-worker.json",
                dict(version=2, status="PENDING_TERMINAL", plan_sha256=authority.digest(plan),
                     counts=dict(constructions=0, encodes=0, reads=0, factors=0, predictions=0)))
            return 0
        def checkpoint():
            if time.monotonic() >= deadline:
                raise TimeoutError("original outer deadline")
        result = execute(plan, Backend(plan, root), checkpoint)
        _atomic_json(out / "stage-b.json", result)
        return 0 if result["status"] == "COMPLETED" else 1
    except Exception as exc:
        _write_infra_stop(plan, out, exc, result, phase)
        return 1


def _parent(plan, root, plan_path, plan_file_sha256):
    from validation.kernel_stage_a.monitor import supervise

    execution = plan["execution"]
    boundary = execution["boundary"]
    limits = execution["limits"]
    deadline = boundary["deadline_monotonic"]
    for key, value in execution["launch"]["environment"].items():
        os.environ[key] = value
    result = supervise(execution["launch"]["argv"], Path(execution["output"]),
                       outer_seconds=deadline - time.monotonic(),
                       outer_ceiling_seconds=limits["outer_seconds"],
                       candidate_seconds=limits["candidate_seconds"],
                       output_bytes=limits["output_bytes"],
                       incremental_bytes=limits["incremental_bytes"],
                       free_disk_bytes=limits["free_disk_bytes"],
                       preparation_output=execution["preparation_output"],
                       authority_root=root, deadline=deadline)
    out = Path(execution["output"])
    same_plan = hashlib.sha256(plan_path.read_bytes()).hexdigest() == plan_file_sha256
    starts = [authority.strict_json(line) for line in (out / "monitor-events.jsonl").read_bytes().splitlines()
              if b'"authority_start"' in line]
    same_plan = same_plan and len(starts) == 1 and starts[0]["plan_file_sha256"] == plan_file_sha256
    external = out / "stage-b-external.json"
    _atomic_json(external, dict(version=2, monitor_status=result["status"],
                                               monitor_returncode=result["returncode"],
                                               outer_seconds=result["outer_seconds"],
                                               observed_monotonic=time.monotonic(),
                                               plan_file_sha256=plan_file_sha256,
                                               same_plan_bytes=same_plan))
    if plan["release"]["scope"] == "binding":
        worker = out / "binding-worker.json"
        success = (same_plan and result["status"] == "COMPLETED" and result["returncode"] == 0 and
                   worker.is_file() and time.monotonic() < deadline)
        if success:
            body = authority.strict_json(worker.read_bytes())
            success = body["status"] == "PENDING_TERMINAL" and body["counts"] == dict(constructions=0, encodes=0, reads=0,
                                             factors=0, predictions=0)
        report = dict(version=2, status="PENDING_TERMINAL" if success else "FAILED",
                      plan_sha256=authority.digest(plan), source_full_git=execution["source_full_git"],
                      source_manifest=execution["source_manifest"],
                      template_sha256=execution["launch"]["template_sha256"],
                      argv_sha256=execution["launch"]["argv_sha256"],
                      monitor=_ref(out / "monitor.json", out, "A_monitor"),
                      events=_ref(out / "monitor-events.jsonl", out, "jsonl"),
                      journal=_ref(out / "monitor-evidence.jsonl", out, "jsonl"),
                      external=_ref(external, out, "A_external"),
                      counts=dict(constructions=0, encodes=0, reads=0, factors=0, predictions=0),
                      failure=None if success else _failure(RuntimeError("binding monitor failed"), "finalize"))
        _atomic_json(out / "binding-report.json", report)
    if (not same_plan or sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) > limits["output_bytes"] or
            time.monotonic() >= deadline):
        print("INFRA_STOP: final plan/output/deadline boundary", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "COMPLETED" else 1


def _charged_bytes(output, preparation):
    return authority.charged_bytes(output, preparation)


def _checked_commit(path, value, execution, deadline):
    """Account for both old target and temporary copy before atomic publication."""
    raw = authority.canonical(value)
    out = Path(execution["output"])
    prep = execution["preparation_output"]
    if time.monotonic() >= deadline or \
            _charged_bytes(out, prep) + len(raw) > execution["limits"]["output_bytes"]:
        raise RuntimeError("terminal commit exceeds original clock/output cap")
    _atomic_bytes(path, raw)
    if time.monotonic() >= deadline or path.read_bytes() != raw:
        raise RuntimeError("terminal commit deadline/byte verification failed")
    return _ref(path, out, "Run" if path.name == "stage-b.json" else
                "binding_record" if path.name == "binding-report.json" else "terminal_report")


def finalize_terminal(plan, root, exit_witness):
    """Post-parent stdlib finalizer called only by the separately pinned witness."""
    from .driver import compose_terminal_intervals, select_family, terminal_costs

    execution = plan["execution"]
    out = Path(execution["output"])
    boundary = execution["boundary"]
    allocation = boundary["allocation_start_monotonic"]
    deadline = boundary["deadline_monotonic"]
    scope = plan["release"]["scope"]
    monitor_path = out / "monitor.json"
    raw_path = out / ("binding-report.json" if scope == "binding" else "stage-b.json")
    failure = None
    committed = None
    monitor_ref = None
    body = None
    same_plan = False
    attributable = True
    try:
        authority.validate_plan(plan)
        authority.validate_exit_witness(plan, root, exit_witness)
        plan_path = Path(execution["launch"]["argv"][5])
        same_plan = authority.strict_json(plan_path.read_bytes()) == plan and \
            hashlib.sha256(plan_path.read_bytes()).hexdigest() == exit_witness["plan_file_sha256"]
        if not same_plan:
            raise RuntimeError("parent/finalizer Plan bytes differ")
        if monitor_path.is_file():
            monitor = authority.strict_json(monitor_path.read_bytes())
            monitor_ref = _ref(monitor_path, out, "A_monitor")
        else:
            monitor = None
        if raw_path.is_file():
            body = authority.strict_json(raw_path.read_bytes())
            committed = _checked_commit(raw_path, body, execution, deadline)
        substantive = (exit_witness["returncode"] == 0 and monitor is not None and
                       monitor.get("status") == "COMPLETED" and monitor.get("returncode") == 0 and
                       body is not None and type(body.get("version")) is int and
                       body["version"] == 2 and body.get("plan_sha256") == authority.digest(plan) and
                       (body.get("status") == "PENDING_TERMINAL" if scope == "binding" else
                        body.get("status") == "COMPLETED" and
                        body.get("cost_scope") == "worker_provisional" and
                        body.get("completion") == "PENDING_TERMINAL") and
                       body.get("failure") is None)
        if not substantive:
            raise RuntimeError("parent, monitor or scientific completion failed")
    except Exception as exc:
        failure = _failure(exc, "finalize")
    program_end = time.monotonic()
    if program_end < exit_witness.get("reaped_monotonic", allocation):
        failure = _failure(RuntimeError("terminal clock precedes parent reap"), "finalize")
    try:
        if scope == "binding":
            intervals = compose_terminal_intervals(allocation, program_end, [], binding=True)
            intervals[0]["status"] = "failed" if failure else "completed"
            costs = []
            selection = {"jet": None, "bank": None}
        else:
            if body is None:
                raise ValueError("missing worker Run attribution")
            intervals = compose_terminal_intervals(allocation, program_end, body["intervals"])
            completed = {row["candidate"] for row in body["combined"] if row["complete"]}
            costs = terminal_costs(plan["candidates"], intervals, completed)
            hashes = {candidate["id"]: candidate["config_sha256"] for candidate in plan["candidates"]}
            selection = ({family: select_family(family, body["combined"], costs, hashes)
                          for family in ("jet", "bank")} if failure is None else
                         {"jet": None, "bank": None})
    except Exception as exc:
        attributable = False
        if failure is None:
            failure = _failure(exc, "finalize")
        intervals = [dict(start=allocation, end=max(allocation, program_end), owner="common",
                          operation="unattributed_failed_program", status="failed")]
        costs = terminal_costs(plan["candidates"], intervals, set()) if scope == "panel" else []
        selection = {"jet": None, "bank": None}
    program_bytes = _charged_bytes(out, execution["preparation_output"])
    if (program_end >= deadline or program_bytes + execution["terminal"]["publication_bytes"] >
            execution["limits"]["output_bytes"] or
            exit_witness.get("returncode") != 0):
        if failure is None:
            failure = _failure(RuntimeError("original terminal clock/cap/exit boundary"), "finalize")
    terminal = dict(version=1, scope=scope, plan_sha256=authority.digest(plan), exit=exit_witness,
                    status="ELIGIBLE_PENDING_PUBLICATION" if failure is None and attributable else "FAILED",
                    failure=failure, run=committed if scope == "panel" else None,
                    binding=committed if scope == "binding" else None,
                    monitor=monitor_ref, allocation_start=allocation, program_end=program_end,
                    intervals=intervals, costs=costs, campaign_seconds=program_end - allocation,
                    selection=selection if failure is None else {"jet": None, "bank": None},
                    same_plan_bytes=same_plan, program_output_bytes=program_bytes,
                    publication_reserve_bytes=execution["terminal"]["publication_bytes"])
    receipt_start = program_end
    try:
        receipt = _checked_commit(out / "terminal-report.json", terminal, execution, deadline)
        receipt_elapsed = time.monotonic() - receipt_start
        after = _charged_bytes(out, execution["preparation_output"])
        if (receipt_elapsed < 0 or receipt_elapsed > execution["terminal"]["publication_seconds"] or
                after - program_bytes > execution["terminal"]["publication_bytes"] or
                after > execution["limits"]["output_bytes"] or time.monotonic() >= deadline):
            raise RuntimeError("terminal receipt exceeds reserved time/output boundary")
        return dict(status=terminal["status"], terminal=receipt, exit=exit_witness,
                    selection=terminal["selection"], receipt_seconds=receipt_elapsed,
                    charged_output_bytes=after)
    except Exception as exc:
        terminal["status"] = "FAILED"
        terminal["failure"] = _failure(exc, "finalize")
        terminal["selection"] = {"jet": None, "bank": None}
        try:
            if time.monotonic() < deadline:
                _checked_commit(out / "terminal-report.json", terminal, execution, deadline)
        except Exception:
            pass
        return dict(status="FAILED", terminal=None, exit=exit_witness,
                    selection={"jet": None, "bank": None})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    try:
        path = args.seal.resolve(strict=True)
        raw = path.read_bytes()
        plan = authority.strict_json(raw)
        if args.worker:
            if plan["execution"] is None or plan["execution"]["launch"]["argv"][5] != str(path):
                raise authority.AuthorityError("worker plan path mismatch")
            return _worker(plan, root)
        authority.entry(plan, root)
        if plan["execution"]["launch"]["argv"][5] != str(path):
            raise authority.AuthorityError("parent plan path mismatch")
        try:
            return _parent(plan, root, path, hashlib.sha256(raw).hexdigest())
        except Exception as exc:
            print("INFRA_STOP: " + str(exc), file=sys.stderr)
            return 1
    except (authority.AuthorityError, OSError, ValueError) as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
