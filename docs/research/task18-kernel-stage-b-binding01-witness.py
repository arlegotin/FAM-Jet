"""Unreleased one-use binding witness; no execution merely by drafting this file."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


ROOT = Path("/Users/artemlegotin/Documents/git_alter/FAM-Jet")
PLAN = ROOT / "artifacts/task18-kernel-stage-b-binding-01-prep/plan.json"
sys.path.insert(0, str(ROOT))
from validation.kernel_stage_b import authority
from validation.kernel_stage_b.__main__ import finalize_terminal
from validation.kernel_stage_a.commands import vector_hash


def save(path, value):
    raw = authority.canonical(value)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    if path.read_bytes() != raw:
        raise RuntimeError("witness evidence commitment failed")


def main():
    raw = PLAN.read_bytes()
    plan = authority.strict_json(raw)
    authority.validate_plan(plan)
    execution = plan["execution"]
    if plan["release"]["scope"] != "binding" or execution["qualification"] is not None:
        raise RuntimeError("this one-use witness permits only the first empty binding")
    if execution["preparation_output"] != str(PLAN.parent):
        raise RuntimeError("binding preparation identity")
    expected = [execution["runtime"]["executable"], "-I",
                str(ROOT / "validation/kernel_stage_b/bootstrap.py"), "--seal", str(PLAN)]
    witness = execution["terminal"]["witness"]
    if (execution["terminal"]["parent_argv"] != expected or
            execution["terminal"]["parent_argv_sha256"] != vector_hash(expected) or
            authority.read_verified(ROOT, witness) != Path(__file__).read_bytes()):
        raise RuntimeError("sealed parent/witness identity")
    # Exclusive persistent marker prevents automatic reuse after any outcome.
    with (PLAN.parent / "launched.once").open("x") as marker:
        marker.write(hashlib.sha256(raw).hexdigest() + "\n")
    env = dict(os.environ)
    env.update(execution["launch"]["environment"])
    launched = time.monotonic()
    if launched >= execution["boundary"]["deadline_monotonic"]:
        raise RuntimeError("original binding deadline expired before launch")
    with (PLAN.parent / "parent.stdout").open("xb") as stdout, \
            (PLAN.parent / "parent.stderr").open("xb") as stderr:
        parent = subprocess.Popen(expected, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
        returncode = parent.wait()
        reaped = time.monotonic()
    exit_witness = dict(version=1, plan_sha256=authority.digest(plan),
                        plan_file_sha256=hashlib.sha256(raw).hexdigest(), witness=witness,
                        parent_argv=expected, parent_argv_sha256=vector_hash(expected),
                        parent_invocations=1, parent_pid=parent.pid,
                        launch_monotonic=launched, reaped_monotonic=reaped,
                        returncode=returncode, reaped=True)
    save(PLAN.parent / "exit-witness.json", exit_witness)
    result = finalize_terminal(plan, ROOT, exit_witness)
    save(PLAN.parent / "witness-result.json", result)
    print(json.dumps({"parent_returncode": returncode, "terminal_status": result["status"]},
                     sort_keys=True), flush=True)
    return 0 if returncode == 0 and result["status"] == "ELIGIBLE_PENDING_PUBLICATION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
