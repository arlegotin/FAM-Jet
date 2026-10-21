"""Controlled source-review checks for the fixed Stage B authority and driver."""
import copy
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads((ROOT / "validation/kernel_stage_b/prospective-plan.json").read_bytes())


def test_full_archived_evidence_accepts_without_scientific_work():
    from validation.kernel_stage_b.authority import validate_evidence

    stage = validate_evidence(PLAN["evidence"], ROOT)
    assert stage["status"] == "FAILED"
    assert len(stage["inventory"]) == 768


@pytest.mark.parametrize("counter", ["worker:read", "candidate_setup"])
def test_archived_counter_value_tamper_refuses(counter, monkeypatch):
    from validation.kernel_stage_b import authority

    original = authority.read_verified
    def changed(root, ref):
        raw = original(root, ref)
        if ref == PLAN["evidence"]["inventory"]:
            stage = authority.strict_json(raw)
            stage["counts"][counter] = 0
            return authority.canonical(stage)
        return raw
    monkeypatch.setattr(authority, "read_verified", changed)
    with pytest.raises(authority.AuthorityError, match="count|worker"):
        authority.validate_evidence(PLAN["evidence"], ROOT)


def test_current_manifest_covers_all_preserved_material_before_import():
    from validation.kernel_stage_b.authority import _source_manifest, STAGE_A_HASHES

    sealed = json.loads((ROOT / PLAN["evidence"]["seal"]["path"]).read_bytes())["observed"]["files"]
    rows = _source_manifest(ROOT, PLAN["evidence"]["source"], sealed)
    paths = {row["path"] for row in rows}
    assert len(rows) == 87
    assert all("validation/kernel_stage_a/" + name in paths for name in STAGE_A_HASHES)


def test_duplicate_static_proof_is_not_six_candidate_proofs():
    from validation.kernel_stage_b.authority import AuthorityError, validate_evidence

    evidence = copy.deepcopy(PLAN["evidence"])
    evidence["statics"][1] = evidence["statics"][0]
    with pytest.raises(AuthorityError, match="archive|static"):
        validate_evidence(evidence, ROOT)


def test_historical_manifest_requires_complete_preserved_inventory():
    from validation.kernel_stage_b.authority import AuthorityError, _compare_material_compatibility

    rows = json.loads((ROOT / PLAN["evidence"]["source"]["path"]).read_bytes())
    sealed = json.loads((ROOT / PLAN["evidence"]["seal"]["path"]).read_bytes())["observed"]["files"]
    old = [row for row in rows if not row["path"].startswith("validation/kernel_stage_b/") and
           row["path"] != "docs/amendments/2026-10-21-kernel-stage-b-external-adapter-source.md"]
    old = [row for row in old if row["path"] != "validation/kernel_stage_a/README.md"]
    compatibility = {"old_source": "81204796ade55ce9e7202bc9253b1b61db6a65a3",
                     "new_source": "0" * 40, "changed_paths": [], "decision": "external_adapter_only"}
    with pytest.raises(AuthorityError, match="historical material"):
        _compare_material_compatibility(old, rows, compatibility, sealed)


def test_qualification_binds_actual_binding_runtime_and_manifest(tmp_path):
    from validation.kernel_stage_b.authority import AuthorityError, _qualified_material

    def ref(name, data):
        path = tmp_path / name
        path.write_bytes(data)
        return {"kind": "source_manifest", "path": name,
                "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

    old = ref("old.json", b"[]")
    new = ref("new.json", b"[1]")
    launch = {"bootstrap": {"sha256": "b"}, "monitor": {"sha256": "m"},
              "template_sha256": "t", "argv_sha256": "a"}
    binding = {"execution": {"source_full_git": "1" * 40, "source_manifest": old,
                             "runtime": {"executable": "old"}, "launch": launch}}
    report = {"source_full_git": "1" * 40, "source_manifest": old,
              "template_sha256": "t", "argv_sha256": "a"}
    current = {"source_full_git": "2" * 40, "source_manifest": new,
               "runtime": {"executable": "new"}, "launch": launch}
    q = {"source_full_git": "1" * 40, "source_manifest": old,
         "runtime": {"executable": "new"}, "template_sha256": "t",
         "monitor": launch["monitor"], "compatibility": {"qualified_source": "1" * 40,
         "current_source": "2" * 40, "material_manifest_equal": True, "ruling": None}}
    with pytest.raises(AuthorityError, match="qualified binding runtime"):
        _qualified_material(q, current, binding, report, tmp_path)
    q["runtime"] = {"executable": "old"}
    current["runtime"] = q["runtime"]
    with pytest.raises(AuthorityError, match="qualified material manifest"):
        _qualified_material(q, current, binding, report, tmp_path)


def test_qualification_requires_explicit_ruling_for_distinct_git(tmp_path):
    from validation.kernel_stage_b.authority import AuthorityError, _qualified_material

    material = tmp_path / "material.json"
    material.write_bytes(b"[]")
    ref = {"kind": "source_manifest", "path": "material.json",
           "sha256": hashlib.sha256(b"[]").hexdigest(), "bytes": 2}
    ruling = tmp_path / "ruling.md"
    ruling.write_text("manual compatibility")
    ruling_ref = {"kind": "markdown", "path": "ruling.md",
                  "sha256": hashlib.sha256(ruling.read_bytes()).hexdigest(),
                  "bytes": len(ruling.read_bytes())}
    launch = {"bootstrap": {"sha256": "b"}, "monitor": {"sha256": "m"},
              "template_sha256": "t", "argv_sha256": "a"}
    bound = {"source_full_git": "1" * 40, "source_manifest": ref,
             "runtime": {"executable": "same"}, "launch": launch}
    binding = {"execution": bound}
    report = {"source_full_git": bound["source_full_git"], "source_manifest": ref,
              "template_sha256": "t", "argv_sha256": "a"}
    current = {"source_full_git": "2" * 40, "source_manifest": ref,
               "runtime": bound["runtime"], "launch": launch}
    q = {"source_full_git": bound["source_full_git"], "source_manifest": ref,
         "runtime": bound["runtime"], "monitor": launch["monitor"],
         "template_sha256": "t", "compatibility": None}
    with pytest.raises(AuthorityError, match="explicit compatibility"):
        _qualified_material(q, current, binding, report, tmp_path)
    q["compatibility"] = {"qualified_source": "1" * 40, "current_source": "2" * 40,
                          "material_manifest_equal": True, "ruling": ruling_ref}
    _qualified_material(q, current, binding, report, tmp_path)
    q["compatibility"]["unreviewed_extra"] = True
    with pytest.raises(AuthorityError, match="compatibility"):
        _qualified_material(q, current, binding, report, tmp_path)


def test_boolean_observation_returncode_refuses():
    from validation.kernel_stage_b.authority import AuthorityError, _observation

    empty = {"kind": "bytes", "path": "empty", "sha256": "0" * 64, "bytes": 0}
    with pytest.raises(AuthorityError, match="observation"):
        _observation({"argv": ["controlled"], "returncode": False,
                      "stdout": empty, "stderr": empty})


def test_inherited_unknown_child_proof_is_exactly_pinned():
    from validation.kernel_stage_b.authority import AuthorityError, _guard_proof, GUARD_PROOF

    ref = {"kind": "existing_guard_proof", "path": GUARD_PROOF[0],
           "bytes": GUARD_PROOF[1], "sha256": GUARD_PROOF[2]}
    _guard_proof(ROOT, ref)
    with pytest.raises(AuthorityError, match="unknown-child proof identity"):
        _guard_proof(ROOT, dict(ref, sha256="0" * 64))


def _driver_plan(tmp_path):
    ids = [("jet", "a"), ("bank", "a"), ("bank", "b"),
           ("jet", "b"), ("jet", "c"), ("bank", "c")]
    candidates = [dict(id=f"{family}:{ridge}", family=family, config_sha256="0" * 64)
                  for family, ridge in ids]
    entries = [dict(episode_id=f"controlled-{i}", query_ids=list(range(8)),
                    length=(128, 512, 2048)[i // 32]) for i in range(96)]
    plan = {"execution": {"output": str(tmp_path),
                          "boundary": {"deadline_monotonic": 10**20},
                          "limits": {"candidate_seconds": 1000}, "source_manifest": None},
            "candidates": candidates}
    return plan, entries


def test_prepare_stop_retains_known_config_and_all_unscored_identities(tmp_path):
    from validation.kernel_stage_b.driver import execute

    plan, entries = _driver_plan(tmp_path)
    config = {"kind": "resolved_run_config", "path": "resolved-panel-config.json",
              "sha256": "0" * 64, "bytes": 2}
    class Backend:
        def __init__(self):
            self.entries = entries
            self.resolved_ref = None
        def prepare(self):
            (tmp_path / config["path"]).write_bytes(b"{}")
            self.resolved_ref = config
            raise RuntimeError("controlled prepare stop")
    result = execute(plan, Backend(), lambda: None)
    assert result["status"] == "INFRA_STOP"
    assert result["resolved_panel_config"] == config
    assert len(result["failure"]["remaining"]) == 576
    assert result["failure"]["remaining"][0]["query_ids"] == list(range(8))


def test_score_stop_uses_attempted_request_ordinal(tmp_path):
    from validation.kernel_stage_b.driver import execute

    plan, entries = _driver_plan(tmp_path)
    class Backend:
        def prepare(self):
            return {"entries": entries, "resolved_panel_config": None}
        def encode(self, family, entry):
            return {"record": {"trigger": None, "snapshot_hash": "0" * 64}}
        def read(self, candidate, entry, snapshot):
            request = tmp_path / "request-000.json"
            request.write_bytes(b"{}")
            self.on_attempt({"kind": "request", "path": request.name,
                             "sha256": hashlib.sha256(b"{}").hexdigest(), "bytes": 2})
            return {"numeric": {}, "counts": {"read": 1}, "seconds": 0.0,
                    "request": None, "stdout": None, "stderr": None}
        def score(self, candidate, entry, numeric, trigger):
            raise RuntimeError("controlled scoring stop")
    result = execute(plan, Backend(), lambda: None)
    assert result["failure"]["phase"] == "score"
    assert result["failure"]["ordinal"] == 0
    assert len(result["failure"]["remaining"]) == 576


def test_later_stop_keeps_completed_candidate_score_evidence(tmp_path):
    from validation.kernel_stage_b.driver import execute

    plan, entries = _driver_plan(tmp_path)
    class Backend:
        def prepare(self):
            return {"entries": entries, "resolved_panel_config": None}
        def encode(self, family, entry):
            return {"record": {"trigger": None, "snapshot_hash": "0" * 64}}
        def read(self, candidate, entry, snapshot):
            if candidate["id"] == "bank:a":
                raise RuntimeError("second candidate stop")
            return {"numeric": {}, "counts": {"read": 1}, "seconds": 0.0,
                    "request": None, "stdout": None, "stderr": None}
        def score(self, candidate, entry, numeric, trigger):
            return [{"fallback": False, "loss_status": "ok", "infinite_loss": False} for _ in range(8)]
    result = execute(plan, Backend(), lambda: None)
    assert result["status"] == "INFRA_STOP"
    assert result["combined"][0]["query_count"] == 768
    assert result["combined"][0]["complete"] is True
    assert result["selection"] == {"jet": None, "bank": None}


def test_boolean_reader_version_and_unused_diagnostic_values_refuse():
    from validation.kernel_stage_b.production import decode_response, validate_window_order

    numeric = {"prediction": [[[None] * 8 for _ in range(8)]], "logits": None,
               "support": [[None] * 8], "failure": [[True] * 8], "schema_version": True,
               "diagnostics": {name: [[False] * 8] for name in
                               ("numerical_eligible", "prediction_valid", "numeric_supported",
                                "factual_support_available", "quarantined")}}
    numeric["diagnostics"].update(
        failure_code=[[[5, 0] for _ in range(8)]],
        reconstructed_mass=[[[None, None] for _ in range(8)]],
        cancellation_bound=[[[None, None] for _ in range(8)]])
    response = {"numeric": numeric, "counts": {"read": 1}, "windows": [],
                "coefficients": [], "window_vectors": [], "seconds": 0.0}
    with pytest.raises(ValueError, match="version"):
        decode_response(response)
    numeric["schema_version"] = 1
    numeric["diagnostics"]["reconstructed_mass"][0][0][1] = 1.0
    with pytest.raises(ValueError, match="unused"):
        validate_window_order(response, ("mean",) * 8, False)


def test_invalid_interval_unexecuted_diagnostics_remain_null():
    from validation.kernel_stage_b.production import validate_window_order

    diagnostics = {"failure_code": [[[7, 0]] + [[0, 0] for _ in range(7)]],
                   "quarantined": [[False] * 8],
                   "reconstructed_mass": [[[1.0, None]] + [[None, None] for _ in range(7)]],
                   "cancellation_bound": [[[None, None] for _ in range(8)]]}
    response = {"numeric": {"diagnostics": diagnostics}, "windows": []}
    with pytest.raises(ValueError, match="unexecuted"):
        validate_window_order(response, ("mean",) * 8, True,
                              [[(1.0, 1.0)] for _ in range(8)])


def test_decode_failure_is_not_labeled_transport(tmp_path):
    from validation.kernel_stage_b.driver import execute
    from validation.kernel_stage_b.production import DecodeError

    plan, entries = _driver_plan(tmp_path)
    class Backend:
        def prepare(self):
            return {"entries": entries, "resolved_panel_config": None}
        def encode(self, family, entry):
            return {"record": {"trigger": None, "snapshot_hash": "0" * 64}}
        def read(self, candidate, entry, snapshot):
            raise DecodeError("controlled malformed response")
    result = execute(plan, Backend(), lambda: None)
    assert result["failure"]["phase"] == "decode"
    assert result["counts"]["predictions_scored"] == 0


def test_partial_score_journal_retains_only_committed_rows(tmp_path, monkeypatch):
    from validation.kernel_stage_b import driver

    plan, entries = _driver_plan(tmp_path)
    append = driver._append
    seen = 0
    def interrupted(path, value):
        nonlocal seen
        if path.name == "scores.jsonl":
            seen += 1
            if seen == 4:
                raise OSError("controlled fourth-score write failure")
        append(path, value)
    monkeypatch.setattr(driver, "_append", interrupted)
    class Backend:
        def prepare(self):
            return {"entries": entries, "resolved_panel_config": None}
        def encode(self, family, entry):
            return {"record": {"trigger": "controlled quarantine", "snapshot_hash": "0" * 64}}
        def score(self, candidate, entry, numeric, trigger):
            return [{"fallback": True, "loss_status": "infinite_loss", "infinite_loss": True}
                    for _ in range(8)]
    result = driver.execute(plan, Backend(), lambda: None)
    assert result["status"] == "INFRA_STOP"
    assert result["counts"]["predictions_scored"] == 3
    assert result["counts"]["fallback_rows"] == 3
    assert result["combined"][0]["query_count"] == 3
    assert result["combined"][0]["has_infinite"] is True
    assert len((tmp_path / "scores.jsonl").read_bytes().splitlines()) == 3


def test_controlled_full_panel_success_and_quarantine_inventory(tmp_path, monkeypatch):
    import base64
    import struct
    from famjet.eval import metrics
    from validation.kernel_stage_b.driver import execute
    from validation.kernel_stage_b.authority import canonical, digest, PACKAGE_HASH
    from validation.kernel_stage_a.commands import vector_hash

    plan, _ = _driver_plan(tmp_path)
    panel_raw = (ROOT / PLAN["panel"]["path"]).read_bytes()
    panel = json.loads(panel_raw)
    entries = [dict(entry, query_ids=list(range(8))) for entry in
               panel["splits"]["development_fit"]["episodes"]]
    def output_ref(path, kind):
        raw = path.read_bytes()
        return {"kind": kind, "path": tmp_path.name + "/" + path.name,
                "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    panel_path = tmp_path / "panel-manifest.json"
    panel_path.write_bytes(panel_raw)
    plan["panel"] = output_ref(panel_path, "existing_manifest")
    config_source = tmp_path / "original-panel-config.yaml"
    config_source.write_bytes((ROOT / PLAN["panel_config"]["path"]).read_bytes())
    plan["panel_config"] = output_ref(config_source, "run_config_yaml")
    for source_name in ("panel_producer", "exposure"):
        source_path = tmp_path / (source_name + Path(PLAN[source_name]["path"]).suffix)
        source_path.write_bytes((ROOT / PLAN[source_name]["path"]).read_bytes())
        plan[source_name] = output_ref(source_path, PLAN[source_name]["kind"])
    training_source = tmp_path / "frozen-training-metadata.json"
    training_source.write_bytes((ROOT / PLAN["training"]["path"]).read_bytes())
    plan["training"] = output_ref(training_source, "frozen_training")
    material_path = tmp_path / "controlled-source-manifest.json"
    material_path.write_bytes((ROOT / PLAN["evidence"]["source"]["path"]).read_bytes())
    plan["execution"]["source_manifest"] = output_ref(material_path, "source_manifest")
    specs = {}
    for candidate in plan["candidates"]:
        spec = {"controlled_method": candidate["id"]}
        path = tmp_path / (candidate["id"].replace(":", "-") + "-static.json")
        path.write_bytes(canonical(spec))
        candidate["static"] = output_ref(path, "static_export")
        rate_path = tmp_path / (candidate["id"].replace(":", "-") + "-rates.json")
        rate_path.write_bytes(b"[]")
        candidate["rates"] = output_ref(rate_path, "represented_rates")
        candidate["config_sha256"] = digest(spec)
        candidate["writer_sha256"] = "0" * 64
        specs[candidate["id"]] = spec
    plan_path = tmp_path / "plan.json"
    witness_path = tmp_path / "controlled-witness.py"
    witness_path.write_bytes(b"# controlled source-only witness\n")
    witness_ref = {"kind": "python_source", "path": tmp_path.name + "/" + witness_path.name,
                   "sha256": hashlib.sha256(witness_path.read_bytes()).hexdigest(),
                   "bytes": len(witness_path.read_bytes())}
    parent_argv = ["python", "-I", "bootstrap", "--seal", str(plan_path)]
    plan["execution"]["boundary"]["allocation_start_monotonic"] = 0.0
    plan["execution"]["limits"]["output_bytes"] = 20000000
    plan["execution"]["preparation_output"] = None
    plan["execution"]["launch"] = {"argv": ["python", "-I", "bootstrap", "--worker",
                                       "--seal", str(plan_path)]}
    plan["execution"]["terminal"] = {"witness": witness_ref, "parent_argv": parent_argv,
                                      "parent_argv_sha256": vector_hash(parent_argv),
                                      "publication_seconds": 10.0,
                                      "publication_bytes": 1000000}
    plan["release"] = {"scope": "panel"}
    plan_path.write_bytes(canonical(plan))
    def controlled_aggregate(scores):
        assert len(scores) == 256
        return {"status": "ok", "loss": sum(row["loss"] for row in scores) / 256,
                "infinite_loss_count": 0, "fallback_count": sum(row["fallback"] for row in scores),
                "query_count": len(scores)}
    monkeypatch.setattr(metrics, "aggregate_scores", controlled_aggregate)
    class Backend:
        def __init__(self):
            self.read_ordinal = 0
        def prepare(self):
            config_path = tmp_path / "resolved-panel-config.json"
            config_path.write_bytes(canonical({"data": panel["data"], "development": {"data_seed": 20261017018}}))
            return {"entries": entries, "resolved_panel_config":
                    {**output_ref(config_path, "resolved_run_config"), "path": config_path.name}}
        def encode(self, family, entry):
            state = {"schema_version": 1, "parameter_hash": "0" * 64, "payload": {},
                     "last_time": {}, "valid": {}, "event_offset": {}}
            body = dict(state, format="famjet.snapshot", format_version=1)
            path = tmp_path / f"snapshot-{family}-{entry['episode_id']}.json"
            path.write_bytes(canonical({"body": body, "checksum": digest(body)}))
            trigger = {"reason": "controlled quarantine"} if (
                family == "jet" and entry["episode_id"] == entries[0]["episode_id"]) else None
            record = {"version": 1, "family": family, "history_id": entry["episode_id"],
                      "writer_sha256": "0" * 64,
                      "snapshot": {**output_ref(path, "snapshot"), "path": path.name},
                      "snapshot_hash": digest(state), "logical_bytes": 0,
                      "trigger": trigger, "event_count": entry["length"],
                      "encoding_seconds": 0.0}
            return {"state": state, "record": record}
        def read(self, candidate, entry, snapshot):
            ordinal = self.read_ordinal
            self.read_ordinal += 1
            query_record = {"dtype": "int64", "shape": [1, 8],
                            "data": base64.b64encode(struct.pack("<8q", *range(8))).decode()}
            request = {"method": specs[candidate["id"]], "state": snapshot["state"],
                       "queries": {"history_ids": [entry["episode_id"]],
                                   "query_ids": query_record}, "operation": "read",
                       "model_hash": candidate["config_sha256"], "source_hash": PACKAGE_HASH}
            request_path = tmp_path / f"request-{ordinal:03}.json"
            request_path.write_bytes(canonical(request))
            request_ref = {**output_ref(request_path, "request"), "path": request_path.name}
            self.on_attempt(request_ref)
            diagnostics = {name: [[False] * 8] for name in
                           ("numerical_eligible", "prediction_valid", "numeric_supported",
                            "factual_support_available", "quarantined")}
            diagnostics.update(failure_code=[[[0, 0] for _ in range(8)]],
                               reconstructed_mass=[[[None, None] for _ in range(8)]],
                               cancellation_bound=[[[None, None] for _ in range(8)]])
            response = {"numeric": {"schema_version": 1, "logits": None,
                                    "prediction": [[[0.0] * 8 for _ in range(8)]],
                                    "support": [[None] * 8], "failure": [[False] * 8],
                                    "diagnostics": diagnostics},
                        "counts": {"read": 1}, "windows": [], "coefficients": [],
                        "window_vectors": [], "seconds": 0.0}
            stdout_path = tmp_path / f"reader-{ordinal:03}.jsonl"
            stdout_path.write_bytes(canonical({"counter": "read"}) + b"\n" + canonical(response) + b"\n")
            stderr_path = tmp_path / f"reader-{ordinal:03}.stderr"
            stderr_path.write_bytes(b"")
            return {"numeric": response["numeric"], "counts": response["counts"],
                    "seconds": 0.0, "request": request_ref,
                    "stdout": {**output_ref(stdout_path, "bytes"), "path": stdout_path.name},
                    "stderr": {**output_ref(stderr_path, "bytes"), "path": stderr_path.name}}
        def score(self, candidate, entry, numeric, trigger):
            assert (numeric is None) == (trigger is not None)
            loss = next(i for i, c in enumerate(plan["candidates"]) if c["id"] == candidate["id"])
            return [{"schema_version": 2, "method": candidate["id"],
                     "history_id": entry["episode_id"], "query_id": q,
                     "regime": entry["regime"], "manifest_hash": panel["manifest_hash"],
                     "fallback": trigger is not None, "loss_status": "ok",
                     "infinite_loss": False, "loss": loss} for q in range(8)]
    result = execute(plan, Backend(), lambda: None)
    assert result["status"] == "COMPLETED"
    assert result["counts"] == {"snapshots_attempted": 192, "snapshots_completed": 192,
                                "requests_attempted": 573, "requests_completed": 573,
                                "worker_reads": 573, "worker_factors": 0,
                                "predictions_scored": 4608, "quarantined_histories": 1,
                                "fallback_rows": 24}
    assert len((tmp_path / "scores.jsonl").read_bytes().splitlines()) == 4608
    assert len((tmp_path / "requests.jsonl").read_bytes().splitlines()) == 1146
    assert len(result["summaries"]) == 18
    assert all(row["complete"] and row["query_count"] == 768 for row in result["combined"])
    assert result["selection"] == {"jet": "jet:a", "bank": "bank:a"}
    from validation.kernel_stage_b.__main__ import finalize_terminal
    from validation.kernel_stage_b.authority import validate_completion
    (tmp_path / "stage-b.json").write_bytes(canonical(result))
    (tmp_path / "monitor.json").write_bytes(b'{"status":"COMPLETED","returncode":0}')
    program_end = result["end_monotonic"] + 2.0
    monkeypatch.setattr("validation.kernel_stage_b.authority.validate_plan", lambda _: None)
    monkeypatch.setattr("validation.kernel_stage_b.__main__.time.monotonic", lambda: program_end)
    witness = {"version": 1, "plan_sha256": digest(plan),
               "plan_file_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
               "witness": witness_ref, "parent_argv": parent_argv,
               "parent_argv_sha256": vector_hash(parent_argv), "parent_invocations": 1,
               "parent_pid": 123, "launch_monotonic": 1.0,
               "reaped_monotonic": result["end_monotonic"] + 1.0,
               "returncode": 0, "reaped": True}
    terminal_result = finalize_terminal(plan, tmp_path.parent, witness)
    terminal = json.loads((tmp_path / "terminal-report.json").read_bytes())
    assert terminal_result["status"] == "ELIGIBLE_PENDING_PUBLICATION", terminal["failure"]
    assert terminal["intervals"][0]["start"] == 0.0
    assert terminal["intervals"][-1]["end"] == program_end
    assert terminal["intervals"][-1]["owner"] == "common"
    assert len(terminal["costs"]) == 6
    def ref(path, kind):
        raw = path.read_bytes()
        return {"kind": kind, "path": path.name, "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw)}
    charged = sum(path.stat().st_size for path in tmp_path.iterdir() if path.is_file())
    invocation = {"version": 1, "witness": witness_ref, "plan_sha256": digest(plan),
                  "actual_returncode": 0, "publication_verified_monotonic": program_end + 4.0,
                  "output_bytes": charged, "commit_success": True}
    invocation_path = tmp_path.parent / "controlled-invocation.json"
    invocation_path.write_bytes(canonical(invocation))
    ruling_path = tmp_path.parent / "controlled-ruling.md"
    ruling_path.write_text("controlled publication")
    publication = {"version": 1, "approved": True,
                   "terminal": {**ref(tmp_path / "terminal-report.json", "terminal_report"),
                                "path": tmp_path.name + "/terminal-report.json"},
                   "witness": witness_ref,
                   "invocation": ref(invocation_path, "root_invocation_record"),
                   "observed_witness_returncode": 0, "receipt_commit_observed": True,
                   "receipt_phase_seconds": 4.0, "charged_output_bytes": charged,
                   "within_original_deadline": True, "within_publication_budget": True,
                   "ruling": ref(ruling_path, "markdown")}
    accepted = validate_completion(plan, terminal, publication, tmp_path.parent)
    assert accepted["campaign_seconds"] == terminal["campaign_seconds"] + 4.0
    assert accepted["selection"] == terminal["selection"]
    assert all(a["standalone_total_seconds"] == b["standalone_total_seconds"] + 4.0
               for a, b in zip(accepted["costs"], terminal["costs"]))
    from validation.kernel_stage_b.authority import AuthorityError
    scores_path = tmp_path / "scores.jsonl"
    original_scores = scores_path.read_bytes()
    changed_scores = original_scores.replace(b'"method":"jet:a"', b'"method":"jet:b"', 1)
    assert len(changed_scores) == len(original_scores) and changed_scores != original_scores
    scores_path.write_bytes(changed_scores)
    with pytest.raises(AuthorityError, match="reference bytes|raw score"):
        validate_completion(plan, terminal, publication, tmp_path.parent)
    scores_path.write_bytes(original_scores)
    for name in ("resolved-panel-config.json", "request-000.json", "reader-000.jsonl",
                 f"snapshot-jet-{entries[0]['episode_id']}.json"):
        path = tmp_path / name
        raw = path.read_bytes()
        path.write_bytes(b"[" + raw[1:])
        with pytest.raises(AuthorityError, match="reference bytes"):
            validate_completion(plan, terminal, publication, tmp_path.parent)
        path.write_bytes(raw)
    run_path = tmp_path / "stage-b.json"
    from validation.kernel_stage_b.authority import validate_run_evidence
    alias = tmp_path / "snapshots-copy.jsonl"
    alias.write_bytes((tmp_path / "snapshots.jsonl").read_bytes())
    aliased_run = json.loads(run_path.read_bytes())
    aliased_run["snapshots"]["path"] = alias.name
    with pytest.raises(AuthorityError, match="journal path"):
        validate_run_evidence(plan, aliased_run, tmp_path.parent)
    alias.unlink()
    wrong_count = json.loads(run_path.read_bytes())
    wrong_count["counts"]["requests_completed"] -= 1
    with pytest.raises(AuthorityError, match="Run full counts"):
        validate_run_evidence(plan, wrong_count, tmp_path.parent)
    rate_path = tmp_path / "jet-a-rates.json"
    rate_path.write_bytes(b"{}")
    with pytest.raises(AuthorityError, match="reference bytes"):
        validate_completion(plan, terminal, publication, tmp_path.parent)
    rate_path.write_bytes(b"[]")
    missing = json.loads(run_path.read_bytes())
    del missing["snapshots"]
    run_path.write_bytes(canonical(missing))
    assert finalize_terminal(plan, tmp_path.parent, witness)["status"] == "FAILED"
    assert json.loads((tmp_path / "monitor.json").read_bytes())["status"] == "COMPLETED"


@pytest.mark.parametrize("monitor_status,expected", [("COMPLETED", "PENDING_TERMINAL"),
                                                    ("STOPPED", "FAILED")])
def test_controlled_parent_binding_remains_provisional(tmp_path, monkeypatch,
                                                        monitor_status, expected):
    from validation.kernel_stage_b.__main__ import _parent

    out = tmp_path / "output"
    out.mkdir()
    plan_path = tmp_path / "plan.json"
    plan_path.write_bytes(b"{}")
    plan_hash = hashlib.sha256(b"{}").hexdigest()
    plan = {"execution": {"output": str(out), "preparation_output": None,
                          "boundary": {"deadline_monotonic": 10**20},
                          "limits": {"outer_seconds": 1000, "candidate_seconds": 1000,
                                     "output_bytes": 1000000, "incremental_bytes": 1000000,
                                     "free_disk_bytes": 0},
                          "launch": {"environment": {}, "argv": ["controlled"],
                                     "template_sha256": "0" * 64, "argv_sha256": "0" * 64},
                          "source_full_git": "0" * 40, "source_manifest": None},
            "release": {"scope": "binding"}}
    def controlled_supervise(*args, **kwargs):
        (out / "monitor.json").write_bytes(json.dumps({"status": monitor_status,
            "returncode": 0 if monitor_status == "COMPLETED" else 1}).encode())
        (out / "monitor-events.jsonl").write_bytes(
            json.dumps({"kind": "authority_start", "plan_file_sha256": plan_hash}).encode() + b"\n")
        (out / "monitor-evidence.jsonl").write_bytes(b"")
        (out / "binding-worker.json").write_bytes(json.dumps({"status": "PENDING_TERMINAL",
            "counts": dict(constructions=0, encodes=0, reads=0, factors=0, predictions=0)}).encode())
        return {"status": monitor_status, "returncode": 0 if monitor_status == "COMPLETED" else 1,
                "outer_seconds": 0.1}
    monkeypatch.setattr("validation.kernel_stage_a.monitor.supervise", controlled_supervise)
    code = _parent(plan, tmp_path, plan_path, plan_hash)
    report = json.loads((out / "binding-report.json").read_bytes())
    assert report["status"] == expected
    assert report["monitor"]["kind"] == "A_monitor"
    assert code == (0 if expected == "PENDING_TERMINAL" else 1)
    assert json.loads((out / "stage-b-external.json").read_bytes())["monitor_status"] == monitor_status


def test_controlled_worker_binding_constructs_no_backend(tmp_path, monkeypatch):
    from validation.kernel_stage_b.__main__ import _worker

    out = tmp_path / "output"
    out.mkdir()
    plan = {"execution": {"output": str(out)}, "release": {"scope": "binding"}}
    seen = []
    def controlled_verify(*args):
        seen.append("verified")
        return 10**20
    def controlled_baseline(*args, **kwargs):
        seen.append("baseline")
    monkeypatch.setattr("validation.kernel_stage_b.authority.verify_worker", controlled_verify)
    monkeypatch.setattr("validation.kernel_stage_a.monitor.record_baseline", controlled_baseline)
    import torch
    monkeypatch.setattr(torch, "set_num_threads", lambda _: None)
    monkeypatch.setattr(torch, "set_num_interop_threads", lambda _: None)
    assert _worker(plan, tmp_path) == 0
    assert seen == ["verified", "baseline"]
    record = json.loads((out / "binding-worker.json").read_bytes())
    assert record["status"] == "PENDING_TERMINAL"
    assert all(value == 0 for value in record["counts"].values())


@pytest.mark.parametrize("exit_code,expected", [(1, "FAILED"), (0, "ELIGIBLE_PENDING_PUBLICATION")])
def test_terminal_finalizer_requires_actual_parent_exit(tmp_path, monkeypatch, exit_code, expected):
    from validation.kernel_stage_b.__main__ import finalize_terminal
    from validation.kernel_stage_b.authority import canonical, digest
    from validation.kernel_stage_a.commands import vector_hash

    plan_path = tmp_path / "plan.json"
    out = tmp_path / "output"
    out.mkdir()
    source = tmp_path / "witness.py"
    source.write_bytes(b"# controlled witness\n")
    source_ref = {"kind": "python_source", "path": source.name,
                  "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                  "bytes": len(source.read_bytes())}
    parent_argv = ["python", "-I", "bootstrap", "--seal", str(plan_path)]
    plan = {"execution": {"output": str(out), "preparation_output": None,
                          "boundary": {"allocation_start_monotonic": 10.0,
                                       "deadline_monotonic": 100.0},
                          "limits": {"output_bytes": 1000000},
                          "launch": {"argv": ["python", "-I", "bootstrap", "--worker", "--seal", str(plan_path)]},
                          "terminal": {"publication_seconds": 20.0,
                                       "publication_bytes": 100000,
                                       "parent_argv": parent_argv,
                                       "parent_argv_sha256": vector_hash(parent_argv),
                                       "witness": source_ref}},
            "release": {"scope": "binding"}, "candidates": []}
    plan_path.write_bytes(canonical(plan))
    (out / "monitor.json").write_bytes(b'{"status":"COMPLETED","returncode":0}')
    (out / "binding-report.json").write_bytes(canonical({"version": 2, "status": "PENDING_TERMINAL",
        "plan_sha256": digest(plan), "failure": None}))
    monkeypatch.setattr("validation.kernel_stage_b.authority.validate_plan", lambda _: None)
    monkeypatch.setattr("validation.kernel_stage_b.__main__.time.monotonic", lambda: 50.0)
    witness = {"version": 1, "plan_sha256": digest(plan),
               "plan_file_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
               "witness": source_ref, "parent_argv": parent_argv,
               "parent_argv_sha256": vector_hash(parent_argv),
               "parent_invocations": 1, "parent_pid": 123,
               "launch_monotonic": 11.0, "reaped_monotonic": 20.0,
               "returncode": exit_code, "reaped": True}
    result = finalize_terminal(plan, tmp_path, witness)
    assert result["status"] == expected
    assert result["exit"]["returncode"] == exit_code
    assert result["selection"] == {"jet": None, "bank": None}
    terminal = json.loads((out / "terminal-report.json").read_bytes())
    assert terminal["status"] == expected
    assert terminal["campaign_seconds"] == 40.0
    assert terminal["intervals"] == [{"start": 10.0, "end": 50.0, "owner": "common",
                                     "operation": "binding_program",
                                     "status": "failed" if exit_code else "completed"}]
    if exit_code == 0:
        from validation.kernel_stage_b.authority import AuthorityError, validate_completion
        def ref(path, kind):
            raw = path.read_bytes()
            return {"kind": kind, "path": str(path.relative_to(tmp_path)),
                    "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        observed_bytes = sum(path.stat().st_size for path in out.rglob("*") if path.is_file())
        invocation = {"version": 1, "witness": source_ref, "plan_sha256": digest(plan),
                      "actual_returncode": 0, "publication_verified_monotonic": 60.0,
                      "output_bytes": observed_bytes, "commit_success": True}
        invocation_path = tmp_path / "invocation.json"
        invocation_path.write_bytes(canonical(invocation))
        ruling_path = tmp_path / "ruling.md"
        ruling_path.write_text("controlled root acceptance")
        publication = {"version": 1, "approved": True,
                       "terminal": ref(out / "terminal-report.json", "terminal_report"),
                       "witness": source_ref,
                       "invocation": ref(invocation_path, "root_invocation_record"),
                       "observed_witness_returncode": 0, "receipt_commit_observed": True,
                       "receipt_phase_seconds": 10.0, "charged_output_bytes": observed_bytes,
                       "within_original_deadline": True, "within_publication_budget": True,
                       "ruling": ref(ruling_path, "markdown")}
        accepted = validate_completion(plan, terminal, publication, tmp_path)
        assert accepted["campaign_seconds"] == 50.0
        assert accepted["costs"] == []
        with pytest.raises(AuthorityError, match="publication"):
            validate_completion(plan, terminal, None, tmp_path)
        bad = dict(publication, receipt_phase_seconds=9.0)
        with pytest.raises(AuthorityError, match="publication clock"):
            validate_completion(plan, terminal, bad, tmp_path)
        forged = dict(witness, parent_argv_sha256="0" * 64)
        with pytest.raises(AuthorityError, match="parent wait witness"):
            from validation.kernel_stage_b.authority import validate_exit_witness
            validate_exit_witness(plan, tmp_path, forged)
        from validation.kernel_stage_b import __main__ as launcher
        checked_commit = launcher._checked_commit
        late_failure = False
        def renamed_then_failed(path, value, execution, deadline):
            nonlocal late_failure
            receipt = checked_commit(path, value, execution, deadline)
            if path.name == "terminal-report.json" and not late_failure:
                late_failure = True
                raise OSError("controlled post-rename verification failure")
            return receipt
        monkeypatch.setattr(launcher, "_checked_commit", renamed_then_failed)
        failed = finalize_terminal(plan, tmp_path, witness)
        assert failed["status"] == "FAILED"
        assert late_failure
        assert json.loads((out / "terminal-report.json").read_bytes())["status"] == "FAILED"
        assert json.loads((out / "monitor.json").read_bytes())["status"] == "COMPLETED"
        binding_path = out / "binding-report.json"
        binding_record = json.loads(binding_path.read_bytes())
        binding_path.write_bytes(canonical(dict(binding_record, plan_sha256="0" * 64)))
        assert finalize_terminal(plan, tmp_path, witness)["status"] == "FAILED"


def test_allocation_cost_partition_rejects_gap_and_charges_common_time():
    from validation.kernel_stage_b.driver import terminal_costs

    candidates = [{"id": "jet:a", "family": "jet"}, {"id": "bank:b", "family": "bank"}]
    intervals = [{"start": 1.0, "end": 2.0, "owner": "common", "operation": "startup", "status": "completed"},
                 {"start": 2.0, "end": 4.0, "owner": "jet", "operation": "encode", "status": "completed"},
                 {"start": 4.0, "end": 5.0, "owner": "jet:a", "operation": "read", "status": "completed"},
                 {"start": 5.0, "end": 8.0, "owner": "common", "operation": "finalize", "status": "completed"}]
    costs = terminal_costs(candidates, intervals, {"jet:a"})
    assert costs[0]["standalone_total_seconds"] == 7.0
    assert costs[1]["standalone_total_seconds"] == 4.0
    with pytest.raises(ValueError, match="interval"):
        terminal_costs(candidates, [*intervals[:2], dict(intervals[2], start=4.1), intervals[3]], {"jet:a"})


def test_terminal_commit_reserves_old_target_temporary_and_deadline(tmp_path, monkeypatch):
    from validation.kernel_stage_b import __main__ as launcher
    from validation.kernel_stage_b.authority import canonical

    target = tmp_path / "terminal-report.json"
    target.write_bytes(b"old retained report")
    payload = {"version": 1, "status": "ELIGIBLE_PENDING_PUBLICATION"}
    old = target.read_bytes()
    execution = {"output": str(tmp_path), "preparation_output": None,
                 "limits": {"output_bytes": len(old) + len(canonical(payload)) - 1}}
    monkeypatch.setattr(launcher.time, "monotonic", lambda: 1.0)
    with pytest.raises(RuntimeError, match="cap"):
        launcher._checked_commit(target, payload, execution, 10.0)
    assert target.read_bytes() == old
    execution["limits"]["output_bytes"] += 1
    with pytest.raises(RuntimeError, match="clock"):
        launcher._checked_commit(target, payload, execution, 1.0)
    assert target.read_bytes() == old


def test_provisional_terminal_cannot_qualify_without_root_publication():
    from validation.kernel_stage_b.authority import AuthorityError, validate_completion

    with pytest.raises(AuthorityError):
        validate_completion({}, {"status": "ELIGIBLE_PENDING_PUBLICATION"}, None)
