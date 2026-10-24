"""Independent two-age, all-key information-sufficiency fixture; no fitting."""
from dataclasses import dataclass

import torch

from famjet.types import EventBatch, QueryBatch


@dataclass(frozen=True)
class TwoAgeFixture:
    events: EventBatch
    queries: QueryBatch
    targets: torch.Tensor


def make_two_age_fixture():
    generator = torch.Generator(device='cpu').manual_seed(2026102401)
    values = 2*torch.rand((4, 2, 16, 8), generator=generator, dtype=torch.float64)-1
    recent, old = values[:, 1], values[:, 0]
    event_values = values.reshape(4, 32, 8)
    key_ids = torch.arange(16, dtype=torch.int64).repeat(2)[None].repeat(4, 1)
    key = torch.nn.functional.one_hot(key_ids, 16).to(torch.float64)
    present = torch.ones(4, 32, dtype=torch.bool)
    ids = tuple(f't18ra1-fixture-{i:02d}' for i in range(4))
    events = EventBatch(ids, torch.arange(32, dtype=torch.int64)[None].repeat(4, 1),
                        torch.tensor([0.]*16 + [2.]*16, dtype=torch.float64)[None].repeat(4, 1),
                        key_ids, key, event_values, torch.full((4,), 32, dtype=torch.int64),
                        present, present[..., None].expand(4, 32, 8).clone(), 's')
    query_key_ids = torch.arange(16, dtype=torch.int64).repeat(4)[None].repeat(4, 1)
    query_key = torch.nn.functional.one_hot(query_key_ids, 16).to(torch.float64)
    starts = torch.tensor([0.]*16 + [2.]*16 + [0.]*16 + [0.]*16, dtype=torch.float64)[None].repeat(4, 1)
    ends = torch.tensor([1.]*16 + [3.]*16 + [2.]*16 + [1.5]*16, dtype=torch.float64)[None].repeat(4, 1)
    queries = QueryBatch(ids, torch.arange(64, dtype=torch.int64)[None].repeat(4, 1),
                         torch.full((4, 64), 2., dtype=torch.float64), query_key_ids, query_key,
                         tuple((('mean',)*32 + ('contrast',)*32) for _ in range(4)),
                         starts, ends, torch.ones(4, 64, dtype=torch.bool),
                         torch.full((4,), 64, dtype=torch.int64))
    targets = torch.cat((recent, old, recent-old, recent-old), 1)
    return TwoAgeFixture(events, queries, targets)
