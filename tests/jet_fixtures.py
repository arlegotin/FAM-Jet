"""Deterministic bounded fixtures shared by kernel tests (seed 20261016)."""
import torch
import pytest
from famjet.types import EventBatch, QueryBatch


@pytest.fixture(params=['cpu64', 'cpu32', 'mps32'])
def kernel_case(request):
    if request.param == 'mps32' and not torch.backends.mps.is_available():
        pytest.skip('native MPS unavailable in this process')
    dtype = torch.float64 if request.param == 'cpu64' else torch.float32
    device = 'mps' if request.param == 'mps32' else 'cpu'
    return dtype, device, (1e-12, 1e-12) if dtype == torch.float64 else (1e-5, 1e-6)


def events(dtype=torch.float64, device='cpu'):
    rng = torch.Generator().manual_seed(20261016)
    keys = (.1 + torch.rand(2, 6, 3, generator=rng, dtype=torch.float64)).to(device, dtype)
    values = torch.randn(2, 6, 2, generator=rng, dtype=torch.float64).to(device, dtype)
    present = (torch.arange(6)[None] < torch.tensor([6, 4])[:, None]).to(device)
    observed = present[:, :, None].expand(-1, -1, 2).clone()
    observed[0, -1] = False  # real final no-write gap
    return EventBatch(('a', 'b'), torch.arange(6).expand(2, -1).clone(),
        torch.tensor([[0, 0, 1, 3, 4, 8], [2, 3, 3, 7, 0, 0]]),
        torch.zeros(2, 6, dtype=torch.int64), keys, values, torch.tensor([6, 4]),
        present, observed, 'ticks', auxiliary={'gate': (.2 + torch.rand(2, 6, generator=rng, dtype=torch.float64)).to(device, dtype)})


def queries(e, times):
    times = torch.as_tensor(times)
    if times.is_floating_point():
        times = times.to(torch.float64)
    b, q = times.shape
    return QueryBatch(e.history_ids, torch.arange(q).expand(b, -1).clone(), times,
        torch.zeros(b, q, dtype=torch.int64), torch.ones(b, q, e.key_features.shape[-1], device=e.values.device, dtype=e.values.dtype),
        tuple(tuple('mean' for _ in range(q)) for _ in range(b)),
        torch.zeros(b, q, dtype=torch.float64), torch.ones(b, q, dtype=torch.float64),
        torch.ones(b, q, device=e.values.device, dtype=torch.bool), torch.full((b,), q))


def chunk(e, start, end):
    from dataclasses import replace
    return replace(e, event_ids=e.event_ids[:, start:end], timestamps=e.timestamps[:, start:end],
        key_ids=e.key_ids[:, start:end], key_features=e.key_features[:, start:end], values=e.values[:, start:end],
        lengths=(e.lengths-start).clamp(0, end-start), present=e.present[:, start:end], observed=e.observed[:, start:end],
        auxiliary={k: v[:, start:end] for k, v in e.auxiliary.items()})
