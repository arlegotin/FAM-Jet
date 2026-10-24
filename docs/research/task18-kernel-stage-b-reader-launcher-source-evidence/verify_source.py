"""Check source-only custody and preserved test output bytes."""

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
BASE = "38093b1ec1d0489a5d3d6247f76ce8baa07d6e74"
SOURCE = "58014373c8f3b542b978d621f3c83652115526aa"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


manifest_path = "docs/research/task18-kernel-stage-b-source-evidence/source-manifest.json"
rows = json.loads((ROOT / manifest_path).read_bytes())
old = {r["path"]: r for r in json.loads(git("show", BASE + ":" + manifest_path))}
current = {r["path"]: r for r in rows}
assert len(rows) == len(current) == 88
assert [r["path"] for r in rows] == sorted(current)
assert [p for p in current if old[p] != current[p]] == ["validation/kernel_stage_b/production.py"]
for row in rows:
    raw = (ROOT / row["path"]).read_bytes()
    assert len(raw) == row["bytes"] and sha(raw) == row["sha256"], row["path"]
historical = json.loads((ROOT / "docs/research/task18-kernel-stage-b-source-review/historical-material-manifest.json").read_bytes())
assert len(historical) == 79
assert all(current[r["path"]] == r for r in historical)
package = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted((ROOT / "famjet").rglob("*.py"))}
package_hash = sha(json.dumps(package, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
assert len(package) == 53
assert package_hash == "15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050"
lock_hash = sha((ROOT / "requirements.lock").read_bytes())
assert lock_hash == "2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1"
stage_a = git("ls-tree", "-r", "--name-only", BASE, "validation/kernel_stage_a").decode().splitlines()
assert len(stage_a) == 15
assert all((ROOT / p).read_bytes() == git("show", BASE + ":" + p) for p in stage_a)
changed = git("diff", "--name-only", BASE, SOURCE).decode().splitlines()
assert sorted(changed) == sorted([
    "validation/kernel_stage_b/production.py",
    "tests/test_kernel_stage_b_reader_launcher.py",
    "tests/test_kernel_stage_b_input_dtype.py",
    manifest_path,
    "validation/kernel_stage_b/prospective-plan.json",
])
plan = json.loads((ROOT / "validation/kernel_stage_b/prospective-plan.json").read_bytes())
assert all(plan[k] is None for k in ("approval", "execution", "release"))
manifest_raw = (ROOT / manifest_path).read_bytes()
assert plan["evidence"]["source"]["sha256"] == sha(manifest_raw)
assert plan["evidence"]["source"]["bytes"] == len(manifest_raw)
invocations = []
for label in ("01-red-reader", "02-green-reader", "03-cover"):
    record = json.loads((EVIDENCE / (label + ".json")).read_bytes())
    for item in record["raw"].values():
        raw = (ROOT / item["path"]).read_bytes()
        assert len(raw) == item["bytes"] and sha(raw) == item["sha256"]
    invocations.append(record)
assert [r["exit_code"] for r in invocations] == [1, 0, 0]
assert b"reader Python image mismatch" in (EVIDENCE / "01-red-reader.stdout").read_bytes()
assert b"67 passed in " in (EVIDENCE / "03-cover.stdout").read_bytes()
proof = {"base": BASE, "source_commit": SOURCE,
         "material_rows": 88, "historical_rows_equal": 79,
         "changed_material_rows": ["validation/kernel_stage_b/production.py"],
         "material_sha256": sha(manifest_raw), "package_files": 53,
         "package_sha256": package_hash, "lock_sha256": lock_hash,
         "stage_a_files_byte_equal": len(stage_a), "protected_diff_empty": True,
         "test_exit_codes": [r["exit_code"] for r in invocations],
         "final_test_result": "67 passed in 9.63s",
         "prospective_authority_null": True, "experiment_executed": False}
(EVIDENCE / "custody-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof, indent=2))
