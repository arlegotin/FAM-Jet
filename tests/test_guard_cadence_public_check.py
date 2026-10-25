import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'docs/research/e2e-guard-cadence-public-check.py'


def _driver():
    spec = importlib.util.spec_from_file_location('public_guard_check', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_driver_help_does_not_run_a_workload():
    run = subprocess.run([sys.executable, str(SCRIPT), '--help'],
                         capture_output=True, text=True, check=True)
    assert '--out' in run.stdout and '--old-public-root' in run.stdout


def test_projection_requires_complete_exact_scientific_rows():
    driver = _driver()
    row = {key: None for key in driver.PROJECTION_FIELDS}
    row.update(history_id='h1', method='exact', task='mean', target=[1.],
               prediction=[1.], failure=False, numeric_supported=True,
               loss=0., policy_hash='old')
    rows = [{**row, 'query_id': i} for i in range(8)]
    changed_policy = [{**row, 'policy_hash': 'new'} for row in rows]
    assert driver.compare_scientific_rows(rows, changed_policy, ['h1'], 'exact')['row_count'] == 8
    with pytest.raises(ValueError, match='scientific row mismatch'):
        driver.compare_scientific_rows(rows, [{**row, 'prediction': [2.]} for row in rows], ['h1'], 'exact')
    with pytest.raises(ValueError, match='coverage'):
        driver.compare_scientific_rows(rows, [], ['h1'], 'exact')


def test_selection_is_first_four_2048_histories_per_regime():
    driver = _driver()
    entries = [{'history_id': f'development_fit-2048-{regime}-{i:03d}'}
               for i in range(16) for regime in driver.REGIMES]
    ids = driver.select_history_ids(entries)
    assert len(ids) == 16
    assert ids[:4] == [f'development_fit-2048-{regime}-000' for regime in driver.REGIMES]
    assert ids[-4:] == [f'development_fit-2048-{regime}-003' for regime in driver.REGIMES]
