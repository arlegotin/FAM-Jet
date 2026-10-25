import importlib.util
import json
import subprocess
import sys
import time
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
    old_selected = [{**row, 'method': 'old-config-hash'} for row in rows]
    assert driver.compare_scientific_rows(old_selected, rows, ['h1'], 'exact',
                                          source_method='old-config-hash')['row_count'] == 8
    with pytest.raises(ValueError, match='method coverage'):
        driver.compare_scientific_rows(old_selected, rows, ['h1'], 'exact',
                                       source_method='different-config-hash')
    with pytest.raises(ValueError, match='scientific row mismatch'):
        driver.compare_scientific_rows(rows, [{**row, 'prediction': [2.]} for row in rows], ['h1'], 'exact')
    with pytest.raises(ValueError, match='coverage'):
        driver.compare_scientific_rows(rows, [], ['h1'], 'exact')
    with pytest.raises(ValueError, match='coverage'):
        driver.compare_scientific_rows(rows, rows + [{**row, 'history_id': 'surplus', 'query_id': 0}],
                                       ['h1'], 'exact')
    with pytest.raises(ValueError, match='duplicate'):
        driver.compare_scientific_rows(rows, rows + [rows[0]], ['h1'], 'exact')
    with pytest.raises(ValueError, match='history'):
        driver.compare_scientific_rows(rows, rows, ['h1', 'h1'], 'exact')


def test_selection_is_first_four_2048_histories_per_regime():
    driver = _driver()
    entries = [{'history_id': f'development_fit-2048-{regime}-{i:03d}'}
               for i in range(16) for regime in driver.REGIMES]
    ids = driver.select_history_ids(entries)
    assert len(ids) == 16
    assert ids[:4] == [f'development_fit-2048-{regime}-000' for regime in driver.REGIMES]
    assert ids[-4:] == [f'development_fit-2048-{regime}-003' for regime in driver.REGIMES]


def test_archived_public_row_shapes_cover_all_eight_projection_bindings():
    driver = _driver()
    _, journal, _, ids, _, rows, _ = driver._old_public_sources(driver.DEFAULT_PUBLIC_ROOT)
    assert set(rows) == set(driver.METHODS)
    for method, original in rows.items():
        source_method = (journal['selected'][method]['config_hash']
                         if method in ('jet', 'bank') else method)
        relabeled = [{**row, 'method': method} for row in original
                     if row['history_id'] in set(ids)]
        matched = driver.compare_scientific_rows(original, relabeled, ids, method,
                                                 source_method=source_method)
        assert matched['row_count'] == 128


def test_public_reference_rejects_private_sibling_and_symlink_before_read(tmp_path, monkeypatch):
    driver = _driver()
    public = tmp_path / 'old-run'
    rows = public / 'development_k16/study/rows'
    rows.mkdir(parents=True)
    forbidden = public / 'confirmation' / 'forbidden.json'
    forbidden.parent.mkdir()
    forbidden.write_text('private fixture')
    read_forbidden = []
    original_read = Path.read_bytes
    def guarded_read(path):
        if Path(path) == forbidden:
            read_forbidden.append(path)
            raise AssertionError('forbidden fixture was opened')
        return original_read(path)
    monkeypatch.setattr(Path, 'read_bytes', guarded_read)
    with pytest.raises(ValueError, match='public'):
        driver._rebase_ref({'path': 'artifacts/e2e-core-run-04/confirmation/forbidden.json',
                            'sha256': '0' * 64, 'bytes': 15}, public)
    with pytest.raises(ValueError, match='public'):
        driver._rebase_ref({'path': 'artifacts/e2e-core-run-04/development_k16/study/rows/../../../confirmation/forbidden.json',
                            'sha256': '0' * 64, 'bytes': 15}, public)
    (rows / 'link.json').symlink_to(forbidden)
    with pytest.raises(ValueError, match='public'):
        driver._rebase_ref({'path': 'artifacts/e2e-core-run-04/development_k16/study/rows/link.json',
                            'sha256': '0' * 64, 'bytes': 15}, public)
    assert read_forbidden == []


def test_initial_public_journal_and_cache_symlinks_fail_before_open(tmp_path, monkeypatch):
    driver = _driver()
    public = tmp_path / 'old-run'
    study = public / 'development_k16/study'
    cache = study / 'development-cache'
    cache.mkdir(parents=True)
    forbidden = tmp_path / 'private-sibling.json'
    forbidden.write_text('private fixture')
    read_forbidden = []
    original_read = Path.read_bytes
    def guarded_read(path):
        if Path(path) == forbidden:
            read_forbidden.append(path)
            raise AssertionError('forbidden fixture was opened')
        return original_read(path)
    monkeypatch.setattr(Path, 'read_bytes', guarded_read)
    journal = study / 'development.json'
    journal.symlink_to(forbidden)
    with pytest.raises(ValueError, match='public'):
        driver._old_public_sources(public)
    journal.unlink()
    journal.write_bytes((driver.DEFAULT_PUBLIC_ROOT / 'development_k16/study/development.json').read_bytes())
    (cache / 'cache-manifest.json').symlink_to(forbidden)
    with pytest.raises(ValueError, match='public'):
        driver._old_public_sources(public)
    assert read_forbidden == []


def test_public_root_with_symlink_ancestor_rejects_before_journal_open(tmp_path, monkeypatch):
    driver = _driver()
    actual_parent = tmp_path / 'private-sibling'
    root = actual_parent / 'old-run'
    journal = root / 'development_k16/study/development.json'
    journal.parent.mkdir(parents=True)
    journal.write_text('private fixture')
    alias = tmp_path / 'alias'
    alias.symlink_to(actual_parent, target_is_directory=True)
    supplied = alias / 'old-run'
    observed = []
    original_read = Path.read_bytes
    def guarded_read(path):
        if Path(path) == supplied / 'development_k16/study/development.json':
            observed.append(path)
            raise AssertionError('forbidden fixture was opened')
        return original_read(path)
    monkeypatch.setattr(Path, 'read_bytes', guarded_read)
    with pytest.raises(ValueError, match='symlink'):
        driver._old_public_sources(supplied)
    assert observed == []


def test_public_driver_uses_outer_and_nested_inner_guard_roots(tmp_path):
    driver = _driver()
    roots = []
    def observe(root):
        roots.append(root.relative_to(tmp_path).as_posix())
        return {'tree_rss_bytes': 2, 'run_output_bytes': 0,
                'now_epoch_seconds': time.time(), 'descendant_pids': []}
    allocation = {'allocation_id': 'public-fixture', 'max_wall_seconds': 2,
                  'max_disk_bytes': 1000000, 'max_rss_bytes': 1000}
    with driver.public_guard_pair(tmp_path, allocation, observer=observe,
                                  sample_interval=.01) as (outer, inner):
        inner.check()
        time.sleep(.04)
    assert set(roots) == {'.', 'runs'}
    assert json.loads((tmp_path / 'outer-live-guard.json').read_bytes())['background_count'] >= 1
    assert json.loads((tmp_path / 'runs/live-guard.json').read_bytes())['background_count'] >= 1


def test_archived_model_parent_symlink_is_rejected_before_model_open(tmp_path, monkeypatch):
    driver = _driver()
    monkeypatch.setattr(driver, 'ROOT', tmp_path)
    archive = tmp_path / 'docs/research/e2e-evaluation-v2-public-model-baseline'
    archive.mkdir(parents=True)
    forbidden = tmp_path / 'private-sibling'
    forbidden.mkdir()
    (forbidden / 'model.json').write_text('private fixture')
    (forbidden / 'model.npz').write_bytes(b'private fixture')
    (archive / 'k16_jet').symlink_to(forbidden, target_is_directory=True)
    ref = {'path': 'docs/research/e2e-evaluation-v2-public-model-baseline/k16_jet/model.json',
           'sha256': '0' * 64}
    with pytest.raises(ValueError, match='symlink'):
        driver._archived_model_file(ref, 'jet')


def test_public_control_builder_uses_archived_development_training_seed():
    driver = _driver()
    from famjet_poc.models import load_model
    baseline, journal, _, _, _, _, _ = driver._old_public_sources(driver.DEFAULT_PUBLIC_ROOT)
    ref = baseline['roles']['k16_jet']['archived_model_ref']
    selected_jet = load_model(driver._archived_model_file(ref, 'jet'), ref['sha256'])
    controls, worker_limits = driver.build_public_controls(selected_jet,
                                                          journal['manifest_sha256'])
    assert controls['reservoir']['constructor_tail']['seed'] == 2026102401801
    assert worker_limits == {'max_frame_bytes': 33554432,
                             'max_array_bytes': 16777216, 'max_histories': 64}


def test_qualification_receipt_counts_its_own_bytes_before_write(tmp_path):
    driver = _driver()
    (tmp_path / 'rows.json').write_bytes(b'12345')
    body = {'status': 'matched'}
    from famjet.provenance import canonical_json
    size = 5 + len(canonical_json(body))
    with pytest.raises(RuntimeError, match='output'):
        driver.write_qualification_receipt(tmp_path, body, size - 1)
    assert not (tmp_path / 'qualification.json').exists()
    driver.write_qualification_receipt(tmp_path, body, size)
    assert (tmp_path / 'qualification.json').read_bytes() == canonical_json(body)
