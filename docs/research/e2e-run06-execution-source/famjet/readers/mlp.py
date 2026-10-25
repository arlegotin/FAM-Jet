"""Numeric and support heads with real, optionally factorized input cost."""
import torch
from torch import nn


class NumericReader(nn.Module):
    def __init__(self, input_dim: int, value_dim: int, width: int, hidden_layers: int = 2,
                 *, rank: int | None = None, schema: dict | None = None):
        super().__init__()
        if any(type(x) is not int or x <= 0 for x in (input_dim, value_dim, width)):
            raise ValueError('reader dimensions must be positive integers')
        if type(hidden_layers) is not int or hidden_layers < 0:
            raise ValueError('hidden_layers must be nonnegative')
        if rank is not None and (not hidden_layers or type(rank) is not int or not 0 < rank <= min(input_dim, width)):
            raise ValueError('invalid factorization rank')
        self.input_dim, self.value_dim, self.width = input_dim, value_dim, width
        self.hidden_layers, self.rank, self.schema = hidden_layers, rank, schema
        layers = []
        previous = input_dim
        for i in range(hidden_layers):
            if i == 0 and rank is not None:
                layers.extend([nn.Linear(previous, rank, bias=False), nn.Linear(rank, width)])
            else:
                layers.append(nn.Linear(previous, width))
            layers.append(nn.SiLU())
            previous = width
        self.hidden = nn.Sequential(*layers)
        self.output = nn.Linear(previous, value_dim)
        self.support = nn.Linear(previous, 1)
        self.register_buffer('feature_mean', torch.zeros(input_dim))
        self.register_buffer('feature_scale', torch.ones(input_dim))

    def forward(self, inputs):
        hidden = self.hidden((inputs-self.feature_mean)/self.feature_scale)
        return self.output(hidden), self.support(hidden).squeeze(-1)

    def cost(self):
        """Actual active parameter count and dense multiply-accumulates/query."""
        return {'parameters': sum(p.numel() for p in self.parameters()),
                'macs_per_query': sum(m.in_features*m.out_features for m in self.modules() if isinstance(m, nn.Linear)),
                'input_dim': self.input_dim, 'rank': self.rank}
