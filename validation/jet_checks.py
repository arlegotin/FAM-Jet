"""Small reproducible device error envelopes, not a scientific experiment.

Run with fallback and fast math disabled; --require-mps refuses hidden MPS.
The JSON contains full bounded inputs and ordinary per-element tolerances.
"""
import argparse
import os
import platform
from pathlib import Path
import sys

import numpy as np
import torch

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from famjet.artifacts import atomic_json
from famjet.memory.coordinates import to_laguerre, from_laguerre, laguerre_step
from famjet.memory.jet import JetMemory, JetState, jet_terminal
from famjet.memory.oracle import direct_moments
from famjet.types import EventBatch


def _fixture():
    rng = torch.Generator().manual_seed(20261016)
    keys = .1 + torch.rand(1, 7, 3, generator=rng, dtype=torch.float64)
    values = torch.randn(1, 7, 2, generator=rng, dtype=torch.float64)
    gates = .2 + torch.rand(1, 7, generator=rng, dtype=torch.float64)
    return {'times': [0, 0, 1, 3, 4, 8, 9], 'keys': keys.tolist(),
            'values': values.tolist(), 'gates': gates.tolist(),
            'observed': [True, True, True, True, True, True, False],
            'rates': [[.01, .1, 1.]], 'rng': 'torch CPU Generator, float64 rand(keys), randn(values), rand(gates)'}


def run_checks(*, include_mps=True):
    fixture = _fixture()
    checks = []
    cases = [('cpu', torch.float64), ('cpu', torch.float32)]
    if include_mps and torch.backends.mps.is_available():
        cases.append(('mps', torch.float32))

    def measure(actual, expected, label, device, dtype, tol):
        actual = actual.detach().cpu().double().numpy()
        expected = np.asarray(expected, dtype=np.float64)
        diff = np.abs(actual-expected)
        ratio = diff/(tol[1]+tol[0]*np.abs(expected))
        checks.append({'device': device, 'dtype': str(dtype), 'quantity': label,
                       'rtol': tol[0], 'atol': tol[1], 'max_absolute_error': float(diff.max()),
                       'max_tolerance_ratio': float(ratio.max()),
                       'passed': bool(np.all(ratio <= 1))})

    for device, dtype in cases:
        keys = torch.tensor(fixture['keys'], dtype=dtype, device=device)
        values = torch.tensor(fixture['values'], dtype=dtype, device=device)
        gates = torch.tensor(fixture['gates'], dtype=dtype, device=device)
        rates = torch.tensor(fixture['rates'], dtype=dtype, device=device)
        obs = torch.tensor(fixture['observed'], device=device)[None, :, None].expand(-1, -1, 2).clone()
        events = EventBatch(('envelope',), torch.arange(7)[None], torch.tensor([fixture['times']]),
                            torch.zeros(1, 7, dtype=torch.int64), keys, values, torch.tensor([7]),
                            torch.ones(1, 7, dtype=torch.bool, device=device), obs, 'ticks', auxiliary={'gate': gates})
        writes = (keys.cpu().double().numpy()[0, :, :, None]
                  * np.concatenate((values.cpu().double().numpy()[0], np.ones((7, 1))), -1)[:, None, :]
                  * (gates.cpu().double().numpy()[0]*np.asarray(fixture['observed']))[:, None, None])
        z, h = direct_moments(np.asarray(fixture['times']), writes, rates.cpu().double().numpy()[0], 9)
        tol = (1e-12, 1e-12) if dtype == torch.float64 else (1e-5, 1e-6)
        stream = JetMemory(rates, 3, 2).encode(events)
        measure(stream.payload['z'][0, 0], z, 'stream_z', device, dtype, tol)
        measure(stream.payload['h'][0, 0], h, 'stream_h', device, dtype, tol)
        for size in (1, 2, 4, 7, 20):
            terminal = jet_terminal(events, rates, size)
            measure(terminal.z[0, 0], z, f'terminal_z_chunk{size}', device, dtype, tol)
            measure(terminal.h[0, 0], h, f'terminal_h_chunk{size}', device, dtype, tol)
        zero = torch.zeros_like(stream.payload['z'])
        l0, l1 = to_laguerre(JetState(zero, zero.clone()))
        for i, time in enumerate(fixture['times']):
            gap = time-fixture['times'][i-1] if i else 0
            gate = gates[:, i, None]*obs[:, i].all(-1)[:, None]
            l0, l1 = laguerre_step(l0, l1, keys[:, i, None], values[:, i, None], gate,
                                   torch.tensor([gap], dtype=torch.float64), rates, events.present[:, i])
        recovered = from_laguerre(l0, l1)
        measure(recovered.z[0, 0], z, 'laguerre_z', device, dtype, tol)
        measure(recovered.h[0, 0], h, 'laguerre_h', device, dtype, tol)
    return {'schema_version': 1, 'seed': 20261016, 'fixture': fixture,
            'environment': {'platform': platform.platform(), 'python': platform.python_version(),
                            'torch': str(torch.__version__), 'numpy': str(np.__version__),
                            'mps_available': torch.backends.mps.is_available(),
                            'mps_fallback': os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK'),
                            'mps_fast_math': os.environ.get('PYTORCH_MPS_FAST_MATH')},
            'checks': checks, 'passed': all(c['passed'] for c in checks),
            'scope': 'Bounded seeded forward state errors only; gradients/time edges are covered separately by pytest.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-mps', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('artifacts/jet_checks.json'))
    args = parser.parse_args()
    if args.require_mps and (not torch.backends.mps.is_available()
                            or os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK') != '0'
                            or os.environ.get('PYTORCH_MPS_FAST_MATH') != '0'):
        raise SystemExit('Native MPS and explicit fallback=0/fast_math=0 required')
    result = run_checks()
    atomic_json(args.output, result)
    print(f'{len(result["checks"])} device/state checks; passed={result["passed"]}; {args.output}')
    raise SystemExit(0 if result['passed'] else 1)
