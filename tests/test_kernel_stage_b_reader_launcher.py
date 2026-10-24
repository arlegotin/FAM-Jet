"""Reader launch gate regression using the real Stage A command builder."""

import hashlib
import json
from pathlib import Path
import time

import pytest
import torch

from famjet.data.synthetic import batch_hash
from famjet.eval.isolation import _reconstruct
from famjet.eval.state_io import snapshot_hash
from famjet.types import Episode, EventBatch, QueryBatch
from validation.kernel_stage_a import authority as stage_a_authority
from validation.kernel_stage_a import commands
from validation.kernel_stage_a import production as stage_a_production
from validation.kernel_stage_b.authority import AuthorityError
from validation.kernel_stage_b.production import Backend


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def reader_case(tmp_path):
    plan = json.loads((ROOT / "validation/kernel_stage_b/prospective-plan.json").read_bytes())
    candidate = next(c for c in plan["candidates"] if c["family"] == "jet")
    spec = json.loads((ROOT / candidate["static"]["path"]).read_bytes())
    model = _reconstruct(spec, freeze_rates=True)
    assert model.kernel.reference_tensor.dtype == torch.float64
    features = torch.zeros((1, 1, 16), dtype=torch.float64)
    features[0, 0, 0] = 1
    events = EventBatch(
        history_ids=("reader-launcher",), event_ids=torch.tensor([[1]]),
        timestamps=torch.tensor([[1]], dtype=torch.int64),
        key_ids=torch.tensor([[1]], dtype=torch.uint64), key_features=features,
        values=torch.ones((1, 1, 8), dtype=torch.float64),
        lengths=torch.tensor([1]), present=torch.tensor([[True]]),
        observed=torch.ones((1, 1, 8), dtype=torch.bool), time_unit="ticks",
    )
    with torch.no_grad():
        state = model.encode(events, mode="stream")
    queries = QueryBatch(
        history_ids=events.history_ids, query_ids=torch.tensor([[0]]),
        T=torch.tensor([[2]], dtype=torch.int64), key_ids=events.key_ids.clone(),
        key_features=features, tasks=(("mean",),),
        age_start=torch.zeros((1, 1), dtype=torch.float64),
        age_end=torch.ones((1, 1), dtype=torch.float64),
        present=torch.tensor([[True]]), lengths=torch.tensor([1]),
    )
    executable = Path(commands.sys.executable).resolve(strict=True)
    runtime = {"executable": str(executable),
               "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
               "process_image": {"path": str(executable), "sha256": "expected-image"}}
    backend = Backend.__new__(Backend)
    backend.plan = {"execution": {"runtime": runtime}}
    backend.root = ROOT
    backend.out = tmp_path
    backend.models = {candidate["id"]: model}
    backend.specs = {candidate["id"]: spec}
    backend.episodes = {"tiny": Episode(events, queries, torch.zeros((1, 1, 8)),
                                       torch.ones((1, 1), dtype=torch.bool))}
    backend.source_hash = "test-source"
    backend.candidate_deadline = time.monotonic() + 120
    backend.read_ordinal = 0
    backend.on_attempt = lambda ref: None
    entry = {"episode_id": "tiny", "query_ids": [0],
             "hashes": {"queries": batch_hash(queries)}}
    snapshot = {"state": state, "record": {"snapshot_hash": snapshot_hash(state)}}
    return backend, candidate, entry, snapshot


def test_real_reader_command_reaches_owned_dispatch_with_lexical_launcher(reader_case, monkeypatch):
    backend, candidate, entry, snapshot = reader_case
    expected = commands.reader_command(backend.root, backend.out / "monitor-events.jsonl",
                                       backend.candidate_deadline)
    assert len(expected) == 6
    assert expected[0] == str(ROOT / ".venv/bin/python")
    assert expected[1:3] == ["-I", "-c"]
    assert expected[-1] == repr(float(backend.candidate_deadline))
    seen = []

    class ReachedDispatch(Exception):
        pass

    def intercept(vector, **kwargs):
        seen.append(vector)
        assert vector == expected
        assert kwargs["deadline"] == backend.candidate_deadline
        assert kwargs["runtime_identity"] == backend.plan["execution"]["runtime"]
        witness = stage_a_authority.python_launch(vector, kwargs["runtime_identity"], "reader")
        assert witness["executable"] == expected[0]
        assert witness["launcher"] == {
            "path": str(Path(expected[0]).resolve(strict=True)),
            "sha256": hashlib.sha256(Path(expected[0]).read_bytes()).hexdigest(),
        }
        assert witness["expected_image"] == kwargs["runtime_identity"]["process_image"]
        raise ReachedDispatch

    monkeypatch.setattr(stage_a_production, "owned_reader_dispatch", intercept)
    with pytest.raises(ReachedDispatch):
        backend.read(candidate, entry, snapshot)
    assert seen == [expected]


@pytest.mark.parametrize("alternate", ["canonical", "other_symlink"])
def test_reader_rejects_nonproject_literal_argv0_before_dispatch(
        reader_case, monkeypatch, tmp_path, alternate):
    backend, candidate, entry, snapshot = reader_case
    canonical = backend.plan["execution"]["runtime"]["executable"]
    if alternate == "canonical":
        launcher = canonical
    else:
        other = tmp_path / "other-python"
        other.symlink_to(canonical)
        launcher = str(other)
    monkeypatch.setattr(commands.sys, "executable", launcher)
    monkeypatch.setattr(stage_a_production, "owned_reader_dispatch",
                        lambda *args, **kwargs: pytest.fail("reader dispatched"))
    with pytest.raises(ValueError, match="reader Python image mismatch"):
        backend.read(candidate, entry, snapshot)


@pytest.mark.parametrize("wrong", ["target", "hash"])
def test_reader_rejects_wrong_canonical_identity_before_dispatch(
        reader_case, monkeypatch, wrong):
    backend, candidate, entry, snapshot = reader_case
    runtime = backend.plan["execution"]["runtime"]
    if wrong == "target":
        runtime["executable"] = str(backend.out / "different-python")
    else:
        runtime["executable_sha256"] = "0" * 64
    monkeypatch.setattr(stage_a_production, "owned_reader_dispatch",
                        lambda *args, **kwargs: pytest.fail("reader dispatched"))
    with pytest.raises(AuthorityError, match="project launcher target"):
        backend.read(candidate, entry, snapshot)
