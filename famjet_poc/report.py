"""Deterministic Markdown and machine report from validated frozen artifacts."""

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from famjet.provenance import canonical_json

from .report_inputs import load_report_inputs


_ROOT = Path(__file__).resolve().parent.parent


def _write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.e5-', delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _smoke_markdown(inputs):
    return '\n'.join((
        '# FAM-Jet artifact replay',
        '',
        '**Status: non_scientific_smoke.** This test-only release does not support a scientific conclusion.',
        '',
        f"Frozen source SHA-256: `{inputs['source_sha256']}`.  ",
        f"Frozen executable SHA-256: `{inputs['executable_sha256']}`.  ",
        f"Release SHA-256: `{inputs['release_sha256']}`.",
        '',
        f"Validated methods: {', '.join(inputs['synthetic']['methods'])}; "
        f"{inputs['synthetic']['query_rows']} raw scored rows.",
        '',
        'Native Beijing metrics: unavailable in this test-only fixture.',
        '',
    ))


def _plot_python():
    explicit = os.environ.get('FAMJET_REPORT_PYTHON')
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise RuntimeError(f'FAMJET_REPORT_PYTHON is missing: {path}')
        return path
    local = _ROOT / '.report-venv' / 'bin' / 'python'
    if local.is_file():
        return local
    if importlib.util.find_spec('matplotlib') is not None:
        return Path(sys.executable)
    raise RuntimeError('Matplotlib plotting dependency missing; install docs/reporting-requirements.lock '
                       'in .report-venv or set FAMJET_REPORT_PYTHON')


def _fmt(value, digits=5):
    if value is None:
        return 'null (unavailable)'
    if type(value) in (int, float) and math.isfinite(value):
        return f'{value:.{digits}g}'
    return str(value)


def _science_chart_data(inputs):
    development = inputs['development']['K16/V8']
    timing = inputs['timing']['summaries']
    methods = []
    for family in ('jet', 'bank'):
        chosen = development['selected'][family]['config_hash']
        candidate = next(item for item in development['candidates']
                         if item['config_hash'] == chosen)
        methods.append({'name': family, 'loss': candidate['loss'],
             'state_bytes': candidate['costs']['maximum_state_bytes'],
             'static_bytes': candidate['wire_static_bytes'],
             'query_seconds': timing[family]['8']['read_output_seconds']['p50']})
    for name, entry in development['controls'].items():
        methods.append({'name': name, 'loss': entry['score']['loss'],
             'state_bytes': entry['costs']['maximum_state_bytes'],
             'static_bytes': entry['costs']['statics_bytes'],
             'query_seconds': timing[name]['8']['read_output_seconds']['p50']})
    effects = [{'panel': phase, 'estimate': panel['D'],
                'lower': panel['lower'], 'upper': panel['upper']}
               for phase, panel in inputs['synthetic']['paired_panels'].items()]
    return {'schema_version': 1, 'kind': 'famjet_e5_chart_data',
            'methods': methods, 'effects': effects,
            'freeze_sha256': inputs['freeze_sha256'],
            'release_sha256': inputs['release_sha256']}


def _render_plots(chart_data, out):
    python = _plot_python()
    chart_path = out.with_name(out.stem + '-chart-data.json')
    chart_bytes = canonical_json(chart_data)
    _write(chart_path, chart_bytes)
    plots_dir = out.with_name(out.stem + '-charts')
    argv = [str(python), str(_ROOT / 'famjet_poc' / 'plots.py'),
            '--data', str(chart_path), '--out', str(plots_dir)]
    started = time.perf_counter()
    env = {**os.environ, 'MPLBACKEND': 'Agg'}
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=env, check=False, timeout=300)
    elapsed = time.perf_counter() - started
    invocation = {'argv': argv, 'exit_code': result.returncode,
                  'elapsed_seconds': elapsed, 'stdout_stderr_bytes': len(result.stdout),
                  'stdout_stderr_sha256': hashlib.sha256(result.stdout).hexdigest()}
    _write(plots_dir / 'plot-invocation.log', result.stdout)
    _write(plots_dir / 'plot-invocation.json', canonical_json(invocation))
    if result.returncode:
        raise RuntimeError(f'Matplotlib plot export failed ({result.returncode}): '
                           + result.stdout.decode(errors='replace')[-800:])
    receipt_path = plots_dir / 'plots-receipt.json'
    receipt = json.loads(receipt_path.read_bytes())
    if (receipt.get('data_sha256') != hashlib.sha256(chart_bytes).hexdigest() or
            receipt.get('renderer_sha256') != hashlib.sha256(
                (_ROOT / 'famjet_poc' / 'plots.py').read_bytes()).hexdigest() or
            receipt.get('report_lock_sha256') != hashlib.sha256(
                (_ROOT / 'docs/reporting-requirements.lock').read_bytes()).hexdigest()):
        raise ValueError('plot data/renderer/environment commitment mismatch')
    for name, expected in receipt['outputs'].items():
        raw = (plots_dir / name).read_bytes()
        if (hashlib.sha256(raw).hexdigest(), len(raw)) != (expected['sha256'], expected['bytes']):
            raise ValueError('plot output byte receipt mismatch')
    return {'chart_data_sha256': hashlib.sha256(chart_bytes).hexdigest(),
            'receipt': receipt, 'directory_name': plots_dir.name}


def coordinate_report(inputs):
    """Expose every validated coordinate receipt without aggregating away failures."""
    panels = {}
    additional_seconds = 0.
    def visit(value, path):
        nonlocal additional_seconds
        if isinstance(value, dict):
            if 'coordinate_diagnostic_summary' in value:
                panels[path] = value['coordinate_diagnostic_summary']
                additional_seconds += value['evaluation_seconds']
            else:
                for key, item in value.items():
                    visit(item, path + '/' + key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, path + '/' + str(index))
    for section in ('development', 'synthetic', 'stress', 'transfer', 'real'):
        visit(inputs.get(section, {}), section)
    return {'policy': 'fp64_coordinate_diagnostic_v2',
            'interpretation': 'strict FP64 read equivalence is not established when any criterion FAILED',
            'panels': panels,
            'additional_coordinate_evaluation_seconds': additional_seconds,
            'additional_expenditure_scope': 'current run coordinate evaluation only; full current run costs remain in section receipts',
            'prior_work': {'run': 'original_actual_run01', 'status': 'FAILED_stopped_before_protected_access',
                           'elapsed_seconds': 1728.763838625, 'current_rss_bytes': 848740352,
                           'diagnosis': 'docs/research/e2e-laguerre-actual-diagnostic-report.md'}}


def coordinate_markdown(diagnostic):
    prior = diagnostic['prior_work']
    lines = ['## Coordinate numerical diagnostics', '',
             'Gamma/Laguerre is a numerical control. Strict FP64 read equivalence is not established '
             'where the original 1e-12 absolute/relative criterion FAILED. State and all five mask '
             'checks remain mandatory; prediction-only rounding is recorded, without a wider tolerance.', '',
             '| Receipt scope | Histories | Queries | Failed histories / queries / scalars | Strict read | State / masks | Max state abs / scaled | Max read abs / scaled |',
             '| --- | ---: | ---: | --- | --- | --- | --- | --- |']
    for scope, item in diagnostic['panels'].items():
        lines.append(f"| {scope} | {item['history_count']} | {item['query_count']} | "
                     f"{item['strict_prediction_failed_histories']} / {item['strict_prediction_failed_queries']} / "
                     f"{item['strict_prediction_failed_scalars']} | {item['strict_prediction_status']} | "
                     f"{item['state_checks']} / {item['mask_checks']} | "
                     f"{_fmt(item['max_state_absolute_error'])} / {_fmt(item['max_state_scaled_error'])} | "
                     f"{_fmt(item['max_prediction_absolute_error'])} / {_fmt(item['max_prediction_scaled_error'])} |")
    lines += ['', f"Prior work: original actual run01 remains **{prior['status']}**; "
              f"elapsed {prior['elapsed_seconds']} s; observed current RSS {prior['current_rss_bytes']} B. "
              f"[Measured conditioning diagnosis]({prior['diagnosis']}). "
              'This observed cancellation case provides no universal error bound.', '',
              f"Additional coordinate evaluation in this run: {diagnostic['additional_coordinate_evaluation_seconds']:.9f} s. "
              'These costs are separate from the stopped run; all other fresh-run fit, cache, worker '
              'and stage costs remain in their machine receipts.', '']
    return '\n'.join(lines)


def _science_machine(inputs, plot):
    panels = inputs['synthetic']['paired_panels']
    confirmed = panels['confirmation']['lower'] > 0
    replicated = panels['replication']['lower'] > 0
    decision = ('conditional_frozen_model_jet_advantage_replicated'
                if confirmed and replicated else 'jet_advantage_not_demonstrated')
    return {'schema_version': 1, 'kind': 'famjet_poc_report',
            'status': 'scientific_artifacts_validated', 'decision': decision,
            'freeze_sha256': inputs['freeze_sha256'],
            'release_sha256': inputs['release_sha256'],
            'source_sha256': inputs['source_sha256'],
            'executable_sha256': inputs['executable_sha256'],
            'git': inputs['freeze']['git'],
            'qualification': inputs['scientific']['qualification'],
            'calibration': inputs['scientific']['calibration'],
            'selected_models': inputs['scientific']['pairs'],
            'coordinate_diagnostics': coordinate_report(inputs),
            'development': inputs['development'], 'timing': inputs['timing'],
            'transfer': inputs['transfer'],
            'synthetic': inputs['synthetic'], 'real': inputs['real'],
            'stress': inputs['stress'],
            'beijing_source_inventory': inputs['beijing_source_inventory'],
            'beijing_source': inputs['beijing_source'],
            'beijing_source_array_status': inputs['beijing_source_array_status'],
            'plot': plot,
            'metrics': {'native_rmse_status': 'see_real_mode_method_rows'},
            'historical_failures': [
                {'name': 'six_prior_mlp_qualification_cases', 'status': 'failed_unchanged',
                 'source': 'docs/research/task18-reader-adequacy-v1-checks-run02-report.md'},
                {'name': 'extreme_signed_cancellation_numerics', 'status': 'failed_unchanged',
                 'source': 'docs/research/task18-kernel-stage-a06-report.md'},
                {'name': 'crossed_bootstrap', 'status': 'failed_unchanged',
                 'source': 'docs/research/task19-bootstrap-recon/report.md'}],
            'limits': ['conditional on frozen fitted readers; retraining variance excluded',
                       'one executed persistent-state budget; no memory frontier',
                       'real 28/56-day clusters are finite-period descriptive sensitivity only',
                       'no broad novelty, capacity, agent or all-family superiority claim']}


def _science_markdown(machine):
    lines = ['# FAM-Jet final artifact report', '',
             f"**Decision:** `{machine['decision']}`.", '',
             'This comparison estimates Bank minus Jet normalized loss conditional on the frozen fitted readers. '
             'The interval excludes retraining variance.', '',
             '## Reproduce', '',
             '```sh',
             '.venv/bin/python -m famjet_poc run --out artifacts/poc-core',
             '.venv/bin/python -m famjet_poc run --out artifacts/poc-core --resume',
             '.venv/bin/python -m famjet_poc report --run artifacts/poc-core --out reports/final.md',
             '```', '',
             f"Frozen executable SHA-256: `{machine['executable_sha256']}`.  ",
             f"Frozen source SHA-256: `{machine['source_sha256']}`.  ",
             f"Release SHA-256: `{machine['release_sha256']}`.  ",
             f"Git revision: `{machine['git']['revision']}`.", '',
             '## Admission and calibration', '',
             'The eight fixed-feature qualification cases established correctness and learnability '
             'for four explicit templates at alpha_max=1 and ridge=1e-10; they do not establish '
             'arbitrary-window sufficiency or every selected ridge configuration.', '',
             f"Reader qualification: `{machine['qualification']['status']}` "
             f"({machine['qualification']['file_count']} archived files).", '',
             'Calibration attempt 1 failed; independent attempt 2 passed all 32 simultaneous guards. '
             'The current conditional-history inference uses the accepted attempt 2; the old crossed '
             'bootstrap failure remains unchanged.', '',
             f"Attempt 2 evidence SHA-256: `{machine['calibration']['evidence_sha256']}`; "
             f"{machine['calibration']['per_cell']} histories per stratum in each scientific panel.", '',
             '## Selected readers and development', '']
    for shape, result in machine['development'].items():
        lines += [f'### {shape}', '',
                  'Frozen chosen configurations:', '',
                  '| Family | Full configuration SHA | Reader parameters | Development loss | Active numeric B | Full wire static B |',
                  '| --- | --- | --- | ---: | ---: | ---: |']
        for family in ('jet', 'bank'):
            chosen = result['selected'][family]
            entry = next(item for item in result['candidates']
                         if item['config_hash'] == chosen['config_hash'])
            reader = json.dumps(chosen['reader'], sort_keys=True, separators=(',', ':'))
            lines.append(f"| {family} | `{chosen['config_hash']}` | `{reader}` | "
                         f"{_fmt(chosen['loss'])} | {_fmt(entry['active_static_bytes'], 0)} | "
                         f"{_fmt(entry['wire_static_bytes'], 0)} |")
        lines += ['', 'Complete candidate ledger:', '',
                  '| Family | Candidate | Development loss | Full wire static B | Fit wall s | Total standalone s | Status / failure |',
                  '| --- | --- | ---: | ---: | ---: | ---: | --- |']
        for item in result['candidates']:
            lines.append(f"| {item['family']} | `{item['config_hash'][:12]}` | "
                         f"{_fmt(item['loss'])} | {_fmt(item['wire_static_bytes'], 0)} | "
                         f"{_fmt((item['costs'] or {}).get('fit_wall_seconds'))} | "
                         f"{_fmt((item['costs'] or {}).get('standalone_seconds'))} | "
                         f"{item['status']}{': ' + item['error'] if item['error'] else ''} |")
        lines += ['', 'Subset fits (each has training-only statistics):', '',
                  '| Family | Training histories | Loss | Evaluation s | Status / failure |',
                  '| --- | ---: | ---: | ---: | --- |']
        for item in result['prefixes']:
            lines.append(f"| {item['family']} | {item['prefix']} | "
                         f"{_fmt(item['score']['loss'] if item['score'] else None)} | "
                         f"{_fmt((item['costs'] or {}).get('evaluation_seconds'))} | "
                         f"{item['status']}{': ' + item['error'] if item['error'] else ''} |")
        lines += ['', f"Training/development cache bytes: "
                  f"{result['shared_costs']['training_cache_bytes']}/"
                  f"{result['shared_costs']['development_cache_bytes']}; "
                  f"fit attempts/completions: {result['fit_attempt_count']}/"
                  f"{result['completed_fit_count']}.", '']
        lines += ['Simple controls:', '',
                  '| Control | Loss | Occupied state B | Full static B | Evaluation s |',
                  '| --- | ---: | ---: | ---: | ---: |']
        for name, item in result['controls'].items():
            lines.append(f"| {name} | {_fmt(item['score']['loss'])} | "
                         f"{_fmt(item['costs']['maximum_state_bytes'], 0)} | "
                         f"{_fmt(item['costs']['statics_bytes'], 0)} | "
                         f"{_fmt(item['costs']['evaluation_seconds'])} |")
        lines.append('')
    lines += ['## One-budget accuracy, state, static storage and cost', '',
              'The chart contains entered configurations at the one declared persistent-state budget. '
              'Full wire-export static bytes are separate from active numeric parameters and recurrent state; cache construction, fit, '
              'preprocessing, serialization, cold start and isolated worker costs remain in the '
              'machine JSON and timing receipts.', '',
              f"![Development loss and occupied state]({machine['plot']['directory_name']}/accuracy-memory.svg)", '',
              f"![Static storage and measured read cost]({machine['plot']['directory_name']}/cost.svg)", '',
              '| Method | Q1 read p50 s | Q8 read p50 s | Q64 read p50 s | Q8 preprocess p50 s | Q8 serialization p50 s |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    for name, data in machine['timing']['summaries'].items():
        lines.append(f"| {name} | {_fmt(data['1']['read_output_seconds']['p50'])} | "
                     f"{_fmt(data['8']['read_output_seconds']['p50'])} | "
                     f"{_fmt(data['64']['read_output_seconds']['p50'])} | "
                     f"{_fmt(data['8']['preprocessing_seconds']['p50'])} | "
                     f"{_fmt(data['8']['serialization_seconds']['p50'])} |")
    lines += ['', '## Protected confirmation and independent replication', '',
              '| Panel | Paired histories | Bank − Jet | 95% lower | 95% upper | Superiority |',
              '| --- | ---: | ---: | ---: | ---: | --- |']
    for phase in ('confirmation', 'replication'):
        item = machine['synthetic']['paired_panels'][phase]
        lines.append(f"| {phase} | {item['paired_history_count']} | {_fmt(item['D'])} | "
                     f"{_fmt(item['lower'])} | {_fmt(item['upper'])} | {item['superiority']} |")
    lines += ['', f"![Separate protected effects]({machine['plot']['directory_name']}/primary-effect.svg)", '',
              'The nuisance pilot was separate and could not select the effect direction. '
              'All entered methods and all raw rows, including fallback and ineligible diagnostics, '
              'remain in the release.', '',
              '| Panel / method | Raw rows | Eligible primary | Ineligible | Fallbacks | Mean normalized loss |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    for key, item in machine['synthetic']['by_phase_method'].items():
        lines.append(f"| {key} | {item['rows']} | {item['primary_rows']} | "
                     f"{item['ineligible_rows']} | {item['fallback_rows']} | "
                     f"{_fmt(item['mean_normalized_loss'])} |")
    lines += ['',
              '## Beijing 2015–17 transfer', '',
              'Both K12/V1 modes use the frozen training normalization and the same 56 chronological '
              'test blocks with 120 queries per block. Native contrast inversion scales without '
              'adding the pollutant mean.', '',
              '| Mode | Method | Native RMSE µg/m³ | Native MAE µg/m³ | Normalized loss | Eligible / ineligible | Fallbacks |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for mode, methods in machine['real']['modes'].items():
        for method, item in methods.items():
            lines.append(f"| {mode} | {method} | {_fmt(item['native_rmse_micrograms'])} | "
                         f"{_fmt(item['native_mae_micrograms'])} | "
                         f"{_fmt(item['mean_normalized_loss'])} | "
                         f"{item['primary_rows']} / {item['ineligible_rows']} | "
                         f"{item['fallback_rows']} |")
    lines += ['', 'The 28-day and 56-day cluster sensitivities use 28 and 14 units respectively. '
              'They describe this finite period and do not provide future-period population significance.', '',
              '| Mode | Cluster | Paired Bank − Jet resampled 95% range | Units |',
              '| --- | --- | --- | ---: |']
    for mode, windows in machine['real']['paired_block_sensitivity'].items():
        for window in ('28d', '56d'):
            item = windows[window]
            lo, hi = item['resampled_mean_95pct']
            lines.append(f"| {mode} | {window} | {_fmt(lo)} to {_fmt(hi)} | "
                         f"{item['cluster_count']} |")
    transfer = machine['transfer']
    lines += ['', '### Task-adapted public fit costs', '',
              f"Measured prefreeze probe: {_fmt(transfer['real_probe']['measured_profile']['fit_seconds'])} s fit, "
              f"{_fmt(transfer['real_probe']['measured_profile']['evaluation_seconds'])} s read; "
              f"forecast {_fmt(transfer['real_probe']['forecast_seconds'])} s.",
              f"Real training/development cache: {transfer['cache_bytes']} B; "
              f"prefreeze elapsed: {_fmt(transfer['elapsed_seconds'])} s. "
              'The selected equivalent reference has separate cost and scored-row receipts.', '',
              '| Family | Candidate | Public development loss | Active numeric B | Evaluation s | Status |',
              '| --- | --- | ---: | ---: | ---: | --- |']
    for item in transfer['real_development_ledger']:
        lines.append(f"| {item['family']} | `{item['config_hash'][:12]}` | "
                     f"{_fmt(item['loss'])} | {_fmt(item['active_static_bytes'], 0)} | "
                     f"{_fmt(item['costs']['evaluation_seconds'])} | {item['status']} |")
    lines += ['',
              '## Secondary tasks and robustness', '',
              '| Cell | Shape | Status | Reason |', '| --- | --- | --- | --- |']
    for item in machine['stress']['secondary_task_ledger']:
        lines.append(f"| {item['name']} | {item['shape']} | {item['status']} | "
                     f"{item['reason'] or '—'} |")
    lines += ['', 'Entered robustness and boundary outcomes:', '',
              '| Mode | Method | Status | Normalized loss | Fallbacks | Evaluation s |',
              '| --- | --- | --- | ---: | ---: | ---: |']
    for item in machine['stress']['results']:
        summary = item['summary'] or {}
        costs = item['costs'] or {}
        lines.append(f"| {item['mode']} | {item['method']} | {item['status']} | "
                     f"{_fmt(summary.get('loss'))} | {_fmt(summary.get('fallback_count'), 0)} | "
                     f"{_fmt(costs.get('evaluation_seconds'))} |")
    lines += ['', 'Unsupported cells have null metrics in the machine JSON. Numeric mean/contrast '
              'results do not imply V32 categorical or support-logit capabilities.', '',
              '## Provenance, failures and limits', '',
              'The complete source/model/grant/score-policy/full-versus-eligible inventory/row/cost '
              'checks precede this report. Raw data, query failures, ineligible labels and training-prior '
              'fallbacks remain in the sealed per-query artifacts.', '',
              f"Beijing v2 source manifest SHA-256: `{machine['real']['beijing_manifest_sha256']}`. "
              f"Official archive SHA-256: `{machine['beijing_source']['archive']['sha256']}`; "
              f"license: {machine['beijing_source']['attribution']['license']}; "
              f"revision: {machine['beijing_source']['preparation_version']}. "
              'Full per-split prepared-array hashes, source attribution and original archive identity '
              'are retained in the machine JSON. External prepared arrays have status '
              f"`{machine['beijing_source_array_status']}`: copied-run analysis checks their "
              'sealed hash inventory and evaluated row/count/grant receipts without reopening '
              'the source array bytes.', '',
              'The six earlier MLP qualification failures, extreme signed-cancellation numerical '
              'failures, and old crossed-bootstrap failure remain failed. The new qualified reader '
              'and conditional inference do not repair them.', '',
              'No multi-budget memory frontier, broad information-capacity result, agent result, '
              'all-family superiority or novelty claim follows from this one entered study.', '']
    lines += [coordinate_markdown(machine.get('coordinate_diagnostics', coordinate_report(machine)))]
    return '\n'.join(lines)


def render_report(run, out):
    """Replay a closed run; publish outputs only after all validation succeeds."""
    inputs = load_report_inputs(run)
    out = Path(out)
    if inputs['status'] == 'non_scientific_smoke':
        machine = {'schema_version': 1, 'kind': 'famjet_poc_report',
                   'status': 'non_scientific_smoke',
                   'freeze_sha256': inputs['freeze_sha256'],
                   'release_sha256': inputs['release_sha256'],
                   'source_sha256': inputs['source_sha256'],
                   'executable_sha256': inputs['executable_sha256'],
                   'synthetic': inputs['synthetic'],
                   'metrics': {'native_rmse_micrograms': None,
                               'native_rmse_status': 'not_applicable_test_fixture'}}
        markdown = _smoke_markdown(inputs)
    else:
        chart_data = _science_chart_data(inputs)
        plot = _render_plots(chart_data, out)
        machine = _science_machine(inputs, plot)
        markdown = _science_markdown(machine)
    md_bytes = markdown.encode('utf-8')
    json_bytes = canonical_json(machine)
    _write(out.with_suffix('.json'), json_bytes)
    _write(out, md_bytes)
    return {'path': str(out), 'sha256': hashlib.sha256(md_bytes).hexdigest(),
            'bytes': len(md_bytes)}
