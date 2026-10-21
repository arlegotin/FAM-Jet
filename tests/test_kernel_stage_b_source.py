"""Source-only checks for the unreleased Stage B adapter."""
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_null_plan_refuses_before_backend_import(monkeypatch, capsys):
    """Replacing the null gate with a permissive branch would reach production."""
    import sys
    from validation.kernel_stage_b.__main__ import main

    sys.modules.pop("validation.kernel_stage_b.production", None)
    code = main(["--seal", str(ROOT / "validation/kernel_stage_b/prospective-plan.json")])
    assert code == 2
    assert "REFUSED" in capsys.readouterr().err
    assert "validation.kernel_stage_b.production" not in sys.modules


def test_help_needs_no_scientific_import(capsys):
    """A help path that imports production would violate prelaunch refusal."""
    import sys
    from validation.kernel_stage_b.__main__ import main

    sys.modules.pop("validation.kernel_stage_b.production", None)
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "--seal" in capsys.readouterr().out
    assert "validation.kernel_stage_b.production" not in sys.modules


def test_canonical_hash_uses_unicode_and_strict_json():
    """Changing Unicode encoding or accepting NaN changes release identities."""
    from validation.kernel_stage_b.authority import canonical, digest

    assert canonical({"é": [1, "β"]}) == b'{"\xc3\xa9":[1,"\xce\xb2"]}'
    assert digest({"é": [1, "β"]}) == hashlib.sha256(b'{"\xc3\xa9":[1,"\xce\xb2"]}').hexdigest()
    with pytest.raises((ValueError, TypeError)):
        canonical({"x": float("nan")})
    with pytest.raises((ValueError, TypeError)):
        canonical({1: "coerced-key"})


@pytest.mark.parametrize("scope", ["feasibility", "subset", "Q1"])
def test_unsupported_scope_refuses(scope):
    """Broadening release scope must not admit an unclosed experiment."""
    from validation.kernel_stage_b.authority import AuthorityError, validate_plan

    plan = json.loads((ROOT / "validation/kernel_stage_b/prospective-plan.json").read_text())
    plan["release"] = {"approved": True, "scope": scope, "payload_sha256": "0" * 64,
                       "ruling": {"kind": "markdown", "path": "x", "sha256": "0" * 64, "bytes": 1}}
    with pytest.raises(AuthorityError, match="unsupported release scope"):
        validate_plan(plan)


def test_verified_ref_rejects_path_escape_and_changed_bytes(tmp_path):
    """Trusting a declared SHA without containment or byte verification is unsafe."""
    from validation.kernel_stage_b.authority import AuthorityError, read_verified

    inside = tmp_path / "safe.json"
    inside.write_bytes(b"{}")
    ref = {"kind": "json", "path": "safe.json", "sha256": hashlib.sha256(b"{}").hexdigest(), "bytes": 2}
    assert read_verified(tmp_path, ref) == b"{}"
    with pytest.raises(AuthorityError):
        read_verified(tmp_path, dict(ref, path="../outside.json"))
    inside.write_bytes(b"[]")
    with pytest.raises(AuthorityError):
        read_verified(tmp_path, ref)


def test_length_composition_keeps_undefined_and_infinite_evidence():
    """Changing precedence or averaging by query count would select a wrong candidate."""
    from validation.kernel_stage_b.driver import combine_lengths

    summaries = [(128, {"status": "ok", "loss": 3., "infinite_loss_count": 0, "query_count": 8}),
                 (512, {"status": "ok", "loss": 6., "infinite_loss_count": 0, "query_count": 80}),
                 (2048, {"status": "ok", "loss": 9., "infinite_loss_count": 0, "query_count": 800})]
    assert combine_lengths("jet:x", summaries, True)["loss"] == 6.
    summaries[1][1].update(status="infinite_loss", loss=None, infinite_loss_count=1)
    assert combine_lengths("jet:x", summaries, True)["status"] == "infinite_loss"
    summaries[2][1].update(status="undefined_loss", loss=None)
    result = combine_lengths("jet:x", summaries, True)
    assert result["status"] == "undefined_loss"
    assert result["has_infinite"] and result["has_undefined"]
    assert result["query_count"] == 888


def test_exact_tie_uses_standalone_cost_then_config_hash():
    """A missing cost or hash tiebreak changes the selected family member."""
    from validation.kernel_stage_b.driver import select_family

    combined = [dict(candidate="jet:a", status="ok", loss=1., complete=True),
                dict(candidate="jet:b", status="ok", loss=1., complete=True),
                dict(candidate="bank:c", status="ok", loss=0.5, complete=True)]
    costs = [dict(candidate="jet:a", standalone_total_seconds=3.),
             dict(candidate="jet:b", standalone_total_seconds=2.),
             dict(candidate="bank:c", standalone_total_seconds=9.)]
    hashes = {"jet:a": "f" * 64, "jet:b": "0" * 64, "bank:c": "1" * 64}
    assert select_family("jet", combined, costs, hashes) == "jet:b"
    costs[0]["standalone_total_seconds"] = 2.
    assert select_family("jet", combined, costs, hashes) == "jet:b"
    combined[1]["status"] = "infinite_loss"
    assert select_family("jet", combined, costs, hashes) == "jet:a"


def test_reader_response_rejects_extra_fields_and_preserves_null():
    """A permissive decoder could reinterpret a malformed or unsupported read."""
    from validation.kernel_stage_b.production import decode_response

    numeric = {"prediction": [[[None] * 8 for _ in range(8)]], "logits": None, "schema_version": 1,
               "support": [[None] * 8], "failure": [[True] * 8],
               "diagnostics": {name: [[False] * 8] for name in
                               ("numerical_eligible", "prediction_valid", "numeric_supported",
                                "factual_support_available", "quarantined")}}
    numeric["diagnostics"].update(failure_code=[[[1, 0] for _ in range(8)]],
                                  reconstructed_mass=[[[None, None] for _ in range(8)]],
                                  cancellation_bound=[[[None, None] for _ in range(8)]])
    response = {"numeric": numeric, "counts": {"read": 1}, "windows": [],
                "coefficients": [], "window_vectors": [], "seconds": 0.1}
    assert decode_response(response)["numeric"]["prediction"][0][0][0] is None
    with pytest.raises(ValueError):
        decode_response(dict(response, invented=True))
    with pytest.raises(ValueError):
        decode_response(dict(response, counts={"read": 1, "factor": 1}))


def test_panel_config_changes_only_the_closed_generator_fields():
    """A replacement of model/training/resource fields would change historical inputs."""
    from dataclasses import asdict
    from famjet.config import load_config
    from validation.kernel_stage_b.production import panel_config_for_entry

    base = load_config(ROOT / "configs/development/jet_finite_raw_32768.yaml")
    manifest = json.loads((ROOT / "artifacts/task18/finite-nested96/manifest.json").read_text())
    from validation.kernel_stage_b.authority import _manifest
    _manifest(manifest)
    assert asdict(base.data) == manifest["data"]
    assert base.development.data_seed == 20261017018
    entry = {"length": 512, "regime": "trend_reset"}
    actual = asdict(panel_config_for_entry(base, entry))
    expected = asdict(base)
    expected["development"]["eval_histories_per_cell"] = 8
    expected["data"]["length"] = 512
    expected["data"]["generator"]["namespace"] = "development_fit"
    expected["data"]["generator"]["regime"] = "trend_reset"
    assert actual == expected


def test_quarantined_q8_uses_central_training_fallback_without_read():
    """Replacing central scoring with fabricated fallback rows would lose flags."""
    import torch
    from types import SimpleNamespace
    from famjet.types import QueryBatch
    from famjet.eval.runner import episode_policy
    from validation.kernel_stage_b.production import score_numeric

    h = "controlled-history"
    q = QueryBatch((h,), torch.arange(8, dtype=torch.int64)[None],
                   torch.ones((1, 8), dtype=torch.float64),
                   torch.zeros((1, 8), dtype=torch.int64),
                   torch.zeros((1, 8, 16), dtype=torch.float64),
                   (("mean", "contrast") * 4,),
                   torch.zeros((1, 8), dtype=torch.float64),
                   torch.ones((1, 8), dtype=torch.float64),
                   torch.ones((1, 8), dtype=torch.bool), torch.tensor([8]))
    ep = SimpleNamespace(queries=q, labels=torch.zeros((1, 8, 8), dtype=torch.float64),
                         supported=torch.ones((1, 8), dtype=torch.bool),
                         metadata={"regime": "trend_reset", "target_valid": [[True] * 8],
                                   "target_semantics": "observed_event_targets_v2", "population": "primary"})
    policy = episode_policy([ep])
    stats = json.loads((ROOT / "validation/kernel_stage_a/frozen-training-metadata.json").read_text())["jet"]["target_statistics"]
    trigger = {"reason": "nonfinite_stored_state"}
    rows = score_numeric("jet:controlled", ep, stats, policy, "0" * 64, None, trigger)
    assert len(rows) == 8
    assert all(row["quarantined"] and row["failure"] and row["fallback"] for row in rows)
    assert all(row["quarantine_trigger"] == trigger for row in rows)
    assert rows[0]["prediction"] == stats["tasks"]["mean"]["mean"]


def test_transport_stop_preserves_attempt_and_does_not_score(tmp_path):
    """Inventing fallback after a failed reader would make incomplete work selectable."""
    from validation.kernel_stage_b.driver import execute

    ids = [("jet", "a"), ("bank", "a"), ("bank", "b"),
           ("jet", "b"), ("jet", "c"), ("bank", "c")]
    candidates = [dict(id=f"{f}:{r}", family=f, config_sha256="0" * 64) for f, r in ids]
    entries = [dict(episode_id=f"controlled-{i}", query_ids=list(range(8)), length=128)
               for i in range(96)]
    class FailingBackend:
        def prepare(self):
            return dict(entries=entries, resolved_panel_config=None)
        def encode(self, family, entry):
            return dict(record=dict(version=1, family=family, history_id=entry["episode_id"],
                                    snapshot_hash="0" * 64, trigger=None))
        def read(self, candidate, entry, snapshot):
            request_path = tmp_path / "request-000.json"
            request_path.write_bytes(b"{}")
            self.on_attempt({"kind": "request", "path": request_path.name,
                             "sha256": hashlib.sha256(b"{}").hexdigest(), "bytes": 2})
            raise RuntimeError("controlled transport failure")
        def score(self, candidate, entry, numeric, trigger):
            pytest.fail("failed transport must not be scored")
    plan = {"execution": {"output": str(tmp_path),
                           "boundary": {"deadline_monotonic": 10**20},
                           "limits": {"candidate_seconds": 1000}, "source_manifest": None},
            "candidates": candidates}
    result = execute(plan, FailingBackend(), lambda: None)
    assert result["status"] == "INFRA_STOP"
    assert result["failure"]["phase"] == "transport"
    assert result["counts"]["requests_attempted"] == 1
    assert result["counts"]["predictions_scored"] == 0
    assert len(result["failure"]["remaining"]) == 576
    assert result["selection"] == {"jet": None, "bank": None}
    assert result["failure"]["raw"]
    for ref in result["failure"]["raw"]:
        raw = (tmp_path / ref["path"]).read_bytes()
        assert len(raw) == ref["bytes"]
        assert hashlib.sha256(raw).hexdigest() == ref["sha256"]


def test_archived_reader_stream_requires_one_final_result():
    """A trailing result or missing counter would falsify the raw A proof."""
    from validation.kernel_stage_b.authority import parse_reader_stream, AuthorityError

    numeric = {"prediction": [[[0.] * 8]], "logits": None, "support": [[None]],
               "failure": [[False]], "schema_version": 1,
               "diagnostics": {name: [[False]] for name in
                               ("numerical_eligible", "prediction_valid", "numeric_supported",
                                "factual_support_available", "quarantined")}}
    numeric["diagnostics"].update(failure_code=[[[0, 0]]],
                                  reconstructed_mass=[[[None, None]]],
                                  cancellation_bound=[[[None, None]]])
    result = {"numeric": numeric, "counts": {"read": 1}, "windows": [],
              "coefficients": [], "window_vectors": [], "seconds": 0.1}
    raw = b'{"counter":"read"}\n' + json.dumps(result).encode()
    assert parse_reader_stream(raw)["counts"] == {"read": 1}
    with pytest.raises(AuthorityError):
        parse_reader_stream(raw + b'\n' + json.dumps(result).encode())


def test_q8_window_trace_follows_query_order_and_early_returns():
    """An extra or reordered window could attach arithmetic to the wrong query."""
    from validation.kernel_stage_b.production import validate_window_order

    diagnostics = {"failure_code": [[[5, 0] for _ in range(8)]],
                   "quarantined": [[False] * 8],
                   "reconstructed_mass": [[[None, None] for _ in range(8)]],
                   "cancellation_bound": [[[None, None] for _ in range(8)]]}
    response = {"numeric": {"diagnostics": diagnostics}, "windows": []}
    validate_window_order(response, ("mean",) * 8, False)
    response["windows"] = [{"code": 5}]
    with pytest.raises(ValueError):
        validate_window_order(response, ("mean",) * 8, False)


def test_prospective_inventory_keeps_all_slots_and_failures():
    """Dropping a hard source-failure slot would narrow the future panel authority."""
    from validation.kernel_stage_b.authority import FAMILIES
    from validation.kernel_stage_a.descriptors import slots

    plan = json.loads((ROOT / "validation/kernel_stage_b/prospective-plan.json").read_text())
    listed = plan["evidence"]["slots"]
    expected = [(f + ":" + r, s.row, s.transform, s.applicable)
                for f, r in FAMILIES for s in slots()]
    assert len(listed) == len(expected) == 768
    assert [(v["candidate"], v["row"], v["transform"], v["ordinal"] is not None)
            for v in listed] == expected
    assert [v["ordinal"] for v in listed if v["ordinal"] is not None] == list(range(744))
    assert sum(v["row"] == 30 for v in listed) == 24
    stage = json.loads((ROOT / plan["evidence"]["inventory"]["path"]).read_text())
    failed = [v for v in stage["inventory"] if v.get("outcome", {}).get("source_state_fidelity") == "FAILED"]
    assert len(failed) == 24
    assert all(v["row"] == 30 for v in failed)
    assert plan["approval"] is plan["execution"] is plan["release"] is None


def test_current_source_manifest_is_byte_bound():
    """A stale source hash must block a later release even when tests pass."""
    from validation.kernel_stage_b.authority import read_verified, strict_json

    plan = json.loads((ROOT / "validation/kernel_stage_b/prospective-plan.json").read_text())
    rows = strict_json(read_verified(ROOT, plan["evidence"]["source"]))
    mapped = {row["path"]: row for row in rows}
    for path in (ROOT / "validation/kernel_stage_b").glob("*.py"):
        relative = str(path.relative_to(ROOT))
        assert mapped[relative]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_archived_single_reader_schema_matches_raw_detail():
    """A real archived wire record catches a source/role schema mismatch."""
    from validation.kernel_stage_b.authority import _role_shape, parse_reader_stream

    archive = ROOT / "docs/research/task18-kernel-stage-a06-evidence/stage-a"
    detail = json.loads((archive / "result-jet-0x1.b7cdfd9d7bdbbp-34-02-I.json").read_text())
    stream = parse_reader_stream((archive / "reader-001.jsonl").read_bytes())
    _role_shape(detail["P"], False)
    _role_shape(detail["A"], True)
    _role_shape(detail["B"], True)
    assert detail["P"]["prediction"] == stream["numeric"]["prediction"][0][0]
