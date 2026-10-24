"""Closed primary-reader dimensions and retained source identities."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import torch

from famjet.eval.isolation import _reconstruct
from famjet.eval.state_io import tensor_from_record
from famjet.models._schema import training_metadata

ROOT = Path(__file__).resolve().parents[2]
PLAN = 'docs/research/task18-kernel-stage-b-panel04-evidence/preparation/plan.json'
METADATA = 'validation/kernel_stage_a/frozen-training-metadata.json'
METADATA_SHA = '9ca422cc04f35de1a94bf65a579f37be5122a382cb635c47e7d39d49fa92509c'
TARGET_SHA = '0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21'
RATE_SHA = {'jet': '007f3cdbc32407f1a905026bc5a5033c82ab0003e328cc8359b0674f4b167a2b',
            'bank': 'cb374d6be7c72999da674a24e3099e97208c29af275173c9fbfad78356723baf'}
WRITER_SHA = {'jet': '6bc455ca97aadfac1e08df5a6b0164746e88381a7f0e0f01ba803aecba4de648',
              'bank': '534888f230076d997f8929ff44ad56bbf2aeb380ba393178f245e5e7f9c9ea3e'}


def _bytes(path, expected):
    raw = (ROOT / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'source SHA mismatch: {path}')
    return raw


@dataclass(frozen=True)
class ReaderSpec:
    family: str
    access: str
    width: int

    def __post_init__(self):
        if (self.family, self.access, self.width) not in {
            (f, a, w) for f in ('jet', 'bank') for a, w in (('C', 128), ('C', 558), ('F', 256))
        }:
            raise ValueError('unsupported primary reader specification')

    @property
    def input_dim(self):
        return 92 if self.access == 'C' else 1172

    @property
    def parameter_count(self):
        d, w = self.input_dim, self.width
        return (d + 1)*w + (w + 1)*w + (w + 1)*8

    @property
    def dense_macs(self):
        d, w = self.input_dim, self.width
        return d*w + w*w + w*8

    @property
    def feature_order(self):
        if self.access == 'F':
            memory = ('z[B,1,J,16,9]', 'h[B,1,4,16,9]') if self.family == 'jet' else ('z[B,1,8,16,9]',)
        else:
            memory = ('u[8]', 'h[8]', 'z', 'b') if self.family == 'jet' else ('u[8]', 'z')
        return memory + ('p[16]', 'mean', 'contrast', 'age_start/t_ref', 'age_end/t_ref')


def pinned_source(family):
    """Resolve first family candidate and verify all family entries agree on kernel bytes."""
    if family not in WRITER_SHA:
        raise ValueError('unsupported family')
    plan = json.loads((ROOT / PLAN).read_bytes())
    candidates = [c for c in plan['candidates'] if c['family'] == family]
    if not candidates:
        raise ValueError('missing retained candidate')
    first = candidates[0]
    for candidate in candidates:
        if candidate['writer_sha256'] != WRITER_SHA[family] or candidate['rates'] != first['rates']:
            raise ValueError('family kernel/rate disagreement')
        raw = _bytes(candidate['static']['path'], candidate['static']['sha256'])
        if len(raw) != candidate['static']['bytes']:
            raise ValueError('static length mismatch')
        static = json.loads(raw)
        if static['schema']['kernel'] != json.loads(_bytes(first['static']['path'], first['static']['sha256']))['schema']['kernel']:
            raise ValueError('family kernel static disagreement')
    rate_ref = first['rates']
    if rate_ref['sha256'] != RATE_SHA[family]:
        raise ValueError('retained rate identity mismatch')
    rate_raw = _bytes(rate_ref['path'], rate_ref['sha256'])
    if len(rate_raw) != rate_ref['bytes']:
        raise ValueError('rate length mismatch')
    rates = torch.tensor([[float.fromhex(x) for x in json.loads(rate_raw)]], dtype=torch.float64)
    metadata = json.loads(_bytes(METADATA, METADATA_SHA))[family]
    provenance, statistics = training_metadata(metadata['fit_provenance'], metadata['target_statistics'], 8)
    if provenance['writer_hash'] != WRITER_SHA[family] or provenance['target_hash'] != TARGET_SHA or provenance['t_ref'] != 1.:
        raise ValueError('frozen target provenance mismatch')
    kernel_static = json.loads(_bytes(first['static']['path'], first['static']['sha256']))['schema']['kernel']
    schema = kernel_static['schema']
    if (schema['key_dim'], schema['value_dim'], schema['eps'], schema['support_floor'], schema['t_ref'], schema['rate_source']) != (16, 8, 1e-8, 1e-12, 1., None):
        raise ValueError('fixed kernel settings mismatch')
    retained_rates = tensor_from_record(kernel_static['weights']['rates'])
    if not torch.equal(rates, retained_rates):
        raise ValueError('rate/static mismatch')
    source = dict(family=family, writer_hash=WRITER_SHA[family], rate_sha256=RATE_SHA[family],
                  target_hash=TARGET_SHA, metadata_sha256=METADATA_SHA,
                  history_identity_hash=provenance['history_identity_hash'], t_ref=1.0)
    return kernel_static, source, statistics


def load_pinned_kernel(family):
    static, source, _ = pinned_source(family)
    kernel = _reconstruct(static)
    if kernel._parameter_hash() != source['writer_hash'] or kernel.rates.dtype != torch.float64 or kernel.rates.device.type != 'cpu':
        raise ValueError('represented kernel identity mismatch')
    return kernel
