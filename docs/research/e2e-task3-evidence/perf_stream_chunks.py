"""Tiny prospective E1 stream-call overhead diagnostic, never a study run."""
from dataclasses import replace
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import torch

from famjet.eval.metrics import fit_target_statistics
from famjet.provenance import canonical_json
from famjet_poc.contracts import PopulationSpec, ReaderSpec, ShapeSpec
from famjet_poc.data import generate_episode
from famjet_poc.models import build_model


def main():
    torch.set_num_threads(1)
    spec = PopulationSpec('poc_numeric_v1', ShapeSpec(12, 1), 'unit_test', 318,
                          (128,), ('piecewise_stationary',), 8, 512)
    ep = generate_episode(spec, 'unit-stream-overhead-0')
    training_view = replace(ep, metadata={**ep.metadata, 'split': 'training'})
    stats = fit_target_statistics([training_view])
    reader = ReaderSpec('ridge_v1', 'jet', 8, 1e-6, 1 / 5224, 1., 1e-6, 1e-12)
    model = build_model(spec.shape, reader, 1., stats)

    def stream(chunk):
        state = None
        started = time.perf_counter()
        with torch.no_grad():
            for start in range(0, 128, chunk):
                stop = min(start + chunk, 128)
                batch = replace(ep.events,
                    **{name: getattr(ep.events, name)[:, start:stop] for name in
                       ('event_ids', 'timestamps', 'key_ids', 'key_features', 'values', 'present', 'observed')},
                    lengths=torch.tensor([stop - start], dtype=torch.int64),
                    auxiliary={k: v[:, start:stop] for k, v in ep.events.auxiliary.items()})
                state = model.encode(batch, state, mode='stream')
        return state, time.perf_counter() - started

    times = {}
    states = {}
    for chunk in (1, 16, 32, 128):
        values = []
        for _ in range(4):
            state, elapsed = stream(chunk)
            values.append(elapsed)
        times[str(chunk)] = values
        states[chunk] = state
    reference = states[1]
    comparisons = {}
    reference_read = model.read(reference, ep.queries)
    for chunk in (16, 32, 128):
        state = states[chunk]
        exact = all(torch.equal(reference.payload[name], state.payload[name]) for name in reference.payload)
        error = max(float(torch.max(torch.abs(reference.payload[name] - state.payload[name])))
                    for name in ('z', 'h'))
        read = model.read(state, ep.queries)
        prediction_exact = torch.equal(reference_read.prediction.contiguous().view(torch.int64),
                                       read.prediction.contiguous().view(torch.int64))
        comparisons[str(chunk)] = {'state_bitwise_equal': exact,
                                   'max_state_absolute_error': error,
                                   'prediction_bitwise_equal': prediction_exact}
    result = {'profile': 'unit_test', 'history_id': ep.events.history_ids[0],
              'event_count': 128, 'mode': 'stream', 'repeats': 4,
              'elapsed_seconds': times,
              'median_speedup_vs_one_event': {str(chunk): statistics.median(times['1']) / statistics.median(times[str(chunk)])
                                              for chunk in (16, 32, 128)},
              'comparisons': comparisons}
    print(canonical_json(result).decode())


if __name__ == '__main__':
    main()
