"""Reader controls must retain information and charge actual learned widths."""
import importlib
import torch
import pytest


def api():
    assert importlib.util.find_spec('famjet.readers.mlp') is not None, 'numeric reader is missing'
    from famjet.readers.mlp import NumericReader
    from famjet.readers.structured import make_reader
    return NumericReader, make_reader


def test_parameter_budget_uses_actual_input_width():
    _, make = api()
    spec = dict(family='jet', anchors=2, key_dim=3, value_dim=2)
    query = dict(key_dim=3)
    a = make('generic_full', spec, query, dict(width=16, hidden_layers=2, max_parameters=500))
    assert sum(p.numel() for p in a.parameters()) <= 500
    assert a.input_dim == 36 + 3 + 7 + 2
    assert a.rank is not None
    with pytest.raises(ValueError, match='budget'):
        make('generic_full', spec, query, dict(width=16, hidden_layers=2, max_parameters=2))


def test_reader_support_head_and_linear_training():
    NumericReader, _ = api()
    reader = NumericReader(2, 1, 4, hidden_layers=0).double()
    x = torch.tensor([[-1., 1.], [0., 0.], [1., -1.]], dtype=torch.float64)
    opt = torch.optim.SGD(reader.parameters(), lr=.1)
    for _ in range(100):
        y, support = reader(x)
        loss = (y[:, 0] - 2*x[:, 0]).square().mean() + support.square().mean()
        opt.zero_grad(); loss.backward(); opt.step()
    assert loss.item() < 1e-10


def test_raw_bank_and_contracted_inputs_preserve_amplitude():
    _, make = api()
    from famjet.readers.structured import memory_inputs
    from famjet.memory.jet import JetMemory
    from famjet.memory.expbank import ExpBankMemory
    from jet_fixtures import events, queries
    e = events(); q = queries(e, [[8], [7]])
    for cls, kind in [(JetMemory, 'generic_contracted'), (ExpBankMemory, 'bank_raw'), (ExpBankMemory, 'bank_normalized')]:
        kernel = cls(torch.tensor([[.1, 1.]], dtype=torch.float64), 3, 2)
        f = kernel.features(kernel.encode(e), q)
        x = memory_inputs(kind, f)
        if kind == 'bank_raw':
            torch.testing.assert_close(x.reshape(2, 1, 1, 2, 3)[..., -1], f.diagnostics['z'])
        elif kind == 'generic_contracted':
            torch.testing.assert_close(x.reshape(2, 1, 1, 2, 6)[..., 4], f.diagnostics['z'])
            torch.testing.assert_close(x.reshape(2, 1, 1, 2, 6)[..., 5], f.diagnostics['b'])
        else:
            torch.testing.assert_close(x.reshape(2, 1, 1, 2, 3)[..., :2], f.diagnostics['r'])


def test_compute_budget_rejects_inactive_padding():
    _, make = api()
    reader = make('generic_full', dict(family='jet', anchors=2, key_dim=3, value_dim=2),
                  dict(key_dim=3), dict(width=16, hidden_layers=2, max_macs=450))
    assert reader.cost()['macs_per_query'] <= 450
    assert reader.cost()['parameters'] == sum(p.numel() for p in reader.parameters())


def test_fixed_scale_anchor_is_explicit_and_selectable():
    _, make = api()
    from famjet.readers.structured import memory_inputs
    from famjet.memory.jet import JetMemory
    from jet_fixtures import events, queries
    e = events(); q = queries(e, [[8], [7]])
    k = JetMemory(torch.tensor([[.1, 1.]], dtype=torch.float64), 3, 2)
    f = k.features(k.encode(e), q)
    r = make('fixed_scale:1', dict(family='jet', anchors=2, key_dim=3, value_dim=2), dict(key_dim=3), dict(width=8, hidden_layers=2))
    torch.testing.assert_close(memory_inputs(r.schema['kind'], f)[..., :2], f.diagnostics['r'][:, :, 0, 1])
    with pytest.raises(ValueError, match='anchor'):
        make('fixed_scale:2', dict(family='jet', anchors=2, key_dim=3, value_dim=2), dict(key_dim=3), dict(width=8, hidden_layers=2))


def test_derived_sign_does_not_allocate_an_unused_task_column():
    api()
    from famjet.readers.structured import query_inputs
    from famjet.eval.oracle import TASKS
    from dataclasses import replace
    from jet_fixtures import events, queries
    e = events(); tasks = tuple(sorted(TASKS - {'change_sign'}))
    q = queries(e, torch.full((2, len(tasks)), 20))
    q = replace(q, tasks=(tasks, tasks))
    x = query_inputs(q, 1.)
    task_columns = x[0, :, 3:-2]
    assert task_columns.shape == (7, 7)
    assert torch.equal(task_columns.sum(0), torch.ones(7, dtype=task_columns.dtype))


@pytest.mark.parametrize('kind,budget', [
    ('fixed_scale:'+'0'*1000, dict(width=8, hidden_layers=2)),
    ('structured', dict(width=8, hidden_layers=2, max_parameters=2**1000)),
    ('structured', dict(width=8, hidden_layers=2, max_macs=2**1000)),
])
def test_reader_schema_rejects_oversized_inactive_metadata(kind, budget):
    _, make = api()
    with pytest.raises(ValueError, match='anchor|budget|schema'):
        make(kind, dict(family='jet', anchors=2, key_dim=3, value_dim=2), dict(key_dim=3), budget)
