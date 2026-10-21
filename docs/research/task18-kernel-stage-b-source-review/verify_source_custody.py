"""Root custody audit only; stdlib, no scientific imports or experiment launch."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys


BASE = "fb26e86c6c78ab4e10cad4413101440304c9ff00"
FIX_BASE = "a993cad3044cefc00d4b42b41c4a2ec5bc75cd65"
ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs/research/task18-kernel-stage-b-source-evidence"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    head, output = sys.argv[1:]
    assert git("rev-parse", "HEAD").decode().strip() == head
    assert not git("status", "--porcelain"), "source acceptance requires clean tracked/unignored state"
    delivered = git("diff", "--name-only", "-z", BASE, head).decode().split("\0")
    delivered = [p for p in delivered if p]
    for name in delivered:
        actual = ROOT / name
        assert actual.is_file() and not actual.is_symlink(), name
        assert actual.read_bytes() == git("show", f"{head}:{name}"), name
    protected = ["famjet", "requirements.lock", "validation/kernel_stage_a",
                 "docs/research/task18-kernel-stage-a06-evidence",
                 "configs/development/jet_finite_raw_32768.yaml"]
    assert not git("diff", "--name-only", BASE, head, "--", *protected)
    manifest = json.loads((EVIDENCE / "source-manifest.json").read_bytes())
    assert manifest == sorted(manifest, key=lambda row: row["path"])
    assert len({row["path"] for row in manifest}) == len(manifest)
    for row in manifest:
        raw = (ROOT / row["path"]).read_bytes()
        assert set(row) == {"path", "bytes", "sha256"}
        assert row["bytes"] == len(raw) and row["sha256"] == sha(raw), row["path"]
    logs = json.loads((EVIDENCE / "run-index.json").read_bytes())
    assert len({r["name"] for r in logs["runs"]}) == len(logs["runs"])
    failures = 0
    for row in logs["runs"]:
        raw = (EVIDENCE / f'{row["name"]}.log').read_bytes()
        assert len(raw) == row["log_bytes"] and sha(raw) == row["log_sha256"], row["name"]
        record = json.loads((EVIDENCE / f'{row["name"]}.json').read_bytes())
        # Raw command records precede the enriched hash index; compare their actual schema.
        assert record == {"argv": row["argv"], "elapsed_seconds": row["elapsed_seconds"],
                          "exit_code": row["exit_code"], "log": row["name"] + ".log"}, row["name"]
        assert type(row["exit_code"]) is int
        assert row["elapsed_seconds"] >= 0 and isinstance(row["argv"], list)
        failures += row["exit_code"] != 0
    assert logs["failures"] == failures
    assert set(logs) == {"failures", "runs"}
    # Independently reconstruct the unchanged existing package hash; no package import.
    package = {str(p.relative_to(ROOT)): sha(p.read_bytes())
               for p in sorted((ROOT / "famjet").rglob("*.py"))}
    package_hash = sha(json.dumps(package, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False).encode())
    assert len(package) == 53
    assert package_hash == "15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050"
    lock_hash = sha((ROOT / "requirements.lock").read_bytes())
    assert lock_hash == "2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1"
    stage_a = git("ls-tree", "-r", "--name-only", BASE, "validation/kernel_stage_a").decode().splitlines()
    assert len(stage_a) == 15
    for name in stage_a:
        assert (ROOT / name).read_bytes() == git("show", f"{BASE}:{name}"), name
    scratch = ROOT / ".superpowers/sdd/2026-10-16-famjet/task-18-kernel-stage-b-source-report.md"
    report = ROOT / "docs/research/task18-kernel-stage-b-source-report.md"
    assert scratch.read_bytes() == report.read_bytes()
    plan = json.loads((ROOT / "validation/kernel_stage_b/prospective-plan.json").read_bytes())
    assert all(plan[key] is None for key in ("approval", "execution", "release"))
    assert len(plan["evidence"]["slots"]) == 768
    proof = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 base=BASE, fix_base=FIX_BASE, head=head,
                 delivered_git_paths_verified=len(delivered),
                 material_manifest_files_verified=len(manifest),
                 test_logs_verified=len(logs["runs"]), failed_attempts_retained=failures,
                 successful_attempts_retained=len(logs["runs"])-failures,
                 final_record=logs["runs"][-1], report_sha256=sha(report.read_bytes()),
                 report_mirror_equal=True, package=package_hash, package_files=len(package),
                 lock_sha256=lock_hash, stage_a_files=len(stage_a),
                 protected_paths_unchanged=True, prospective_authority_null=True,
                 experiment_permission=False)
    Path(output).write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
