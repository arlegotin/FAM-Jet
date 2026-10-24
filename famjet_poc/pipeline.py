"""Finite, byte-audited stage execution and one-command PoC orchestration."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from famjet.provenance import canonical_hash, canonical_json


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _atomic(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.e4-', delete=False) as stream:
        tmp = Path(stream.name)
        stream.write(canonical_json(body))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def _files(directory):
    return {str(path.relative_to(directory)): {'sha256': _sha(path), 'bytes': path.stat().st_size}
            for path in sorted(directory.rglob('*')) if path.is_file()}


class StageLedger:
    """Keep failed attempts and skip only hash-verified completed stages."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'run-ledger.json'
        if not self.path.exists():
            _atomic(self.path, {'schema_version': 1, 'kind': 'famjet_e4_stage_ledger', 'generations': []})

    def _read(self):
        value = json.loads(self.path.read_bytes())
        if value.get('schema_version') != 1 or value.get('kind') != 'famjet_e4_stage_ledger' or type(value.get('generations')) is not list:
            raise ValueError('stage ledger schema mismatch')
        prior = '0' * 64
        for index, record in enumerate(value['generations']):
            if (record.get('generation') != index or record.get('prior_sha256') != prior or
                    record.get('entry_sha256') != canonical_hash({key: val for key, val in record.items()
                                                                   if key != 'entry_sha256'})):
                raise ValueError('stage ledger generation hash chain mismatch')
            prior = record['entry_sha256']
        return value

    def _append(self, item):
        value = self._read()
        item['generation'] = len(value['generations'])
        item['prior_sha256'] = (value['generations'][-1]['entry_sha256']
                                if value['generations'] else '0' * 64)
        item['entry_sha256'] = canonical_hash(item)
        value['generations'].append(item)
        _atomic(self.path, value)

    def first_start_epoch(self, name):
        records = [r for r in self._read()['generations']
                   if r['stage'] == name and r['status'] == 'running']
        if not records:
            raise ValueError('stage has no original allocation clock')
        return records[0]['start_epoch_seconds']

    def stage(self, name, inputs, action, *, resume=False, retryable=False,
              monitor=False, monitor_observer=None, monitor_cancel=None):
        if type(name) is not str or not name or '/' in name or name.startswith('.') or not callable(action):
            raise ValueError('valid stage and action required')
        digest = canonical_hash(inputs)
        records = [r for r in self._read()['generations'] if r['stage'] == name]
        completed = [r for r in records if r['status'] == 'completed']
        if records and not resume:
            raise FileExistsError('existing stage requires --resume')
        if completed:
            receipt = completed[-1]
            if receipt['input_sha256'] != digest:
                raise ValueError('resumed stage input hash mismatch')
            directory = self.root / name
            if _files(directory) != receipt['output_files']:
                raise ValueError('resumed stage output hash mismatch')
            return receipt['result']
        if records and records[-1]['status'] == 'running' and retryable and resume:
            interrupted = records[-1]
            directory = self.root / name
            self._append({'stage': name, 'status': 'failed',
                          'input_sha256': interrupted['input_sha256'],
                          'start_monotonic': interrupted['start_monotonic'],
                          'end_monotonic': time.monotonic(),
                          'start_epoch_seconds': interrupted['start_epoch_seconds'],
                          'end_epoch_seconds': time.time(),
                          'output_files': _files(directory), 'result': None,
                          'error': 'interrupted public stage; original allocation retained'})
            records = [r for r in self._read()['generations'] if r['stage'] == name]
        if records and not retryable:
            raise ValueError('failed/incomplete stage needs dated amendment, not routine resume')
        directory = self.root / name
        if records:
            last = records[-1]
            if last['input_sha256'] != digest or last['status'] != 'failed' or _files(directory) != last['output_files']:
                raise ValueError('failed public stage input/output hash mismatch')
        else:
            if directory.exists():
                raise ValueError('unreceipted stage directory exists')
            directory.mkdir()
        started = time.monotonic()
        epoch = time.time()
        self._append({'stage': name, 'status': 'running', 'input_sha256': digest,
                      'start_monotonic': started, 'start_epoch_seconds': epoch,
                      'deadline_epoch_seconds': inputs.get('deadline_epoch_seconds') if type(inputs) is dict else None})
        try:
            if monitor:
                from .resources import LiveStageGuard
                original = inputs.get('allocation') if type(inputs) is dict else None
                if type(original) is not dict:
                    raise ValueError('monitored stage requires frozen allocation')
                first = self.first_start_epoch(name)
                remaining = first + original['max_wall_seconds'] - time.time()
                if remaining <= 0:
                    raise RuntimeError('original monitored stage deadline expired')
                attempt = sum(r['stage'] == name and r['status'] == 'running'
                              for r in self._read()['generations']) - 1
                active = {**original, 'max_wall_seconds': remaining}
                live = LiveStageGuard(directory, active,
                        directory / f'live-guard-attempt-{attempt:03d}.json',
                        observer=monitor_observer, cancel=monitor_cancel)
                with live:
                    result = action(directory)
                if type(result) is dict:
                    result = {**result, 'outer_live_guard_ref': live.receipt_ref}
            else:
                result = action(directory)
            if result is None:
                raise ValueError('stage returned no completion receipt')
            files = _files(directory)
            if not files:
                raise ValueError('stage has no durable outputs')
            self._append({'stage': name, 'status': 'completed', 'input_sha256': digest,
                          'start_monotonic': started, 'end_monotonic': time.monotonic(),
                          'start_epoch_seconds': epoch, 'end_epoch_seconds': time.time(),
                          'output_files': files, 'result': result, 'error': None})
            return result
        except BaseException as exc:
            self._append({'stage': name, 'status': 'failed', 'input_sha256': digest,
                          'start_monotonic': started, 'end_monotonic': time.monotonic(),
                          'start_epoch_seconds': epoch, 'end_epoch_seconds': time.time(),
                          'output_files': _files(directory), 'result': None,
                          'error': f'{type(exc).__name__}: {exc}'})
            raise


def observe_resources(root):
    """Observe host headroom and the current inherited process tree."""
    disk = shutil.disk_usage(root)
    import sys
    if sys.platform == 'darwin':
        free_output = subprocess.run(['vm_stat'], check=True, capture_output=True, text=True).stdout
        page_size = int(free_output.split('page size of ')[1].split(' bytes')[0])
        pages = {}
        for line in free_output.splitlines():
            if ':' in line:
                key, value = line.split(':', 1)
                number = value.strip().rstrip('.')
                if number.isdigit():
                    pages[key.strip()] = int(number)
        free_ram = page_size * (pages.get('Pages free', 0) + pages.get('Pages speculative', 0))
    else:
        lines = Path('/proc/meminfo').read_text().splitlines()
        free_ram = int(next(line.split()[1] for line in lines if line.startswith('MemAvailable:'))) * 1024
    output = subprocess.run(['ps', '-axo', 'pid=,ppid=,rss='], check=True,
                            capture_output=True, text=True).stdout
    table = {}
    for line in output.splitlines():
        values = line.split()
        if len(values) == 3 and all(value.isdigit() for value in values):
            pid, ppid, rss_kib = map(int, values)
            table[pid] = (ppid, rss_kib * 1024)
    frontier = [os.getpid()]
    members = set(frontier)
    while frontier:
        parent = frontier.pop()
        for pid, (ppid, _) in table.items():
            if ppid == parent and pid not in members:
                members.add(pid)
                frontier.append(pid)
    return {'free_ram_bytes': free_ram, 'free_disk_bytes': disk.free,
            'tree_rss_bytes': sum(table[pid][1] for pid in members if pid in table),
            'now_epoch_seconds': time.time(), 'child_processes': len(members) - 1,
            'descendant_pids': sorted(members - {os.getpid()}),
            'run_output_bytes': sum(path.stat().st_size for path in Path(root).rglob('*') if path.is_file())}


def admit_resources(observed, allocation):
    required_o = {'free_ram_bytes', 'free_disk_bytes', 'tree_rss_bytes', 'now_epoch_seconds'}
    required_a = {'max_incremental_rss_bytes', 'max_output_bytes', 'deadline_epoch_seconds'}
    if type(observed) is not dict or type(allocation) is not dict or not required_o <= set(observed) or not required_a <= set(allocation):
        raise ValueError('complete resource observation/allocation required')
    if any(type(observed[k]) not in (int, float) or not math.isfinite(observed[k]) or observed[k] < 0 for k in required_o):
        raise ValueError('finite resource observation required')
    if any(type(allocation[k]) not in (int, float) or not math.isfinite(allocation[k]) or allocation[k] <= 0 for k in required_a):
        raise ValueError('finite resource allocation required')
    if observed['now_epoch_seconds'] >= allocation['deadline_epoch_seconds']:
        raise RuntimeError('allocation deadline expired')
    if observed['tree_rss_bytes'] > allocation['max_incremental_rss_bytes']:
        raise RuntimeError('current process-tree RSS allocation exceeded')
    if observed['free_ram_bytes'] < 2 * 2**30 or allocation['max_incremental_rss_bytes'] > min(1.5 * 2**30, .75 * observed['free_ram_bytes']):
        raise RuntimeError('RAM admission failed')
    if observed['free_disk_bytes'] < 4 * 2**30 or allocation['max_output_bytes'] > observed['free_disk_bytes'] - 4 * 2**30:
        raise RuntimeError('disk admission failed')
    return {'status': 'admitted', 'observed': observed, 'allocation': allocation,
            'reserve_fraction': .25, 'rss_scope': 'current_parent_plus_live_descendants'}


def _study_inputs(root):
    from .study import study_manifest
    repo = Path(__file__).resolve().parent.parent
    config = json.loads((repo / 'docs/research/e2e-study-config.json').read_bytes())
    manifest = study_manifest(config)
    policy = json.loads((repo / 'docs/research/e2e-development-resource-policy.json').read_bytes())
    if policy['expected_e3_source_sha256'] != manifest['e3_source_sha256']:
        raise ValueError('accepted E3 source changed')
    return manifest, policy


def k16_probe_allocation(manifest, policy):
    """Create a fresh source-matched probe; historical receipts are provenance only."""
    if (type(manifest) is not dict or type(policy) is not dict or
            manifest.get('e3_source_sha256') != policy.get('expected_e3_source_sha256') or
            type(manifest.get('manifest_sha256')) is not str or
            len(manifest['manifest_sha256']) != 64 or
            policy.get('probe_ref_status') !=
            'historical_pre_worker_fix; requires fresh matching actual CLI probe'):
        raise ValueError('current E3 manifest and historical probe policy required')
    return {'schema_version': 1, 'phase': 'probe',
            'manifest_sha256': manifest['manifest_sha256'],
            'allocation_id': 'e4-k16-current-source-probe-v1',
            'max_wall_seconds': 120, 'max_disk_bytes': 134217728,
            'max_rss_bytes': 1610612736}


def remaining_probe_allocation(original, first_start_epoch, now_epoch):
    """Charge every probe attempt to the first attempt's absolute deadline."""
    if (type(original) is not dict or original.get('phase') != 'probe' or
            type(original.get('max_wall_seconds')) not in (int, float) or
            type(first_start_epoch) not in (int, float) or
            type(now_epoch) not in (int, float) or
            not all(math.isfinite(v) for v in
                    (original['max_wall_seconds'], first_start_epoch, now_epoch))):
        raise ValueError('original finite probe allocation clock required')
    remaining = first_start_epoch + original['max_wall_seconds'] - now_epoch
    if remaining <= 0:
        raise RuntimeError('original probe allocation deadline expired')
    return {**original, 'max_wall_seconds': remaining}


def execute_study_probe(ledger, name, manifest, original_allocation, directory):
    """Run E3's actual probe in a new durable attempt under the first deadline."""
    from .study import probe_feasibility
    attempt = sum(r['stage'] == name and r['status'] == 'running'
                  for r in ledger._read()['generations']) - 1
    first = ledger.first_start_epoch(name)
    allocation_now = remaining_probe_allocation(original_allocation, first, time.time())
    probe_dir = Path(directory) / f'attempt-{attempt:03d}' / 'probe'
    result = probe_feasibility(manifest, probe_dir, allocation_now)
    if result.get('status') != 'measured' or result.get('feasible') is not True:
        raise RuntimeError('current-source resource probe not feasible')
    path = probe_dir / 'probe.json'
    return {'status': 'measured', 'probe_path': str(path),
            'probe_sha256': _sha(path),
            'e3_source_sha256': manifest['e3_source_sha256'],
            'original_start_epoch_seconds': first,
            'attempt': attempt, 'attempt_allocation': allocation_now}


def stress_inventory():
    """Public, diagnostic-only 8 robustness modes plus mean-only boundary."""
    from famjet.data._processes import REGIMES, ROBUSTNESS
    root = 2026102401910
    items = []
    for robustness in ('standard', 'zipf', 'lognormal_gaps', 'heavy_gaps',
                       'heavy_noise', 'fast_resets', 'broad_periods', 'unseen_reversals'):
        if robustness not in ROBUSTNESS:
            raise ValueError('historical robustness law changed')
        for regime in REGIMES:
            for index in range(4):
                items.append({'history_id': f'diagnostic-{robustness}-{regime}-{index:02d}',
                              'namespace': 'development_calibration', 'seed': root,
                              'length': 512, 'queries_per_history': 8,
                              'population': 'primary', 'robustness': robustness,
                              'regime': regime, 'tasks': ['mean', 'contrast']})
    for regime in REGIMES:
        for index in range(4):
            items.append({'history_id': f'diagnostic-boundary-{regime}-{index:02d}',
                          'namespace': 'development_calibration', 'seed': root,
                          'length': 512, 'queries_per_history': 8,
                          'population': 'boundary', 'robustness': 'standard',
                          'regime': regime, 'tasks': ['mean']})
    if len(items) != 144 or len({item['history_id'] for item in items}) != 144:
        raise ValueError('diagnostic inventory changed')
    return items


def diagnostic_policy(episodes, tasks, manifest_hash):
    """Record a missing-task diagnostic without replacing a history."""
    from .study import freeze_score_policy
    episodes = list(episodes)
    history_ids = [ep.events.history_ids[0] for ep in episodes]
    try:
        policy = freeze_score_policy(iter(episodes), tasks=tasks,
                                     manifest_hash=manifest_hash)
    except ValueError as exc:
        if 'primary history lacks eligible task' not in str(exc):
            raise
        return {'status': 'failed_missing_primary_task', 'reason': str(exc),
                'history_ids': history_ids, 'policy': None}
    return {'status': 'entered', 'reason': None,
            'history_ids': history_ids, 'policy': policy}


def secondary_ledger(stress_results):
    """Fixed task scope, with null metrics for unsupported or unentered cells."""
    if type(stress_results) is not list:
        raise ValueError('stress result list required')
    ledger = []
    unsupported = (
        ('latest', 'K16/V8', 'No qualified latest-task fitting/output/scoring bridge'),
        ('presence', 'K16/V8', 'No qualified binary output/scoring bridge'),
        ('interval_support', 'K16/V8', 'No calibrated support logit or qualified output bridge'),
        ('change_sign', 'K16/V8', 'No qualified change-sign output/scoring bridge'),
        ('corrected_categorical_v32', 'K16/V32', 'No V32 checkpoint or qualified categorical reader'),
        ('random_binding_v32', 'K16/V32', 'No V32 checkpoint or qualified categorical reader'),
    )
    for name, shape, reason in unsupported:
        ledger.append({'name': name, 'shape': shape, 'status': 'unsupported',
                       'reason': reason, 'metrics': None, 'method_refs': None,
                       'source': 'famjet_poc/models.py;famjet_poc/study.py'})
    for name, mode in [('sharp_windows', 'boundary'),
                       *[(robustness, robustness) for robustness in
                         ('standard', 'zipf', 'lognormal_gaps', 'heavy_gaps',
                          'heavy_noise', 'fast_resets', 'broad_periods', 'unseen_reversals')]]:
        entries = [item for item in stress_results if item.get('mode') == mode]
        if not entries:
            status, reason, metrics, refs = 'unentered', 'diagnostic not executed', None, None
        elif any(item['status'] != 'ok' for item in entries):
            status, reason, metrics, refs = 'failed', '; '.join(sorted({
                item.get('reason') or item['status'] for item in entries if item['status'] != 'ok'})), None, None
        else:
            status, reason = 'implemented/scored', None
            metrics = {item['method']: item['summary'] for item in entries}
            refs = {item['method']: item['rows_ref'] for item in entries}
        ledger.append({'name': name, 'shape': 'K16/V8', 'status': status,
                       'reason': reason, 'metrics': metrics, 'method_refs': refs,
                       'source': 'famjet.data.synthetic.generate_episode;famjet_poc.study.evaluate_panel'})
    return ledger


def timing_accuracy_admission(method_names):
    names = tuple(method_names)
    if not names or len(names) != len(set(names)) or any(type(name) is not str or not name for name in names):
        raise ValueError('finite named timing methods required')
    return {'accuracy_satisfied': {name: False for name in names},
            'reason': 'no application tolerance specified',
            'break_even_claim': None,
            'interpretation': 'constraint_unspecified_not_empirical_failure'}


def run_stress(selected_models, worker_limits, allocation, out):
    """Evaluate the unchanged historical generator without fitting or selection."""
    from dataclasses import asdict, replace
    from famjet.config import load_config
    from famjet.data.synthetic import generate_episode
    from .comparators import build_controls
    from .models import load_model
    from .study import evaluate_panel
    from .transfer import _cached_factory, evaluate_equivalent_control
    from .protected import admit_cell
    if set(selected_models) != {'jet', 'bank'}:
        raise ValueError('frozen selected pair required for diagnostics')
    models = {name: load_model(Path(ref['path']), ref['sha256']) for name, ref in selected_models.items()}
    if any(model.shape.to_json() != {'key_dim': 16, 'value_dim': 8} for model in models.values()):
        raise ValueError('stress requires K16/V8 selected pair')
    controls = build_controls(models['jet'].shape, 9345, models['jet'].target_statistics,
                              2026102401910)
    methods = {**models, **{name: item['method'] for name, item in controls.items()},
               'laguerre': models['jet']}
    inventory = stress_inventory()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    def guard():
        return admit_cell(out, allocation, started,
                          tree_rss_bytes=observe_resources(out)['tree_rss_bytes'])
    guard()
    _atomic(out / 'inventory.json', {'schema_version': 1, 'status': 'predeclared_public_diagnostic',
                                     'inventory': inventory, 'inventory_sha256': canonical_hash(inventory)})
    base = load_config(Path(__file__).resolve().parent.parent / 'configs/smoke.yaml')
    results = []
    for mode in [*dict.fromkeys(item['robustness'] for item in inventory), 'boundary']:
        subset = [item for item in inventory if (item['population'] == 'boundary' if mode == 'boundary'
                 else item['population'] == 'primary' and item['robustness'] == mode)]
        raw_inventory = []
        def generated():
            for item in subset:
                generator = replace(base.data.generator, namespace='development_calibration',
                                    population=item['population'], regime=item['regime'],
                                    robustness=item['robustness'])
                data = replace(base.data, generator_version='initial_spec_v2_targets',
                               length=512, queries_per_history=8, generator=generator)
                config = replace(base, data=data)
                episode = generate_episode(config, 2026102401910, item['history_id'])
                raw_inventory.append({'history_id': item['history_id'],
                                      'config_sha256': canonical_hash(asdict(config)),
                                      'hashes': episode.metadata['hashes'],
                                      'diagnostics': episode.metadata['diagnostics']})
                yield episode
        factory, cache_entries, cache_bytes = _cached_factory(generated(),
                                                               out / mode / 'raw-cache',
                                                               256 * 2**20)
        guard()
        _atomic(out / mode / 'raw-inventory.json',
                {'schema_version': 1, 'mode': mode, 'records': raw_inventory,
                 'cache_entries': cache_entries, 'cache_bytes': cache_bytes,
                 'records_sha256': canonical_hash(raw_inventory)})
        tasks = ('mean',) if mode == 'boundary' else ('mean', 'contrast')
        entry = diagnostic_policy(factory(), tasks,
                                  canonical_hash({'mode': mode, 'inventory': subset}))
        if entry['status'] != 'entered':
            for method in methods:
                results.append({'mode': mode, 'method': method,
                                'status': entry['status'], 'reason': entry['reason'],
                                'history_ids': entry['history_ids'], 'rows_ref': None,
                                'summary': None, 'costs': None, 'tasks': list(tasks)})
            continue
        policy = entry['policy']
        for method, model in methods.items():
            guard()
            phase_allocation = {**allocation, 'phase': 'development',
                                'manifest_sha256': policy['manifest_hash']}
            if method == 'laguerre':
                result = evaluate_equivalent_control(model, factory, policy,
                         models['jet'].target_statistics, out / mode / method,
                         phase_allocation, worker_limits)
            else:
                result = evaluate_panel(model, factory, policy, models['jet'].target_statistics,
                                        method, out / mode / method, phase_allocation, worker_limits)
            results.append({'mode': mode, 'method': method, 'status': result['summary']['status'],
                            'rows_ref': result['rows_ref'], 'summary': result['summary'],
                            'costs': result['costs'], 'tasks': list(tasks)})
            guard()
    _atomic(out / 'results.json', {'schema_version': 1, 'kind': 'famjet_e4_public_stress',
                                   'inventory_sha256': canonical_hash(inventory),
                                   'results': results,
                                   'secondary_task_ledger': secondary_ledger(results)})
    guard()
    return {'status': 'completed', 'results_path': str(out / 'results.json'),
            'results_sha256': _sha(out / 'results.json'), 'history_count': 144}


def run(out, resume=False):
    """Execute fixed public fitting, freeze, panels, transfer and report in order."""
    from .study import probe_feasibility, run_development, study_manifest
    from .protected import (FrozenStudyRef, ReleaseRef, _accepted_qualification,
                            _accepted_calibration, calibration_costs,
                            evaluate_cell, freeze_study,
                            grant_for, infer_release, seal_release)
    from .transfer import (ModeRefs, PrefreezeTransferInputs, evaluate_real_mode,
                           fit_transfer_modes, load_bound_modes, seal_real_release,
                           probe_transfer_profile, verify_transfer_probe)
    from . import transfer as transfer_module
    from .contracts import PopulationSpec, ShapeSpec
    from .models import load_model
    from .inference import STRATA
    out = Path(out)
    ledger = StageLedger(out)
    manifest, policy = _study_inputs(out)
    repository = Path(__file__).resolve().parent.parent
    master_path = out / 'run-policy.json'
    if master_path.exists():
        master = json.loads(master_path.read_bytes())
        if not resume or master.get('study_manifest_sha256') != manifest['manifest_sha256']:
            raise ValueError('existing run policy requires matching --resume')
    else:
        if resume:
            raise ValueError('nothing to resume')
        free_disk = shutil.disk_usage(out).free
        output_envelope = min(32 * 2**30, free_disk - 4 * 2**30)
        if output_envelope < 2 * 2**30:
            raise RuntimeError('whole-run output cannot preserve four GiB disk reserve')
        master = {'schema_version': 1, 'study_manifest_sha256': manifest['manifest_sha256'],
                  'start_epoch_seconds': time.time(), 'global_wall_seconds': 21600,
                  'resource_envelope_bytes': 1610612736,
                  'output_envelope_bytes': output_envelope,
                  'profile': 'scientific_study'}
        _atomic(master_path, master)
    global_deadline = master['start_epoch_seconds'] + master['global_wall_seconds']

    def admit(max_output=2 * 2**30, max_rss=1610612736):
        observed = observe_resources(out)
        if observed['run_output_bytes'] > master['output_envelope_bytes']:
            raise RuntimeError('whole-run output envelope exhausted')
        return admit_resources(observed,
                               {'max_incremental_rss_bytes': max_rss,
                                'max_output_bytes': max_output,
                                'deadline_epoch_seconds': global_deadline})

    def preflight(directory):
        admission = admit()
        qualification = _accepted_qualification()
        calibration = _accepted_calibration()
        body = {'reader': qualification, 'inference': calibration,
                'study_manifest_sha256': manifest['manifest_sha256'],
                'status': 'accepted_reused_evidence', 'admission': admission,
                'calibration_validation_costs': calibration_costs()}
        _atomic(directory / 'preflight.json', body)
        return body
    preflight_allocation = {'allocation_id': 'e4-preflight-v1',
                            'max_wall_seconds': 300,
                            'max_disk_bytes': 64 * 2**20,
                            'max_rss_bytes': 1610612736}
    ledger.stage('preflight', {'study_manifest_sha256': manifest['manifest_sha256'],
                               'accepted_inference_acceptance_sha256': _sha(repository / 'docs/research/e2e-inference-qualification.json'),
                               'allocation': preflight_allocation},
                 preflight, resume=resume, monitor=True)
    probe16_allocation = k16_probe_allocation(manifest, policy)
    def probe16(directory):
        admit(134217728)
        return execute_study_probe(ledger, 'probe_k16', manifest,
                                   probe16_allocation, directory)
    probe16 = ledger.stage('probe_k16', {'manifest_sha256': manifest['manifest_sha256'],
                                        'e3_source_sha256': manifest['e3_source_sha256'],
                                        'allocation': probe16_allocation},
                           probe16, resume=resume, retryable=True, monitor=True)
    if _sha(probe16['probe_path']) != probe16['probe_sha256'] or (
            probe16['e3_source_sha256'] != manifest['e3_source_sha256']):
        raise ValueError('current-source K16 probe bytes/source changed')
    probe_ref = {'path': probe16['probe_path'], 'sha256': probe16['probe_sha256']}
    allocation = {'schema_version': 1, 'phase': 'development',
                  'manifest_sha256': manifest['manifest_sha256'],
                  'allocation_id': policy['allocation_policy_id'],
                  'max_wall_seconds': policy['max_wall_seconds'],
                  'max_disk_bytes': policy['max_disk_bytes'],
                  'max_rss_bytes': policy['max_rss_bytes'],
                  'probe_ref': probe_ref}
    def develop(directory):
        admission = admit(policy['max_disk_bytes'], policy['max_rss_bytes'])
        _atomic(directory / 'manifest.json', manifest)
        journal = run_development(manifest, directory / 'study', allocation)
        if journal.get('status') != 'complete':
            raise RuntimeError('development did not complete')
        result = {'status': 'complete', 'journal_path': str(directory / 'study' / 'development.json'),
                  'journal_sha256': _sha(directory / 'study' / 'development.json'), 'admission': admission}
        _atomic(directory / 'result.json', result)
        return result
    developed16 = ledger.stage('development_k16', {'manifest_sha256': manifest['manifest_sha256'],
                                      'allocation': allocation}, develop, resume=resume,
                               retryable=True, monitor=True)
    journal16 = json.loads(Path(developed16['journal_path']).read_bytes())
    if _sha(developed16['journal_path']) != developed16['journal_sha256']:
        raise ValueError('K16 development journal hash mismatch')

    from .cache import load_episode_cache, episode_factory
    from .comparators import build_controls
    from .timing import benchmark
    selected16_for_timing = {name: entry['fit_ref'] for name, entry in journal16['selected'].items()}
    timing_models = {name: load_model(Path(ref['path']), ref['sha256'])
                     for name, ref in selected16_for_timing.items()}
    timing_controls = build_controls(ShapeSpec(16, 8), 9345,
                                     timing_models['jet'].target_statistics,
                                     2026102401906)
    timing_methods = {**timing_models,
                      **{name: item['method'] for name, item in timing_controls.items()}}
    timing_admission = timing_accuracy_admission(timing_methods)
    workload_ids = [item['history_id'] for item in manifest['development_inventory'][:12]]
    timing_manifest_sha = canonical_hash({'selected': selected16_for_timing,
                                          'workload_ids': workload_ids,
                                          'development_cache_sha256': journal16['development_cache_sha256']})
    timing_policy = {'warmups': 3, 'blocks': 12, 'query_counts': [1, 8, 64],
                     'seed': 2026102401907,
                     'worker_limits': manifest['config']['worker_limits'],
                     'timeout_seconds': 120.,
                     'accuracy_satisfied': timing_admission['accuracy_satisfied'],
                     'manifest_sha256': timing_manifest_sha,
                     'baseline_method': 'exact'}
    timing_allocation = {'schema_version': 1, 'phase': 'timing',
                         'manifest_sha256': timing_manifest_sha,
                         'allocation_id': 'e4-paired-timing-v1',
                         'max_wall_seconds': 1800, 'max_disk_bytes': 1 * 2**30,
                         'max_rss_bytes': 1610612736}
    def timing_action(directory):
        admit(1 * 2**30)
        cache_root = Path(developed16['journal_path']).parent / 'development-cache'
        cache = load_episode_cache(cache_root, journal16['development_cache_sha256'])
        workloads = list(episode_factory(cache, workload_ids)())
        result = benchmark(timing_methods, workloads, timing_policy,
                           directory / 'benchmark', timing_allocation)
        _atomic(directory / 'accuracy-admission.json', timing_admission)
        return {'status': 'measured', 'timing_path': str(directory / 'benchmark' / 'timing.json'),
                'timing_sha256': _sha(directory / 'benchmark' / 'timing.json'),
                'accuracy_admission': timing_admission,
                'break_even_queries': result['break_even_queries']}
    ledger.stage('timing_k16', {'timing_manifest_sha256': timing_manifest_sha,
                                 'policy': timing_policy, 'allocation': timing_allocation},
                 timing_action, resume=resume, monitor=True)

    config12 = {**manifest['config'], 'shape': ShapeSpec(12, 1).to_json(),
                'training_seed': 2026102401803, 'development_seed': 2026102401804}
    manifest12 = study_manifest(config12)
    probe12_allocation = {'schema_version': 1, 'phase': 'probe',
                          'manifest_sha256': manifest12['manifest_sha256'],
                          'allocation_id': 'e4-k12-probe-v1', 'max_wall_seconds': 120,
                          'max_disk_bytes': 134217728, 'max_rss_bytes': 1610612736}
    def probe12(directory):
        admit(134217728)
        return execute_study_probe(ledger, 'probe_k12', manifest12,
                                   probe12_allocation, directory)
    p12 = ledger.stage('probe_k12', {'manifest_sha256': manifest12['manifest_sha256'],
                                    'allocation': probe12_allocation}, probe12,
                       resume=resume, retryable=True, monitor=True)
    if _sha(p12['probe_path']) != p12['probe_sha256']:
        raise ValueError('K12 probe bytes changed')
    probe12 = json.loads(Path(p12['probe_path']).read_bytes())
    forecast = probe12['forecast']
    estimated = (forecast['estimated_cache_construction_seconds'] +
                 forecast['estimated_cold_worker_seconds'] +
                 forecast['estimated_development_stream_seconds'] +
                 forecast['estimated_training_fit_seconds'])
    if not math.isfinite(estimated) or estimated <= 0:
        raise ValueError('K12 forecast invalid')
    wall12 = min(7200, max(1800, math.ceil((2 * estimated + 180) / 300) * 300))
    allocation12 = {'schema_version': 1, 'phase': 'development',
                    'manifest_sha256': manifest12['manifest_sha256'],
                    'allocation_id': 'e4-k12-measured-v1', 'max_wall_seconds': wall12,
                    'max_disk_bytes': 2 * 2**30, 'max_rss_bytes': 1610612736,
                    'probe_ref': {'path': p12['probe_path'], 'sha256': p12['probe_sha256']}}
    def develop12(directory):
        admission = admit()
        _atomic(directory / 'manifest.json', manifest12)
        journal = run_development(manifest12, directory / 'study', allocation12)
        if journal.get('status') != 'complete':
            raise RuntimeError('K12 development did not complete')
        result = {'status': 'complete', 'journal_path': str(directory / 'study' / 'development.json'),
                  'journal_sha256': _sha(directory / 'study' / 'development.json'), 'admission': admission}
        _atomic(directory / 'result.json', result)
        return result
    developed12 = ledger.stage('development_k12', {'manifest_sha256': manifest12['manifest_sha256'],
                                                    'allocation': allocation12},
                               develop12, resume=resume, retryable=True, monitor=True)
    if _sha(developed12['journal_path']) != developed12['journal_sha256']:
        raise ValueError('K12 development journal hash mismatch')
    journal12 = json.loads(Path(developed12['journal_path']).read_bytes())
    selected12 = {name: entry['fit_ref'] for name, entry in journal12['selected'].items()}
    for name, ref in selected12.items():
        model = load_model(Path(ref['path']), ref['sha256'])
        if model.shape != ShapeSpec(12, 1) or model.spec.family != name:
            raise ValueError('K12 selected checkpoint mismatch')

    beijing = repository / 'configs/manifests/beijing_v2_targets.json'
    beijing_sha = _sha(beijing)
    if beijing_sha != '5bf4ead56d916538944ed7c3145e2800d281f567c19c1bc204233044d832d21c':
        raise ValueError('accepted Beijing v2 manifest changed')
    real_probe_allocation = {'schema_version': 1, 'phase': 'probe',
                             'manifest_sha256': beijing_sha,
                             'allocation_id': 'e4-real-profile-probe-v1',
                             'max_wall_seconds': 300, 'max_disk_bytes': 256 * 2**20,
                             'max_rss_bytes': 1610612736}
    def real_probe_action(directory):
        admit(256 * 2**20)
        attempt = sum(r['stage'] == 'probe_beijing_fit' and r['status'] == 'running'
                      for r in ledger._read()['generations']) - 1
        allocation_now = remaining_probe_allocation(
            real_probe_allocation, ledger.first_start_epoch('probe_beijing_fit'), time.time())
        probe_ref = probe_transfer_profile(beijing,
                        manifest['config']['worker_limits'], allocation_now,
                        directory / f'attempt-{attempt:03d}')
        return {'status': 'measured', 'probe_ref': probe_ref,
                'attempt': attempt,
                'original_start_epoch_seconds': ledger.first_start_epoch('probe_beijing_fit')}
    real_probe = ledger.stage('probe_beijing_fit',
                 {'beijing_manifest_sha256': beijing_sha,
                  'transfer_source_sha256': _sha(transfer_module.__file__),
                  'allocation': real_probe_allocation},
                 real_probe_action, resume=resume, retryable=True, monitor=True)
    measured_real = verify_transfer_probe(real_probe['probe_ref'], beijing_sha,
                                          manifest['config']['worker_limits'])
    transfer_allocation = {'schema_version': 1, 'phase': 'development',
                           'manifest_sha256': beijing_sha,
                           'allocation_id': 'e4-real-prefreeze-v1',
                           'max_wall_seconds': measured_real['recommended_wall_seconds'],
                           'max_disk_bytes': measured_real['recommended_disk_bytes'],
                           'max_rss_bytes': measured_real['recommended_rss_bytes']}
    prefreeze = PrefreezeTransferInputs(selected12, transfer_allocation,
                                        config12['worker_limits'], 1 * 2**30, beijing_sha,
                                        real_probe['probe_ref'])
    def fit_real(directory):
        admission = admit()
        modes = fit_transfer_modes(prefreeze, beijing, directory / 'modes')
        result = {'status': 'prefreeze_fitted', 'modes_ref': {'path': str(modes.path),
                  'sha256': modes.sha256}, 'live_guard_ref': modes.guard_ref,
                  'real_probe_ref': real_probe['probe_ref'], 'admission': admission}
        _atomic(directory / 'result.json', result)
        return result
    transfer_result = ledger.stage('transfer_fit', {'beijing_manifest_sha256': beijing_sha,
                                 'selected_k12_sha256': canonical_hash(selected12),
                                 'transfer_source_sha256': _sha(transfer_module.__file__),
                                 'real_probe_sha256': real_probe['probe_ref']['sha256'],
                                 'allocation': transfer_allocation}, fit_real, resume=resume,
                                   retryable=False, monitor=True)
    mode_ref = ModeRefs(Path(transfer_result['modes_ref']['path']),
                        transfer_result['modes_ref']['sha256'])
    modes = mode_ref.read()

    selected16 = {name: entry['fit_ref'] for name, entry in journal16['selected'].items()}
    for name, ref in selected16.items():
        model = load_model(Path(ref['path']), ref['sha256'])
        if model.shape != ShapeSpec(16, 8) or model.spec.family != name:
            raise ValueError('K16 selected checkpoint mismatch')
    pair_sha = canonical_hash({name: ref['sha256'] for name, ref in selected16.items()})
    populations = []
    for phase, seed, count in (('pilot', 2026102401902, 16),
                               ('confirmation', 2026102401904, 256),
                               ('replication', 2026102401905, 256)):
        for stratum in STRATA:
            length_text, regime = stratum.split(':', 1)
            length = int(length_text)
            spec = PopulationSpec('poc_numeric_v1', ShapeSpec(16, 8), phase, seed,
                                  (length,), (regime,), 8, 4096)
            populations.append({'phase': phase, 'split': phase,
                                'cell_id': f'{phase}-{length}-{regime}',
                                'spec': spec.to_json(),
                                'episode_ids': [f'{phase}-{length}-{regime}-{i:03d}'
                                                for i in range(count)]})
    from famjet.data import beijing as beijing_core
    beijing_metadata = beijing_core._verify_manifest(beijing)
    test_blocks = beijing_metadata['splits']['test']['blocks']
    test_ids = [item['history_id'] for item in test_blocks]
    real_commitments = {name: canonical_hash(modes[name])
                        for name in ('synthetic_frozen', 'task_adapted')}
    freeze_inputs = {'profile': 'study', 'model_pair_sha256': pair_sha,
                     'selected_models': selected16, 'selected_k12_models': selected12,
                     'study_k16_sha256': developed16['journal_sha256'],
                     'study_k12_sha256': developed12['journal_sha256'],
                     'transfer_modes_path': str(mode_ref.path),
                     'transfer_modes_sha256': mode_ref.sha256,
                     'transfer_fit_guard_ref': transfer_result['live_guard_ref'],
                     'transfer_fit_allocation': transfer_allocation,
                     'transfer_probe_ref': real_probe['probe_ref'],
                     'beijing_manifest_sha256': beijing_sha,
                     'beijing_test_ids': test_ids,
                     'beijing_array_inventory': {name: [
                         {'history_id': item['history_id'], 'sha256': item['sha256']}
                         for item in beijing_metadata['splits'][name]['blocks']]
                         for name in ('training', 'development_fit', 'development_calibration', 'test')},
                     'real_model_commitments': real_commitments,
                     'populations': populations,
                     'public_training_inventory_sha256': manifest['training_inventory_hash'],
                     'public_development_inventory_sha256': manifest['development_inventory_hash'],
                     'strata': list(STRATA), 'stratum_weights': [1 / 12] * 12,
                     'calibration': _accepted_calibration(),
                     'nuisance_authorization': {'root': 2026102401902,
                         'max_histories': 192, 'selection_allowed': False},
                     'outcome_policy': {'primary_tasks': ['mean', 'contrast'],
                                        'fallback': 'training_prior_full_loss',
                                        'missing_primary_task': 'block_panel'},
                     'resource_policy': master,
                     'protected_cell_allocation_template': {
                         'max_wall_seconds': 600, 'max_disk_bytes': 256 * 2**20,
                         'max_rss_bytes': 1610612736},
                     'real_method_allocation_template': {
                         'max_wall_seconds': 1200, 'max_disk_bytes': 512 * 2**20,
                         'max_rss_bytes': 1610612736},
                     'worker_limits': manifest['config']['worker_limits'],
                     'expected_query_ids': list(range(8)),
                     'control_seed': 2026102401906,
                     'expected_methods': ['jet', 'bank', 'exact', 'recent',
                                          'latest_lru', 'reservoir', 'buckets', 'laguerre'],
                     'expected_protected_run_ids': [
                         item['cell_id'] + '-' + method for item in populations
                         for method in ('jet', 'bank', 'exact', 'recent',
                                        'latest_lru', 'reservoir', 'buckets', 'laguerre')]}
    def freeze_action(directory):
        admit()
        ref = freeze_study(freeze_inputs, directory)
        return {'status': 'frozen', 'path': str(ref.path), 'sha256': ref.sha256,
                'source_sha256': ref.source_sha256,
                'executable_sha256': ref.executable_sha256,
                'calibration_costs_so_far': calibration_costs()}
    freeze_allocation = {'allocation_id': 'e4-runtime-freeze-v1',
                         'max_wall_seconds': 300,
                         'max_disk_bytes': 64 * 2**20,
                         'max_rss_bytes': 1610612736}
    freeze_result = ledger.stage('freeze', {'freeze_input_sha256': canonical_hash(freeze_inputs),
                                            'allocation': freeze_allocation},
                                 freeze_action, resume=resume, monitor=True)
    freeze = FrozenStudyRef(Path(freeze_result['path']), freeze_result['sha256'],
                            freeze_result['source_sha256'], freeze_result['executable_sha256'])
    freeze.read()
    load_bound_modes(mode_ref, freeze)

    stress_allocation = {'schema_version': 1, 'phase': 'development',
                         'manifest_sha256': freeze.sha256,
                         'allocation_id': 'e4-stress-public-v1', 'max_wall_seconds': 1200,
                         'max_disk_bytes': 1 * 2**30, 'max_rss_bytes': 1610612736}
    def stress_action(directory):
        admit(1 * 2**30)
        return run_stress(selected16, manifest['config']['worker_limits'],
                          stress_allocation, directory / 'diagnostic')
    ledger.stage('stress', {'freeze_sha256': freeze.sha256,
                            'inventory_sha256': canonical_hash(stress_inventory()),
                            'allocation': stress_allocation}, stress_action,
                 resume=resume, monitor=True)

    protected_receipts = []
    for item in populations:
        spec = PopulationSpec.from_json(item['spec'])
        cell_name = 'cell-' + item['cell_id']
        phase_allocation = {'schema_version': 1, 'phase': item['phase'],
                            'manifest_sha256': freeze.sha256,
                            'allocation_id': 'e4-' + item['cell_id'],
                            'max_wall_seconds': 600,
                            'max_disk_bytes': 256 * 2**20,
                            'max_rss_bytes': 1610612736}
        def protected_action(directory, item=item, spec=spec, allocation=phase_allocation):
            admit(256 * 2**20)
            previous_costs = len(calibration_costs())
            grant = grant_for(freeze, item['phase'], item['split'], spec, pair_sha)
            cell = {**item, 'models': selected16, 'allocation': allocation,
                    'worker_limits': manifest['config']['worker_limits']}
            receipts = evaluate_cell(freeze, cell, grant, directory / 'runs')
            _atomic(directory / 'receipts.json', receipts)
            return {'status': 'completed', 'receipts': receipts,
                    'receipts_sha256': _sha(directory / 'receipts.json'),
                    'calibration_digest_costs': calibration_costs()[previous_costs:]}
        result = ledger.stage(cell_name, {'freeze_sha256': freeze.sha256,
                                           'cell': item, 'allocation': phase_allocation},
                              protected_action, resume=resume, monitor=True)
        protected_receipts.extend(result['receipts'])

    real_receipts = []
    for mode_name in ('synthetic_frozen', 'task_adapted'):
        pair_commitment = real_commitments[mode_name]
        for family in ('jet', 'bank', 'exact', 'recent', 'latest_lru',
                       'reservoir', 'buckets', 'laguerre'):
            allocation_real = {'schema_version': 1, 'phase': 'test',
                               'manifest_sha256': beijing_sha,
                               'allocation_id': 'e4-beijing-' + mode_name + '-' + family,
                               'max_wall_seconds': 1200,
                               'max_disk_bytes': 512 * 2**20,
                               'max_rss_bytes': 1610612736}
            def real_action(directory, mode_name=mode_name, family=family,
                            allocation_real=allocation_real):
                admit(512 * 2**20)
                previous_costs = len(calibration_costs())
                grant = grant_for(freeze, 'test', 'test', beijing, pair_commitment)
                descriptor = {'mode_name': mode_name, 'modes_ref': transfer_result['modes_ref'],
                              'family': family, 'manifest': str(beijing),
                              'allocation': allocation_real,
                              'worker_limits': manifest['config']['worker_limits'],
                              'freeze_path': str(freeze.path), 'freeze_sha256': freeze.sha256,
                              'source_sha256': freeze.source_sha256,
                              'executable_sha256': freeze.executable_sha256}
                result = evaluate_real_mode(descriptor, grant, directory / 'evaluation')
                result['calibration_digest_costs'] = calibration_costs()[previous_costs:]
                _atomic(directory / 'receipt.json', result)
                return result
            real_receipts.append(ledger.stage('beijing-' + mode_name + '-' + family,
                                 {'freeze_sha256': freeze.sha256, 'mode': mode_name,
                                  'family': family, 'allocation': allocation_real},
                                 real_action, resume=resume, monitor=True))

    def release_action(directory):
        admit()
        release = seal_release(freeze, protected_receipts, directory,
                               expected_methods=tuple(freeze_inputs['expected_methods']))
        real_release = seal_real_release(freeze, mode_ref, real_receipts,
                                         beijing, directory / 'real')
        confirmation = infer_release(freeze, release, 'confirmation')
        replication = infer_release(freeze, release, 'replication')
        _atomic(directory / 'inference.json', {'confirmation': confirmation,
                                                'replication': replication})
        return {'status': 'complete', 'release_path': str(release.path),
                'release_sha256': release.sha256,
                'real_release_path': str(real_release.path),
                'real_release_sha256': real_release.sha256,
                'inference_sha256': _sha(directory / 'inference.json'),
                'real_receipts_sha256': canonical_hash(real_receipts)}
    release_allocation = {'allocation_id': 'e4-release-v1',
                          'max_wall_seconds': 1800,
                          'max_disk_bytes': 512 * 2**20,
                          'max_rss_bytes': 1610612736}
    released = ledger.stage('release', {'freeze_sha256': freeze.sha256,
                                        'protected_receipt_sha256': canonical_hash(protected_receipts),
                                        'real_receipt_sha256': canonical_hash(real_receipts),
                                        'allocation': release_allocation},
                            release_action, resume=resume, monitor=True)
    ReleaseRef(Path(released['release_path']), released['release_sha256'])
    from .report import render_report
    def report_action(directory):
        admit(512 * 2**20)
        reference = render_report(out, directory / 'final.md')
        if reference is None:
            raise RuntimeError('report did not return a content reference')
        if isinstance(reference, dict):
            report_ref = {key: str(value) if isinstance(value, Path) else value
                          for key, value in reference.items()}
        elif hasattr(reference, 'path') and hasattr(reference, 'sha256'):
            report_ref = {'path': str(reference.path), 'sha256': reference.sha256}
        elif isinstance(reference, (str, Path)):
            path = Path(reference)
            report_ref = {'path': str(path), 'sha256': _sha(path)}
        else:
            raise ValueError('report did not return a usable content reference')
        if _sha(report_ref['path']) != report_ref['sha256']:
            raise ValueError('rendered report byte hash mismatch')
        return {'status': 'complete', 'report_ref': report_ref}
    report_allocation = {'allocation_id': 'e4-report-v1',
                         'max_wall_seconds': 1800,
                         'max_disk_bytes': 512 * 2**20,
                         'max_rss_bytes': 1610612736}
    ledger.stage('report', {'release_sha256': released['release_sha256'],
                            'inference_sha256': released['inference_sha256'],
                            'allocation': report_allocation},
                 report_action, resume=resume, monitor=True)
    return out
