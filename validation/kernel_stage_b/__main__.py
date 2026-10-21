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
    raw = authority.canonical(value)
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


def _write_infra_stop(plan, out, exc):
    """Retain a complete zero-work record after monitor initialization."""
    for name in ("snapshots", "requests", "scores"):
        (out / (name + ".jsonl")).touch(exist_ok=True)
    counts = {k: 0 for k in ("snapshots_attempted", "snapshots_completed", "requests_attempted",
                              "requests_completed", "worker_reads", "worker_factors", "predictions_scored",
                              "quarantined_histories", "fallback_rows")}
    failure = _failure(exc, "authority")
    combined = [dict(candidate=c["id"], status="incomplete", loss=None, infinite_loss_count=0,
                     has_infinite=False, has_undefined=False, query_count=0, complete=False)
                for c in plan["candidates"]]
    costs = [dict(candidate=c["id"], complete=False, direct_seconds=0.,
                  family_encoding_seconds=0., common_seconds=0., standalone_total_seconds=0.,
                  intervals=[]) for c in plan["candidates"]]
    stamp = time.monotonic()
    body = dict(version=1, plan_sha256=authority.digest(plan), status="INFRA_STOP",
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
    try:
        deadline = authority.verify_worker(plan, root, events)
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
                dict(version=1, status="PASS", plan_sha256=authority.digest(plan),
                     counts=dict(constructions=0, encodes=0, reads=0, factors=0, predictions=0)))
            return 0
        def checkpoint():
            if time.monotonic() >= deadline:
                raise TimeoutError("original outer deadline")
        result = execute(plan, Backend(plan, root), checkpoint)
        _atomic_json(out / "stage-b.json", result)
        return 0 if result["status"] == "COMPLETED" else 1
    except Exception as exc:
        _write_infra_stop(plan, out, exc)
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
    _atomic_json(external, dict(version=1, monitor_status=result["status"],
                                               monitor_returncode=result["returncode"],
                                               outer_seconds=result["outer_seconds"],
                                               commit_monotonic=time.monotonic(),
                                               plan_file_sha256=plan_file_sha256,
                                               same_plan_bytes=same_plan))
    if plan["release"]["scope"] == "binding":
        worker = out / "binding-worker.json"
        success = (same_plan and result["status"] == "COMPLETED" and result["returncode"] == 0 and
                   worker.is_file() and time.monotonic() < deadline)
        if success:
            body = authority.strict_json(worker.read_bytes())
            success = body["counts"] == dict(constructions=0, encodes=0, reads=0,
                                             factors=0, predictions=0)
        report = dict(version=1, status="PASS" if success else "FAILED",
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
