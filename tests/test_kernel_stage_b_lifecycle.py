"""Controlled nonnull worker authority with real gates and low-level doubles."""
import copy
import hashlib
import io
import json
import platform
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace

import pytest

from validation.kernel_stage_b import authority
from validation.kernel_stage_a.commands import vector_hash


ROOT = Path(__file__).resolve().parents[1]
PROSPECTIVE = json.loads((ROOT / "validation/kernel_stage_b/prospective-plan.json").read_bytes())


def _released_binding(work):
    """A test-only, disposable binding shape; no manual approval is published."""
    plan = copy.deepcopy(PROSPECTIVE)
    def ref(path, kind):
        raw = path.read_bytes()
        return {"kind": kind, "path": str(path.relative_to(ROOT)),
                "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    ruling = work / "controlled-ruling.md"
    ruling.write_text("controlled source lifecycle only")
    note = ref(ruling, "markdown")
    current_rows = json.loads((ROOT / plan["evidence"]["source"]["path"]).read_bytes())
    old_rows = [row for row in current_rows if not row["path"].startswith("validation/kernel_stage_b/")
                and row["path"] not in {
                    "docs/amendments/2026-10-21-kernel-stage-b-external-adapter-source.md",
                    "docs/amendments/2026-10-21-kernel-stage-b-terminal-publication.md"}]
    old_path = work / "controlled-old-material.json"
    old_path.write_bytes(authority.canonical(old_rows))
    stage = json.loads((ROOT / plan["evidence"]["inventory"]["path"]).read_bytes())
    failures = []
    for row in stage["inventory"]:
        if row["row"] == 30:
            failures.append({"candidate": ":".join(row["candidate"]), "row": 30,
                             "transform": row["transform"], "source_status": "FAILED",
                             "strict_status": "FAILED",
                             "failed_fields": row["outcome"]["comparisons"]["A_B"]["failed_fields"],
                             "contraction_indices": list(range(8, 72)),
                             "decision": "retain_and_score_actual_state", "ruling": note})
    source = "a" * 40
    plan["approval"] = {"ruling": note, "approved": True,
                        "scope": "descriptive_actual_state_only",
                        "evidence_sha256": authority.digest(plan["evidence"]),
                        "failures": failures, "source_review": note,
                        "compatibility": {"old_source": authority.EXECUTED_A_SOURCE,
                                          "new_source": source,
                                          "old_manifest": ref(old_path, "source_manifest"),
                                          "new_manifest": plan["evidence"]["source"],
                                          "changed_paths": sorted(set(row["path"] for row in current_rows) -
                                                                  set(row["path"] for row in old_rows)),
                                          "decision": "external_adapter_only"}}
    host = {key: getattr(platform, key)() for key in ("node", "system", "release", "machine")}
    runtime = {"python": "controlled", "executable": sys.executable,
               "executable_sha256": "0" * 64, "implementation": "controlled",
               "process_image": {"method": "controlled", "path": sys.executable,
                                 "sha256": "0" * 64},
               "helpers": {name: {"path": name, "sha256": "0" * 64} for name in ("ps", "git")},
               "decimal_version": "controlled", "libmpdec_version": "controlled",
               "decimal_extension": "controlled", "decimal_extension_sha256": "0" * 64,
               "byteorder": sys.byteorder, "machine": host["machine"], "context": "controlled"}
    now, tick = time.time(), time.monotonic()
    out = work / "output"
    out.mkdir()
    for name in ("stdout.log", "stderr.log", "monitor-events.jsonl",
                 "monitor-evidence.jsonl", "monitor.json"):
        (out / name).write_bytes(b"")
    def observation(name, args, stdout):
        stdout_path = work / (name + ".stdout")
        stderr_path = work / (name + ".stderr")
        stdout_path.write_bytes(stdout)
        stderr_path.write_bytes(b"")
        return {"argv": args, "returncode": 0,
                "stdout": ref(stdout_path, "bytes"), "stderr": ref(stderr_path, "bytes")}
    vm = observation("vm", ["/usr/bin/vm_stat"],
                     b"Mach Virtual Memory Statistics: (page size of 4096 bytes)\n"
                     b"Pages free: 300000.\nPages speculative: 100000.\n")
    pressure = observation("pressure", ["/usr/bin/memory_pressure", "-Q"], b"controlled\n")
    power = observation("power", ["/usr/bin/pmset", "-g", "batt"], b"controlled\n")
    available = 400000 * 4096
    bootstrap = ROOT / "validation/kernel_stage_b/bootstrap.py"
    monitor = ROOT / "validation/kernel_stage_a/monitor.py"
    plan_path = work / "controlled-plan.json"
    witness = work / "controlled-witness.py"
    witness.write_bytes(b"# source-only controlled witness\n")
    worker_argv = [sys.executable, "-I", str(bootstrap), "--worker", "--seal", str(plan_path)]
    parent_argv = [sys.executable, "-I", str(bootstrap), "--seal", str(plan_path)]
    environment = {key: "1" for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
                                         "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
                                         "NUMEXPR_NUM_THREADS")}
    environment.update(PYTORCH_ENABLE_MPS_FALLBACK="0", PYTORCH_MPS_FAST_MATH="0")
    plan["execution"] = {"source_full_git": source,
                         "source_manifest": plan["evidence"]["source"], "runtime": runtime,
                         "host": host,
                         "admission": {"utc_epoch": now, "host": host, "vm_stat": vm,
                                       "memory_pressure": pressure, "power": power,
                                       "page_size": 4096, "free_pages": 300000,
                                       "speculative_pages": 100000,
                                       "available_bytes": available,
                                       "reserve_bytes": 409600000,
                                       "planning_envelope_bytes": available - 409600000,
                                       "free_disk_bytes": 4294967296},
                         "limits": {"outer_seconds": 1000, "candidate_seconds": 100,
                                    "incremental_bytes": 100000000,
                                    "output_bytes": 1000000,
                                    "free_disk_bytes": 4294967296,
                                    "numerical_threads": 1},
                         "boundary": {"allocation_start_monotonic": tick,
                                      "allocation_start_utc_epoch": now,
                                      "deadline_monotonic": tick + 1000,
                                      "baseline": "post-import/pre-allocation per worker",
                                      "absolute_rss": True, "process_tree_rss": True,
                                      "sequential_workers": True,
                                      "outputs_include_temporaries": True},
                         "launch": {"bootstrap": ref(bootstrap, "python_source"),
                                    "template_sha256": authority.digest(authority.TEMPLATE),
                                    "argv": worker_argv, "argv_sha256": vector_hash(worker_argv),
                                    "monitor": ref(monitor, "python_source"),
                                    "environment": environment,
                                    "fresh_utc_epoch": now, "free_disk_bytes": 4294967296,
                                    "power": power},
                         "terminal": {"witness": ref(witness, "python_source"),
                                      "parent_argv": parent_argv,
                                      "parent_argv_sha256": vector_hash(parent_argv),
                                      "publication_seconds": 10.0,
                                      "publication_bytes": 10000},
                         "qualification": None, "preparation_output": None,
                         "output": str(out)}
    plan["release"] = {"approved": True, "scope": "binding",
                       "payload_sha256": authority.digest({key: value for key, value in plan.items()
                                                            if key != "release"}),
                       "ruling": note}
    plan_path.write_bytes(authority.canonical(plan))
    return plan, out, runtime, now, tick


@pytest.mark.parametrize("helper_fails", [False, True])
def test_real_worker_authority_lifecycle_with_only_low_level_doubles(monkeypatch, helper_fails):
    from validation.kernel_stage_a import authority as a_authority
    from validation.kernel_stage_b.__main__ import _worker

    with tempfile.TemporaryDirectory(prefix=".task18-controlled-", dir=ROOT) as name:
        plan, out, runtime, now, tick = _released_binding(Path(name))
        monkeypatch.setattr(a_authority, "runtime", lambda: runtime)
        monkeypatch.setattr(authority.time, "time", lambda: now)
        monkeypatch.setattr(authority.time, "monotonic", lambda: tick)
        monkeypatch.setattr(authority.shutil, "disk_usage", lambda _: SimpleNamespace(free=2**40))
        calls = []
        monkeypatch.setattr(a_authority, "helper_artifact",
                            lambda path: {"path": path, "sha256": "0" * 64})
        class ControlledGitProcess:
            def __init__(self, command, **kwargs):
                calls.append(tuple(command[-2:]))
                self.pid = 700 + len(calls)
                self.returncode = 1 if helper_fails and len(calls) == 2 else 0
                self.stdout = io.StringIO()
                self.stderr = io.StringIO()
            def communicate(self, timeout=None):
                return (plan["execution"]["source_full_git"] + "\n" if len(calls) == 1
                        else "", "controlled helper failure" if self.returncode else "")
            def poll(self):
                return self.returncode
            def kill(self):
                self.returncode = -9
        monkeypatch.setattr(a_authority.subprocess, "Popen", ControlledGitProcess)
        if helper_fails:
            import builtins
            original_import = builtins.__import__
            def import_guard(name, *args, **kwargs):
                if name == "torch" or name.startswith("famjet"):
                    raise AssertionError("science imported after failed authority")
                return original_import(name, *args, **kwargs)
            monkeypatch.setattr(builtins, "__import__", import_guard)
            assert _worker(plan, ROOT) == 1
            assert json.loads((out / "stage-b.json").read_bytes())["failure"]["phase"] == "authority"
        else:
            assert authority.verify_worker(plan, ROOT, out / "monitor-events.jsonl") == tick + 1000
        events = [json.loads(line) for line in (out / "monitor-events.jsonl").read_bytes().splitlines()]
        assert [event["event"] for event in events] == [
            "authority_start", "authority_helper", "authority_helper_end",
            "authority_helper", "authority_helper_end", "authority_end"]
        assert events[-1]["success"] is (not helper_fails)
        assert [event["returncode"] for event in events if event["event"] == "authority_helper_end"] == (
            [0, 1] if helper_fails else [0, 0])
        assert all(event["reaped"] for event in events if event["event"] == "authority_helper_end")
        assert calls == [("rev-parse", "HEAD"), ("status", "--porcelain")]


def test_boolean_numerical_thread_limit_refuses(monkeypatch):
    with tempfile.TemporaryDirectory(prefix=".task18-controlled-", dir=ROOT) as name:
        plan, _, _, _, _ = _released_binding(Path(name))
        plan["execution"]["limits"]["numerical_threads"] = True
        plan["release"]["payload_sha256"] = authority.digest(
            {key: value for key, value in plan.items() if key != "release"})
        with pytest.raises(authority.AuthorityError, match="limits"):
            authority.validate_plan(plan)
