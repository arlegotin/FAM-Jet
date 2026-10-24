from dataclasses import replace
import copy

import pytest
import torch

from famjet.types import EventBatch, QueryBatch
from validation.reader_adequacy_v1 import (
    ReaderSpec, PrimaryReader, features, load_pinned_kernel, make_two_age_fixture,
)


def tiny_case(family):
    kernel = load_pinned_kernel(family)
    key = torch.nn.functional.one_hot(torch.tensor([[3]]), 16).to(torch.float64)
    events = EventBatch(('tiny',), torch.tensor([[0]]), torch.tensor([[0.]], dtype=torch.float64),
                        torch.tensor([[3]]), key, torch.arange(1., 9., dtype=torch.float64).reshape(1, 1, 8),
                        torch.tensor([1]), torch.tensor([[True]]), torch.ones(1, 1, 8, dtype=torch.bool), 's')
    snapshot = kernel.encode(events)
    queries = QueryBatch(('tiny',), torch.tensor([[0, 1]]), torch.zeros(1, 2, dtype=torch.float64),
                         torch.tensor([[3, 0]]), torch.cat((key, torch.zeros_like(key)), 1),
                         (('mean', 'contrast'),), torch.zeros(1, 2, dtype=torch.float64),
                         torch.ones(1, 2, dtype=torch.float64), torch.tensor([[True, False]]), torch.tensor([1]))
    return kernel, snapshot, queries


@pytest.mark.parametrize('family', ['jet', 'bank'])
@pytest.mark.parametrize('access,width,d,params,macs', [
    ('C', 128, 92, 29448, 29184), ('C', 558, 92, 368288, 367164),
    ('F', 256, 1172, 368136, 367616),
])
def test_primary_ledger_matches_real_module(family, access, width, d, params, macs):
    spec = ReaderSpec(family, access, width)
    reader = PrimaryReader(spec)
    assert (spec.input_dim, spec.parameter_count, spec.dense_macs) == (d, params, macs)
    assert sum(p.numel() for p in reader.parameters()) == params
    assert all(p.dtype == torch.float64 and p.device.type == 'cpu' for p in reader.parameters())


def test_spec_rejects_unsupported_arms():
    for fields in [('jet', 'F', 128), ('bank', 'C', 256), ('other', 'C', 128)]:
        with pytest.raises(ValueError): ReaderSpec(*fields)


@pytest.mark.parametrize('family', ['jet', 'bank'])
def test_contracted_order_support_mask_and_immutability(family):
    kernel, snapshot, queries = tiny_case(family)
    before = {k: v.clone() for k, v in snapshot.payload.items()}
    before_query = queries.key_features.clone()
    batch = features(kernel, snapshot, queries, ReaderSpec(family, 'C', 128))
    assert batch.values.shape == (1, 2, 92)
    assert batch.values.dtype == torch.float64
    assert batch.supported.tolist() == [[True, False]]
    anchor = torch.cat((torch.arange(1., 9., dtype=torch.float64),
                        torch.zeros(8, dtype=torch.float64), torch.ones(1, dtype=torch.float64),
                        torch.zeros(1, dtype=torch.float64))) if family == 'jet' else torch.cat((
                        torch.arange(1., 9., dtype=torch.float64), torch.ones(1, dtype=torch.float64)))
    assert torch.equal(batch.values[0, 0, :anchor.numel()], anchor)
    assert torch.equal(batch.values[0, 0, -20:-4], queries.key_features[0, 0])
    assert batch.values[0, 0, -4:].tolist() == [1., 0., 0., 1.]
    assert all(torch.equal(snapshot.payload[k], v) for k, v in before.items())
    assert torch.equal(queries.key_features, before_query)


def test_full_order_and_invalid_task():
    kernel, snapshot, queries = tiny_case('jet')
    batch = features(kernel, snapshot, queries, ReaderSpec('jet', 'F', 256))
    assert batch.values.shape == (1, 2, 1172)
    assert batch.values[0, 0, 3 * 9:3 * 9 + 9].tolist() == list(range(1, 9)) + [1.]
    assert torch.count_nonzero(batch.values[0, 0, 576:1152]) == 0
    bad = replace(queries, tasks=(('latest', 'contrast'),))
    with pytest.raises(ValueError): features(kernel, snapshot, bad, ReaderSpec('jet', 'F', 256))


def test_reader_static_roundtrip_and_rejection():
    kernel, snapshot, queries = tiny_case('bank')
    reader = PrimaryReader(ReaderSpec('bank', 'C', 128))
    before = reader.read(kernel, snapshot, queries)
    static = reader.export_static()
    assert len(static['source']['reader_source_sha256']) == 64
    restored = PrimaryReader.from_static(static)
    after = restored.read(kernel, snapshot, queries)
    assert torch.equal(before.prediction, after.prediction)
    assert after.failure.tolist() == [[False, False]]
    assert after.diagnostics['prediction_valid'].tolist() == [[True, False]]
    assert after.support.tolist() == [[1., 0.]]
    for tamper in ('writer_hash', 'target_hash'):
        corrupt = copy.deepcopy(static)
        corrupt['source'][tamper] = '0' * 64
        with pytest.raises(ValueError): PrimaryReader.from_static(corrupt)
    corrupt = copy.deepcopy(static)
    corrupt['weights']['network.0.weight']['dtype'] = 'float32'
    with pytest.raises(ValueError): PrimaryReader.from_static(corrupt)


def test_training_statistics_small_exact_and_development_rejected():
    reader = PrimaryReader(ReaderSpec('bank', 'C', 128))
    rows = ({'split': 'training', 'values': torch.stack((torch.zeros(92, dtype=torch.float64),
             torch.full((92,), 2., dtype=torch.float64))), 'supported': torch.tensor([True, True])},)
    mean, scale = reader.fit_feature_statistics(rows)
    assert torch.equal(mean, torch.ones(92, dtype=torch.float64))
    assert torch.equal(scale, torch.ones(92, dtype=torch.float64))
    with pytest.raises(ValueError): reader.fit_feature_statistics(rows)
    with pytest.raises(ValueError): PrimaryReader(ReaderSpec('bank', 'C', 128)).fit_feature_statistics(
        ({'split': 'development', 'values': rows[0]['values'], 'supported': rows[0]['supported']},))


def test_production_fit_claim_requires_pinned_history_identity():
    row = {'split': 'training', 'values': torch.zeros(1, 92, dtype=torch.float64),
           'supported': torch.tensor([True])}
    reader = PrimaryReader(ReaderSpec('bank', 'C', 128))
    with pytest.raises(ValueError): reader.fit_feature_statistics((row,), provenance='original768')
    with pytest.raises(ValueError): reader.fit_feature_statistics((row,), provenance='fixture_only')
    reader.target_mean[0, 0] += 1
    with pytest.raises(ValueError): reader.export_static()


def test_fixture_identity_cannot_be_promoted_to_original_training_static():
    reader = PrimaryReader(ReaderSpec('bank', 'C', 128))
    row = {'split': 'training', 'values': torch.zeros(1, 92, dtype=torch.float64),
           'supported': torch.tensor([True])}
    reader.fit_feature_statistics((row,), provenance={'scope': 'fixture_only',
                                                       'fixture_id': 't18ra1-fixture-00'})
    static = reader.export_static()
    assert static['feature_fit']['identity_hash'] != reader.source['history_identity_hash']
    static['feature_fit'] = {'scope': 'original768', 'row_count': 6144,
                             'identity_hash': reader.source['history_identity_hash']}
    with pytest.raises(ValueError): PrimaryReader.from_static(static, require_production=True)
    with pytest.raises(ValueError): PrimaryReader.from_static(static)
    with pytest.raises(ValueError): reader.export_static(require_production=True)


@pytest.mark.parametrize('family,access,width', [('jet', 'C', 128), ('bank', 'F', 256)])
def test_zero_query_features_and_read_are_empty(family, access, width):
    kernel, snapshot, queries = tiny_case(family)
    empty = replace(queries, query_ids=torch.empty(1, 0, dtype=torch.int64),
                    T=torch.empty(1, 0, dtype=torch.float64), key_ids=torch.empty(1, 0, dtype=torch.int64),
                    key_features=torch.empty(1, 0, 16, dtype=torch.float64), tasks=((),),
                    age_start=torch.empty(1, 0, dtype=torch.float64),
                    age_end=torch.empty(1, 0, dtype=torch.float64),
                    present=torch.empty(1, 0, dtype=torch.bool), lengths=torch.zeros(1, dtype=torch.int64))
    spec = ReaderSpec(family, access, width)
    batch = features(kernel, snapshot, empty, spec)
    assert batch.values.shape == (1, 0, spec.input_dim)
    assert batch.supported.shape == batch.diagnostics['failure'].shape == (1, 0)
    result = PrimaryReader(spec).read(kernel, snapshot, empty)
    assert result.prediction.shape == (1, 0, 8)
    assert result.support.shape == result.failure.shape == (1, 0)
    assert result.diagnostics['prediction_valid'].shape == (1, 0)


def test_feature_fit_rejects_one_shot_rows():
    row = {'split': 'training', 'values': torch.zeros(1, 92, dtype=torch.float64),
           'supported': torch.tensor([True])}
    reader = PrimaryReader(ReaderSpec('bank', 'C', 128))
    with pytest.raises(ValueError): reader.fit_feature_statistics(iter((row,)))


def test_fixture_determinism_and_oracle_schema():
    one = make_two_age_fixture()
    two = make_two_age_fixture()
    assert torch.equal(one.events.values, two.events.values)
    assert len(one.events.history_ids) == 4
    assert one.events.values.shape == (4, 32, 8)
    assert one.queries.T.shape == (4, 64)
    assert one.targets.shape == (4, 64, 8)
    assert one.events.values.dtype == torch.float64
    assert torch.equal(one.targets[0, 0], one.events.values[0, 16])
    assert torch.equal(one.targets[0, 32], one.events.values[0, 16] - one.events.values[0, 0])
