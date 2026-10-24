"""Real fixed-writer regression for the Stage B external input boundary."""

from dataclasses import replace
import json
from pathlib import Path
import time

import pytest
import torch

from famjet.data.synthetic import batch_hash
from famjet.eval.isolation import _query_from_record, _reconstruct
from famjet.eval.state_io import snapshot_hash
from famjet.types import Episode, EventBatch, QueryBatch
from validation.kernel_stage_b.production import Backend


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("family", ["jet", "bank"])
def test_external_encode_promotes_only_writer_floats_and_matches_real_writer(family, tmp_path):
    """Passing the original FP32 event slice to an FP64 writer must fail this test."""
    plan = json.loads((ROOT / "validation/kernel_stage_b/prospective-plan.json").read_bytes())
    candidate = next(c for c in plan["candidates"] if c["family"] == family)
    spec = json.loads((ROOT / candidate["static"]["path"]).read_bytes())
    model = _reconstruct(spec, freeze_rates=True)
    assert model.kernel.rates.dtype == torch.float64
    assert model.kernel.rates.device.type == "cpu"

    first_time = 2**53 + 1
    keys = torch.zeros((1, 3, 16), dtype=torch.float32)
    keys[0, 0, 0] = 1
    keys[0, 1, 1] = 1
    keys[0, 2, 2] = 1
    values = torch.tensor([[[1.25] * 8, [9.0] * 8, [-2.5] * 8]], dtype=torch.float32)
    events = EventBatch(
        history_ids=("tiny-dtype-history",),
        event_ids=torch.tensor([[4, 5, 8]], dtype=torch.int64),
        timestamps=torch.tensor([[first_time, first_time + 1, first_time + 2]], dtype=torch.int64),
        key_ids=torch.tensor([[2**63 + 3, 2**63 + 5, 2**63 + 7]], dtype=torch.uint64),
        key_features=keys, values=values, lengths=torch.tensor([3]),
        present=torch.tensor([[True, True, True]]),
        observed=torch.tensor([[[True] * 8, [False] * 8, [True] * 8]]),
        time_unit="ticks", auxiliary={"gate": torch.tensor([[1.0, 0.5, 0.75]])},
    )
    queries = QueryBatch(
        history_ids=events.history_ids, query_ids=torch.tensor([[0]]),
        T=torch.tensor([[first_time + 3]], dtype=torch.int64),
        key_ids=torch.tensor([[2**63 + 3]], dtype=torch.uint64),
        key_features=keys[:, :1], tasks=(("mean",),),
        age_start=torch.zeros((1, 1), dtype=torch.float64),
        age_end=torch.ones((1, 1), dtype=torch.float64),
        present=torch.tensor([[True]]), lengths=torch.tensor([1]),
    )
    raw_hash = batch_hash(events)
    raw_fields = {name: getattr(events, name).clone() for name in
                  ("event_ids", "timestamps", "key_ids", "key_features", "values",
                   "lengths", "present", "observed")}
    raw_gate = events.auxiliary["gate"].clone()

    backend = Backend.__new__(Backend)
    backend.plan = plan
    backend.out = tmp_path
    backend.models = {candidate["id"]: model}
    backend.episodes = {"tiny": Episode(events, queries, torch.zeros((1, 1, 8)),
                                       torch.ones((1, 1), dtype=torch.bool))}
    actual = backend.encode(family, {"episode_id": "tiny"})["state"]

    typed = replace(events, key_features=keys.to(torch.float64), values=values.to(torch.float64))
    expected = None
    with torch.no_grad():
        for offset in range(3):
            item = replace(typed, **{name: getattr(typed, name)[:, offset:offset + 1]
                                     for name in ("event_ids", "timestamps", "key_ids",
                                                  "key_features", "values", "present", "observed")},
                           lengths=torch.ones_like(typed.lengths),
                           auxiliary={"gate": typed.auxiliary["gate"][:, offset:offset + 1]})
            expected = model.encode(item, expected, mode="stream")
    assert snapshot_hash(actual) == snapshot_hash(expected)
    assert actual.event_offset.tolist() == [3]
    assert actual.last_time.dtype == torch.int64
    assert actual.last_time.tolist() == [first_time + 2]
    assert batch_hash(events) == raw_hash
    for name, before in raw_fields.items():
        assert torch.equal(getattr(events, name), before)
    assert torch.equal(events.auxiliary["gate"], raw_gate)
    assert events.key_features.dtype == events.values.dtype == torch.float32
    assert events.timestamps.dtype == torch.int64
    assert events.key_ids.dtype == torch.uint64


@pytest.mark.parametrize("family", ["jet", "bank"])
def test_external_read_request_types_query_features_for_fp64_state(family, tmp_path, monkeypatch):
    """Serializing raw FP32 query features would fail the real reader contract."""
    from validation.kernel_stage_a import commands
    from validation.kernel_stage_a import production as stage_a_production
    from validation.kernel_stage_b import authority

    plan = json.loads((ROOT / "validation/kernel_stage_b/prospective-plan.json").read_bytes())
    candidate = next(c for c in plan["candidates"] if c["family"] == family)
    spec = json.loads((ROOT / candidate["static"]["path"]).read_bytes())
    model = _reconstruct(spec, freeze_rates=True)
    key = torch.zeros((1, 1, 16), dtype=torch.float32)
    key[0, 0, 0] = 1
    events = EventBatch(
        history_ids=("tiny-query-history",), event_ids=torch.tensor([[7]]),
        timestamps=torch.tensor([[2**53 + 1]], dtype=torch.int64),
        key_ids=torch.tensor([[2**63 + 9]], dtype=torch.uint64),
        key_features=key, values=torch.ones((1, 1, 8), dtype=torch.float32),
        lengths=torch.tensor([1]), present=torch.tensor([[True]]),
        observed=torch.ones((1, 1, 8), dtype=torch.bool), time_unit="ticks",
    )
    typed = replace(events, key_features=key.to(torch.float64),
                    values=events.values.to(torch.float64))
    with torch.no_grad():
        state = model.encode(typed, mode="stream")
    queries = QueryBatch(
        history_ids=events.history_ids, query_ids=torch.tensor([[0]]),
        T=torch.tensor([[2**53 + 2]], dtype=torch.int64),
        key_ids=events.key_ids.clone(), key_features=key,
        tasks=(("mean",),), age_start=torch.zeros((1, 1), dtype=torch.float64),
        age_end=torch.ones((1, 1), dtype=torch.float64),
        present=torch.tensor([[True]]), lengths=torch.tensor([1]),
    )
    with pytest.raises(ValueError, match="query features must be nonnegative on state device/dtype"):
        model.kernel.features(state, queries)
    query_hash = batch_hash(queries)

    class ReachedDispatch(Exception):
        pass

    monkeypatch.setattr(commands, "reader_command", lambda *args: ["python"])
    monkeypatch.setattr(authority, "project_launcher", lambda root, runtime: "python")
    monkeypatch.setattr(stage_a_production, "owned_reader_dispatch",
                        lambda *args, **kwargs: (_ for _ in ()).throw(ReachedDispatch()))
    backend = Backend.__new__(Backend)
    backend.plan = {"execution": {"runtime": {"executable": "python"}}}
    backend.root = ROOT
    backend.out = tmp_path
    backend.models = {candidate["id"]: model}
    backend.specs = {candidate["id"]: spec}
    backend.episodes = {"tiny": Episode(events, queries, torch.zeros((1, 1, 8)),
                                       torch.ones((1, 1), dtype=torch.bool))}
    backend.source_hash = "test-source"
    backend.candidate_deadline = time.monotonic() + 30
    backend.read_ordinal = 0
    backend.on_attempt = lambda ref: None
    snapshot = {"state": state, "record": {"snapshot_hash": snapshot_hash(state)}}
    with pytest.raises(ReachedDispatch):
        backend.read(candidate, {"episode_id": "tiny", "query_ids": [0],
                                 "hashes": {"queries": query_hash}}, snapshot)
    request = json.loads((tmp_path / "request-000.json").read_bytes())
    assert request["queries"]["key_features"]["dtype"] == "float64"
    assert request["queries"]["T"]["dtype"] == "int64"
    assert request["queries"]["key_ids"]["dtype"] == "uint64"
    typed_queries = _query_from_record(request["queries"])
    assert typed_queries.T.tolist() == [[2**53 + 2]]
    assert typed_queries.key_ids.tolist() == [[2**63 + 9]]
    assert typed_queries.present.tolist() == [[True]]
    with torch.no_grad():
        model.kernel.features(state, typed_queries)
    assert batch_hash(queries) == query_hash
    assert queries.key_features.dtype == torch.float32
