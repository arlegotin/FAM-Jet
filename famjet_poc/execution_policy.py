"""Dated whole-run policy and exact public model reproduction admission."""
import hashlib
import json
import math
import os
from pathlib import Path
import time

from famjet.provenance import canonical_hash, canonical_json


ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / 'docs/research/e2e-execution-policy-v2.json'
BASELINE_PATH = ROOT / 'docs/research/e2e-evaluation-v2-selection-baseline.json'
BASELINE_SHA256 = 'dd49488b03f78fb7b0818ed837fd53b6272304c0f8497030b4a239c78c5abe43'
EXPECTED_POLICY = {'schema_version': 1, 'policy_id': 'e2e-measured-execution-v2-20261025',
                   'global_wall_seconds': 28800, 'synthetic_cell_wall_seconds': 1800,
                   'completion_reserve_seconds': 1800,
                   'resource_envelope_bytes': 1610612736,
                   'output_envelope_bytes': 34359738368,
                   'cohort_prefix': 'budget-v2-20261025'}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_execution_policy():
    raw = POLICY_PATH.read_bytes()
    policy = json.loads(raw)
    if (type(policy) is not dict or set(policy) != set(EXPECTED_POLICY) or
            any(type(policy[key]) is not type(expected) or policy[key] != expected
                for key, expected in EXPECTED_POLICY.items())):
        raise ValueError('dated execution policy changed')
    return policy


def new_run_policy(study_manifest_sha256, *, start_epoch_seconds=None):
    policy = load_execution_policy()
    start = time.time() if start_epoch_seconds is None else start_epoch_seconds
    if (type(study_manifest_sha256) is not str or len(study_manifest_sha256) != 64 or
            type(start) not in (int, float) or not math.isfinite(start) or start <= 0):
        raise ValueError('valid original run start and manifest required')
    return {**policy, 'execution_policy_sha256': _sha(POLICY_PATH),
            'study_manifest_sha256': study_manifest_sha256,
            'start_epoch_seconds': start,
            'global_deadline_epoch_seconds': start + policy['global_wall_seconds'],
            'work_deadline_epoch_seconds': (start + policy['global_wall_seconds'] -
                                            policy['completion_reserve_seconds']),
            'profile': 'scientific_study'}


def verify_run_policy(master, study_manifest_sha256):
    expected = (new_run_policy(study_manifest_sha256,
                               start_epoch_seconds=master.get('start_epoch_seconds'))
                if type(master) is dict else {})
    if (type(master) is not dict or set(master) != set(expected) or
            any(type(master[key]) is not type(value) or master[key] != value
                for key, value in expected.items())):
        raise ValueError('run execution policy/source/original deadline mismatch')
    return master


def bind_run_policy(master_path, *, create=False):
    """Keep an independent write-once byte anchor for the first run clock."""
    master_path = Path(master_path)
    raw = master_path.read_bytes()
    master = json.loads(raw)
    verify_run_policy(master, master.get('study_manifest_sha256'))
    expected = {'schema_version': 1, 'kind': 'famjet_run_policy_anchor_v2',
                'run_policy_sha256': hashlib.sha256(raw).hexdigest(),
                'original_start_epoch_seconds': master['start_epoch_seconds'],
                'global_deadline_epoch_seconds': master['global_deadline_epoch_seconds'],
                'work_deadline_epoch_seconds': master['work_deadline_epoch_seconds']}
    anchor = master_path.with_name('run-policy-anchor.json')
    if create:
        with anchor.open('xb') as stream:
            stream.write(canonical_json(expected))
            stream.flush()
            os.fsync(stream.fileno())
    if anchor.read_bytes() != canonical_json(expected):
        raise ValueError('run policy original-clock anchor mismatch')
    return master


def admit_scientific_work(master, declared_ceiling_seconds, *, now_epoch_seconds=None):
    verify_run_policy(master, master.get('study_manifest_sha256'))
    now = time.time() if now_epoch_seconds is None else now_epoch_seconds
    if (type(declared_ceiling_seconds) not in (int, float) or
            not math.isfinite(declared_ceiling_seconds) or declared_ceiling_seconds <= 0 or
            type(now) not in (int, float) or not math.isfinite(now)):
        raise ValueError('finite scientific work ceiling and clock required')
    if now + declared_ceiling_seconds > master['work_deadline_epoch_seconds']:
        raise RuntimeError('scientific work cannot preserve completion reserve')
    return master['work_deadline_epoch_seconds']


def _selected_roles(selected16, selected12, modes):
    return {'k16_jet': selected16['jet'], 'k16_bank': selected16['bank'],
            'k12_jet': selected12['jet'], 'k12_bank': selected12['bank'],
            'real_jet': modes['task_adapted']['jet'],
            'real_bank': modes['task_adapted']['bank']}


def verify_public_selection(selected16, selected12, modes, *,
                            baseline_sha256=BASELINE_SHA256, resolve=Path):
    """Recompute all six public numeric identities; old run files are never read."""
    from .comparators import coordinate_model_sha256
    from .cache import e3_source_sha256
    from .contracts import ShapeSpec
    from .models import load_model

    if baseline_sha256 != BASELINE_SHA256 or _sha(BASELINE_PATH) != BASELINE_SHA256:
        raise ValueError('public selection baseline hash mismatch')
    baseline = json.loads(BASELINE_PATH.read_bytes())
    if (baseline.get('schema_version') != 1 or
            set(baseline.get('roles', {})) != {'k16_jet', 'k16_bank', 'k12_jet',
                                               'k12_bank', 'real_jet', 'real_bank'}):
        raise ValueError('public selection baseline schema mismatch')
    if baseline.get('e3_source_sha256') != e3_source_sha256():
        raise ValueError('public selection baseline E3 source mismatch')
    try:
        roles = _selected_roles(selected16, selected12, modes)
        norm_hash = canonical_hash(modes['normalization'])
    except (KeyError, TypeError) as exc:
        raise ValueError('public selection roles/normalization missing') from exc
    if norm_hash != baseline['real_normalization_sha256']:
        raise ValueError('public real normalization mismatch')
    results = {}
    for role, ref in roles.items():
        expected = baseline['roles'][role]
        model = load_model(resolve(ref['path']), ref['sha256'])
        shape = ShapeSpec(16, 8) if role.startswith('k16_') else ShapeSpec(12, 1)
        if (model.shape != shape or model.shape.to_json() != expected['shape'] or
                model.spec.family != role.split('_')[-1] or
                model.spec.to_json() != expected['reader'] or
                coordinate_model_sha256(model) != expected['numeric_sha256']):
            raise ValueError('public selected numeric/shape/spec identity mismatch: ' + role)
        results[role] = {'model_ref': ref, 'numeric_sha256': expected['numeric_sha256'],
                         'shape': model.shape.to_json(), 'reader': model.spec.to_json()}
    return {'schema_version': 1, 'kind': 'famjet_public_selection_gate',
            'status': 'matched', 'baseline_sha256': BASELINE_SHA256,
            'baseline_e3_source_sha256': baseline['e3_source_sha256'],
            'gate_source_sha256': _sha(__file__),
            'real_normalization_sha256': norm_hash, 'roles': results}


def verify_public_gate_ref(ref, selected16, selected12, modes, *, resolve=Path):
    """Validate gate bytes and every live checkpoint for freeze and copied replay."""
    if type(ref) is not dict or set(ref) != {'path', 'sha256'}:
        raise ValueError('public selection gate reference missing')
    path = resolve(ref['path'])
    if _sha(path) != ref['sha256']:
        raise ValueError('public selection gate bytes changed')
    body = json.loads(path.read_bytes())
    cost = body.get('verification_seconds')
    if type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0:
        raise ValueError('public selection gate verification cost invalid')
    observed = {key: value for key, value in body.items() if key != 'verification_seconds'}
    if observed != verify_public_selection(selected16, selected12, modes, resolve=resolve):
        raise ValueError('public selection gate result mismatch')
    return body
