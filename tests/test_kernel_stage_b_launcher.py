"""Controlled source checks for the fixed Stage B project launcher."""
import hashlib
import json
from pathlib import Path

import pytest

from validation.kernel_stage_b import authority

AuthorityError = authority.AuthorityError
ROOT = Path(__file__).resolve().parents[1]


def launcher_fixture(tmp_path):
    root = tmp_path / "project"
    bin_dir = root / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    (root / ".venv" / "pyvenv.cfg").write_text("home = controlled\n")
    executable = tmp_path / "base-python"
    executable.write_bytes(b"controlled executable image")
    (bin_dir / "python").symlink_to(executable)
    runtime = {"executable": str(executable),
               "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest()}
    return root, runtime, executable


def test_project_launcher_preserves_lexical_symlink(tmp_path):
    root, runtime, executable = launcher_fixture(tmp_path)
    assert authority.project_launcher(root, runtime) == str(root / ".venv/bin/python")
    assert authority.project_launcher(root, runtime) != str(executable)


def test_project_launcher_rejects_wrong_target_or_hash(tmp_path):
    root, runtime, executable = launcher_fixture(tmp_path)
    with pytest.raises(AuthorityError):
        authority.project_launcher(root, dict(runtime, executable_sha256="0" * 64))
    other = tmp_path / "other-python"
    other.write_bytes(executable.read_bytes())
    (root / ".venv/bin/python").unlink()
    (root / ".venv/bin/python").symlink_to(other)
    with pytest.raises(AuthorityError):
        authority.project_launcher(root, runtime)


def test_project_launcher_rejects_missing_cfg_and_directory_escape(tmp_path):
    root, runtime, _ = launcher_fixture(tmp_path)
    (root / ".venv/pyvenv.cfg").unlink()
    with pytest.raises(AuthorityError):
        authority.project_launcher(root, runtime)
    outside = tmp_path / "cfg"
    outside.write_text("home = outside\n")
    (root / ".venv/pyvenv.cfg").symlink_to(outside)
    with pytest.raises(AuthorityError):
        authority.project_launcher(root, runtime)
    (root / ".venv/pyvenv.cfg").unlink()
    (root / ".venv").rename(root / "held")
    (root / ".venv").symlink_to(root / "held", target_is_directory=True)
    with pytest.raises(AuthorityError):
        authority.project_launcher(root, runtime)


def test_project_launcher_rejects_missing_or_looped_executable(tmp_path):
    root, runtime, _ = launcher_fixture(tmp_path)
    launcher = root / ".venv/bin/python"
    launcher.unlink()
    with pytest.raises(AuthorityError):
        authority.project_launcher(root, runtime)
    launcher.symlink_to(launcher)
    with pytest.raises(AuthorityError):
        authority.project_launcher(root, runtime)


def test_qualification_requires_bound_and_current_literal_launchers(tmp_path):
    from validation.kernel_stage_b.authority import _qualified_material

    manifest = tmp_path / "material.json"
    manifest.write_bytes(b"[]")
    ref = {"kind": "source_manifest", "path": manifest.name,
           "sha256": hashlib.sha256(b"[]").hexdigest(), "bytes": 2}
    launcher = str(tmp_path / ".venv/bin/python")
    source = "a" * 40
    runtime = {"executable": str(tmp_path / "base-python")}
    def execution(first):
        return {"runtime": runtime, "source_full_git": source, "source_manifest": ref,
                "launch": {"argv": [first, "-I", "bootstrap", "--worker", "--seal", "plan"],
                           "template_sha256": "template", "argv_sha256": "argv",
                           "monitor": "monitor", "bootstrap": "bootstrap"},
                "terminal": {"parent_argv": [first, "-I", "bootstrap", "--seal", "plan"]}}
    bound = execution(launcher)
    current = execution(launcher)
    binding = {"execution": bound}
    report = {"source_full_git": source, "source_manifest": ref,
              "template_sha256": "template", "argv_sha256": "argv"}
    q = {"runtime": runtime, "source_full_git": source, "source_manifest": ref,
         "template_sha256": "template", "monitor": "monitor", "compatibility": None}
    _qualified_material(q, current, binding, report, tmp_path)
    current["launch"]["argv"][0] = runtime["executable"]
    with pytest.raises(AuthorityError, match="project launcher"):
        _qualified_material(q, current, binding, report, tmp_path)
    current["launch"]["argv"][0] = launcher
    bound["terminal"]["parent_argv"][0] = runtime["executable"]
    with pytest.raises(AuthorityError, match="project launcher"):
        _qualified_material(q, current, binding, report, tmp_path)


def test_adopted_material_addition_preserves_all_historical_rows():
    rows = json.loads((ROOT / "docs/research/task18-kernel-stage-b-source-evidence/source-manifest.json").read_bytes())
    old = [row for row in rows if not row["path"].startswith("validation/kernel_stage_b/") and
           row["path"] not in {
               "docs/amendments/2026-10-21-kernel-stage-b-external-adapter-source.md",
               "docs/amendments/2026-10-21-kernel-stage-b-project-launcher.md",
               "docs/amendments/2026-10-21-kernel-stage-b-terminal-publication.md"}]
    assert len(old) == 79 and len(rows) == 88
    plan = json.loads((ROOT / "validation/kernel_stage_b/prospective-plan.json").read_bytes())
    sealed = json.loads((ROOT / plan["evidence"]["seal"]["path"]).read_bytes())[
        "observed"]["files"]
    compatibility = {"old_source": authority.EXECUTED_A_SOURCE,
                     "changed_paths": sorted(set(row["path"] for row in rows) -
                                             set(row["path"] for row in old))}
    authority._compare_material_compatibility(old, rows, compatibility, sealed)
    protected = next(row for row in rows if row["path"] == "requirements.lock")
    changed = [dict(row, sha256="0" * 64) if row is protected else row for row in rows]
    with pytest.raises(AuthorityError, match="historical material bytes"):
        authority._compare_material_compatibility(old, changed, compatibility, sealed)
