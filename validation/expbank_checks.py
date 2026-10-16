"""Bounded bank/device oracle envelopes and optional differencing diagnostics.

Finite differences are diagnostics only, never the default bank read. Run with
--require-mps and fallback/fast math0 for actual native device evidence.
"""
import argparse
import math
import os
from pathlib import Path
import platform
import sys

import numpy as np
import torch

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from famjet.artifacts import atomic_json
from famjet.memory.expbank import ExpBankMemory, exp_terminal, contract_bank
from famjet.memory.oracle import direct_moments
from famjet.types import EventBatch
from validation.jet_checks import _fixture


def run_checks(*, include_mps=True):
    fixture = _fixture()
    fixture['rates'] = [np.geomspace(.01, 1., 8).tolist()]
    checks, differences = [], []
    cases = [('cpu64', 'cpu', torch.float64), ('cpu32', 'cpu', torch.float32)]
    if include_mps and torch.backends.mps.is_available():
        cases.append(('mps32', 'mps', torch.float32))

    for case, device, dtype in cases:
        key = torch.tensor(fixture['keys'], dtype=dtype, device=device)
        value = torch.tensor(fixture['values'], dtype=dtype, device=device)
        gate = torch.tensor(fixture['gates'], dtype=dtype, device=device)
        rate = torch.tensor(fixture['rates'], dtype=dtype, device=device)
        observed = torch.tensor(fixture['observed'], device=device)[None, :, None].expand(-1, -1, 2).clone()
        events = EventBatch(('bank-envelope',), torch.arange(7)[None], torch.tensor([fixture['times']]),
                            torch.zeros(1, 7, dtype=torch.int64), key, value, torch.tensor([7]),
                            torch.ones(1, 7, dtype=torch.bool, device=device), observed, 'ticks', auxiliary={'gate': gate})
        writes = (key.cpu().double().numpy()[0, :, :, None]
                  * np.concatenate((value.cpu().double().numpy()[0], np.ones((7, 1))), -1)[:, None]
                  * (gate.cpu().double().numpy()[0]*np.asarray(fixture['observed']))[:, None, None])
        rates64 = rate.cpu().double().numpy()[0]
        z, _ = direct_moments(np.asarray(fixture['times']), writes, rates64, 9)
        tol = (1e-12, 1e-12) if dtype == torch.float64 else (1e-5, 1e-6)

        def measure(actual, expected, quantity):
            actual = actual.detach().cpu().double().numpy()
            error = np.abs(actual-expected)
            ratio = error/(tol[1]+tol[0]*np.abs(expected))
            checks.append({'case': case, 'device': device, 'dtype': str(dtype), 'quantity': quantity,
                           'rtol': tol[0], 'atol': tol[1], 'max_absolute_error': float(error.max()),
                           'max_tolerance_ratio': float(ratio.max()), 'passed': bool(np.all(ratio <= 1))})

        memory = ExpBankMemory(rate, 3, 2)
        stream = memory.encode(events)
        measure(stream.payload['z'][0, 0], z, 'stream_z')
        for size in (1, 2, 4, 7, 20):
            measure(exp_terminal(events, rate, size)[0, 0], z, f'terminal_z_chunk{size}')
        advanced = memory.advance_copy(stream, 12)
        query = torch.ones(1, 1, 3, dtype=dtype, device=device)
        feature = contract_bank(advanced.payload['z'], query, rate, 1e-8, 1e-12, 1.)
        direct_query, _ = direct_moments(np.asarray(fixture['times']), writes, rates64, 12)
        contractions = direct_query.sum(1)
        measure(feature.diagnostics['u'][0, 0, 0], contractions[:, :-1], 'query_raw_u')
        measure(feature.diagnostics['z'][0, 0, 0], contractions[:, -1], 'query_raw_z')
        measure(feature.diagnostics['r'][0, 0, 0], contractions[:, :-1]/(contractions[:, -1:]+1e-8), 'query_normalized_r')

        # Keep actual represented center rate and poles, plus stencil collapse.
        center = float(torch.tensor(.3, dtype=dtype))
        _, moment = direct_moments(np.asarray(fixture['times']), writes, np.asarray([center]), 9)
        curve = []
        for spacing in (1e-1, 1e-2, 1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8):
            poles = torch.tensor([[center*math.exp(-spacing), center*math.exp(spacing)]], dtype=dtype, device=device)
            represented = poles.cpu().double().numpy()[0]
            state = exp_terminal(events, poles, 2)
            estimate = ((state[:, :, 0]-state[:, :, 1])/(2*spacing)).detach().cpu().double().numpy()[0, 0]
            curve.append({'requested_log_half_spacing': spacing, 'represented_poles': represented.tolist(),
                          'realized_log_half_spacing': float(np.log(represented[1]/represented[0])/2),
                          'poles_collapsed': bool(represented[0] == represented[1]),
                          'max_absolute_error': float(np.max(np.abs(estimate-moment[0])))})
        differences.append({'case': case, 'center_rate': center, 'curve': curve,
                            'scope': 'Optional symmetric log-rate stencil; no pass/fail conditioning bound.'})

    return {'schema_version': 1, 'seed': 20261016, 'fixture': fixture,
            'environment': {'platform': platform.platform(), 'python': platform.python_version(),
                            'torch': str(torch.__version__), 'numpy': str(np.__version__),
                            'mps_available': torch.backends.mps.is_available(),
                            'mps_fallback': os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK'),
                            'mps_fast_math': os.environ.get('PYTORCH_MPS_FAST_MATH')},
            'checks': checks, 'finite_difference': differences, 'passed': all(c['passed'] for c in checks),
            'scope': 'Bounded seeded state/read error envelopes; pytest separately covers gradients and time edges. No throughput or universal conditioning claim.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-mps', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('artifacts/expbank_checks.json'))
    args = parser.parse_args()
    if args.require_mps and (not torch.backends.mps.is_available()
                            or os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK') != '0'
                            or os.environ.get('PYTORCH_MPS_FAST_MATH') != '0'):
        raise SystemExit('Native MPS and explicit fallback=0/fast_math=0 required')
    result = run_checks()
    atomic_json(args.output, result)
    print(f'{len(result["checks"])} bank device/state/read checks; passed={result["passed"]}; {args.output}')
    raise SystemExit(0 if result['passed'] else 1)
