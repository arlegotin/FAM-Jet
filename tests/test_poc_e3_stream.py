from dataclasses import replace

import torch

from famjet.eval.metrics import fit_target_statistics
from famjet.eval.state_io import snapshot_hash
from famjet.memory.buckets import TemporalBucketsMemory
from famjet.memory.exact_store import PackedHistoryMemory
from famjet.memory.reservoir import ReservoirMemory
from famjet_poc.contracts import PopulationSpec, ReaderSpec, ShapeSpec
from famjet_poc.data import generate_episode
from famjet_poc.models import build_model


def _episode():
    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'unit_test', 318,
                          (128,), ('piecewise_stationary',), 8, 512)
    ep = generate_episode(spec, 'unit-stream-chunk-0')
    times = ep.events.timestamps.clone()
    times[0, 10] = times[0, 9]
    observed = ep.events.observed.clone()
    observed[0, 11] = False
    return replace(ep, events=replace(ep.events, timestamps=times, observed=observed))


def _one_event_state(method, ep):
    state = None
    events = ep.events
    for i in range(int(events.lengths[0])):
        event = replace(events, **{name: getattr(events, name)[:, i:i+1] for name in
                                 ('event_ids', 'timestamps', 'key_ids', 'key_features', 'values', 'present', 'observed')},
                        lengths=torch.ones_like(events.lengths))
        state = method.encode(event, state, mode='stream')
    return state


def test_chunk128_stream_matches_single_event_state_ids_bytes_and_predictions():
    from famjet_poc.study import _stream_snapshot

    ep = _episode()
    stats = fit_target_statistics([replace(ep, metadata={**ep.metadata, 'split': 'training'})])
    methods = {}
    for family in ('jet', 'bank'):
        reader = ReaderSpec('ridge_v1', family, 8, 1e-6, 1 / 5224, 1., 1e-6, 1e-12)
        methods[family] = build_model(ShapeSpec(12, 1), reader, 1., stats)
    methods.update(exact=PackedHistoryMemory(None, 1, 'exact', key_dim=12),
                   recent=PackedHistoryMemory(16, 1, 'recent', key_dim=12),
                   latest_lru=PackedHistoryMemory(16, 1, 'latest_lru', key_dim=12),
                   reservoir=ReservoirMemory(16, 1, 41, key_dim=12),
                   buckets=TemporalBucketsMemory(16, 1, key_dim=12, normalization='shared'))
    for name, method in methods.items():
        expected = _one_event_state(method, ep)
        actual, trigger, nbytes, audit = _stream_snapshot(method, ep, chunk_size=128, return_audit=True)
        assert trigger is None, name
        assert snapshot_hash(actual) == snapshot_hash(expected), name
        assert method.persistent_nbytes(actual) == method.persistent_nbytes(expected) == nbytes, name
        assert actual.event_offset.tolist() == expected.event_offset.tolist() == [128]
        assert audit['chunk_count'] == 1 and audit['replay_count'] == 0
        got = method.read(actual, ep.queries)
        want = method.read(expected, ep.queries)
        assert torch.equal(got.prediction.contiguous().view(torch.int64),
                           want.prediction.contiguous().view(torch.int64)), name


def test_bad_chunk_replays_from_checkpoint_to_first_nonfinite_event():
    from famjet_poc.study import _stream_snapshot

    ep = _episode()
    values = ep.events.values.clone()
    keys = ep.events.key_features.clone()
    key_ids = ep.events.key_ids.clone()
    values[0, 3, 0] = 1e308
    values[0, 4, 0] = 1e308
    keys[0, 4] = keys[0, 3]
    key_ids[0, 4] = key_ids[0, 3]
    ep = replace(ep, events=replace(ep.events, values=values, key_features=keys, key_ids=key_ids))
    stats = fit_target_statistics([replace(_episode(), metadata={**ep.metadata, 'split': 'training'})])
    reader = ReaderSpec('ridge_v1', 'jet', 8, 1e-6, 1 / 5224, 1., 1e-6, 1e-12)
    model = build_model(ShapeSpec(12, 1), reader, 1., stats)
    _, trigger, _, audit = _stream_snapshot(model, ep, chunk_size=128, return_audit=True)
    assert trigger['event_offset'] == 5
    assert trigger['reason'] == 'nonfinite_stored_state'
    assert audit['replay_count'] == 1 and audit['replayed_events'] == 5
