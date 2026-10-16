"""Observed-event UCI501 preparation; civil hours, sealed labels, no scoring.

Only the small manifest is public evidence. Protected labels are prepared to
ignored local arrays and the development iterator refuses that split. This is
an administrative access boundary, not an authorization mechanism.
"""
import csv
from dataclasses import asdict
from datetime import datetime, timedelta
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

import numpy as np
import torch

from famjet.artifacts import atomic_json
from famjet.config import config_documents_equal, RunConfig, validate_config
from famjet.eval.metrics import fit_target_statistics
from famjet.eval.oracle import exact_targets
from famjet.provenance import canonical_hash, canonical_json
from famjet.types import Episode, EventBatch, QueryBatch

LEGACY_VERSION = 'beijing_observed_v1'
VERSION = 'beijing_observed_v2_targets'
QUERY_GRID = 'station_mean_contrast_widths_1_6_24_72_168_v1'
STATIONS = ('Aotizhongxin', 'Changping', 'Dingling', 'Dongsi', 'Guanyuan', 'Gucheng',
            'Huairou', 'Nongzhanguan', 'Shunyi', 'Tiantan', 'Wanliu', 'Wanshouxigong')
HEADER = 'No,year,month,day,hour,PM2.5,PM10,SO2,NO2,CO,O3,TEMP,PRES,DEWP,RAIN,wd,WSPM,station'.split(',')
INNER = 'PRSA2017_Data_20130301-20170228.zip'
ARCHIVE_SHA256 = 'b04da438b2f331ac0ffd45aebdfec0d20d2367feb5f6948c4b1f7ce1191e33c4'
INNER_SHA256 = 'd1b9261c54132f04c374f762f1e5e512af19f95c95fd6bfa1e8ac7e927e3b0b8'
EPOCH = datetime(2013, 3, 1)
TIME_UNIT = 'dataset_local_civil_hour_since_2013-03-01'
MAX_ARCHIVE_BYTES = 32 << 20
MAX_DECODED_BYTES = 128 << 20
ATTRIBUTION = {
    'citation': 'Chen, S. (2017). Beijing Multi-Site Air Quality [Dataset]. UCI Machine Learning Repository.',
    'doi': '10.24432/C5RK5G', 'source_record': 'R16',
    'catalog': 'https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data',
    'url': 'https://archive.ics.uci.edu/static/public/501/beijing%2Bmulti%2Bsite%2Bair%2Bquality%2Bdata.zip',
    'license': 'CC BY 4.0', 'license_url': 'https://creativecommons.org/licenses/by/4.0/',
    'license_evidence': 'docs/research/2026-10-16-source-verification.md',
    'changes': 'Select PM2.5; omit missing observations; sort station-hour events; training-only scaling; chronological histories and exact oracle labels.',
}


def _sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _tick(text):
    return int((datetime.fromisoformat(text) - EPOCH).total_seconds() // 3600)


def _date(tick):
    return (EPOCH + timedelta(hours=int(tick))).date().isoformat()


def _safe_members(archive, remaining):
    names = set()
    members = archive.infolist()
    if len(members) > 64:
        raise ValueError('archive has too many members')
    for item in members:
        path = PurePosixPath(item.filename)
        mode = item.external_attr >> 16
        if (not item.filename or path.is_absolute() or '..' in path.parts or
                '\\' in item.filename or ':' in item.filename or '\x00' in item.filename or
                item.filename in names or stat.S_ISLNK(mode) or item.flag_bits & 1):
            raise ValueError('unsafe archive member')
        names.add(item.filename)
        remaining -= item.file_size
        if item.file_size < 0 or remaining < 0:
            raise ValueError('archive decoded-byte budget exceeded')
    return members, remaining


def load_observations(archive: Path, byte_budget: int):
    """Stream safe nested CSVs without extraction; audit ordering before sorting.

    This low-level reader permits partial station fixtures. prepare_beijing also
    enforces the pinned official identity, station inventory and full hourly grid.
    """
    archive = Path(archive)
    if not 0 < byte_budget <= MAX_DECODED_BYTES:
        raise ValueError('decoded-byte budget must be in (0,128MiB]')
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError('archive transfer-byte budget exceeded')
    times, keys, values = [], [], []
    audits, seen = {}, set()
    with zipfile.ZipFile(archive) as outer:
        outer_members, remaining = _safe_members(outer, byte_budget)
        if INNER not in {m.filename for m in outer_members}:
            raise ValueError('named PRSA nested archive missing')
        inner_bytes = outer.read(INNER)  # bounded above; CRC is checked by zipfile
        with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
            members, remaining = _safe_members(inner, remaining)
            for item in members:
                if item.is_dir():
                    continue
                filename = PurePosixPath(item.filename).name
                station = next((s for s in STATIONS if filename == f'PRSA_Data_{s}_20130301-20170228.csv'), None)
                if station is None or station in audits:
                    raise ValueError('unexpected or duplicate station file')
                count = missing = backwards = gaps = 0
                previous = None
                low = high = None
                with inner.open(item) as stream:
                    reader = csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig', newline=''))
                    if reader.fieldnames != HEADER:
                        raise ValueError('unexpected Beijing schema')
                    for row in reader:
                        if None in row or any(v is None for v in row.values()) or row['station'] != station:
                            raise ValueError('malformed station row')
                        dt = datetime(*(int(row[k]) for k in ('year','month','day','hour')))
                        tick = int((dt - EPOCH).total_seconds() // 3600)
                        if not 0 <= tick < 35064:
                            raise ValueError('station timestamp outside dataset')
                        if (station,tick) in seen:
                            raise ValueError('duplicate station-hour')
                        seen.add((station,tick))
                        if previous is not None:
                            backwards += tick < previous
                            gaps += tick != previous + 1
                        previous = tick
                        low = tick if low is None else min(low,tick)
                        high = tick if high is None else max(high,tick)
                        count += 1
                        if row['PM2.5'].strip() in {'NA',''}:
                            missing += 1
                            continue
                        value = float(row['PM2.5'])
                        if not np.isfinite(value):
                            raise ValueError('nonfinite observed PM2.5')
                        times.append(tick); keys.append(STATIONS.index(station)); values.append(value)
                audits[station] = {'rows':count,'missing_pm25':missing,'observed':count-missing,
                                   'first_tick':low,'last_tick':high,'backward_steps':backwards,
                                   'nonhourly_steps':gaps,'duplicates':0}
    order = np.lexsort((keys,times))
    data = {'times':np.asarray(times,dtype=np.int64)[order],
            'keys':np.asarray(keys,dtype=np.int64)[order],
            'values':np.asarray(values,dtype=np.float64)[order]}
    return data, {'schema':HEADER,'stations':audits,'rows':sum(a['rows'] for a in audits.values()),
                  'missing_pm25':sum(a['missing_pm25'] for a in audits.values()),'observed':len(times),
                  'decoded_bytes':byte_budget-remaining,
                  'inner_bytes':len(inner_bytes),'inner_sha256':hashlib.sha256(inner_bytes).hexdigest(),
                  'outer_members':[{'path':i.filename,'bytes':i.file_size} for i in outer_members],
                  'inner_members':[{'path':i.filename,'bytes':i.file_size} for i in members]}


def block_inventory():
    """14d blocks anchored to each original split, including calibration exclusion."""
    result = {}
    for parent,start,end in [('training','2013-03-01','2014-09-01'),
                              ('development','2014-09-01','2015-01-01'),
                              ('test','2015-01-01','2017-03-01')]:
        first,last = _tick(start),_tick(end)
        names = ['development_fit','development_calibration'] if parent == 'development' else [parent]
        for name in names:
            result[name] = {'start': '2014-11-01' if name == 'development_calibration' else start,
                            'end': '2014-11-01' if name == 'development_fit' else end,
                            'parent_split':parent,'blocks':[], 'trailing_hours':(last-first)%336,
                            'boundary_excluded_hours':0}
        for index,a in enumerate(range(first,last-335,336)):
            b = a+336
            if parent == 'development' and a < _tick('2014-11-01') < b:
                result['development_fit']['boundary_excluded_hours'] += 336
                continue
            name = ('development_fit' if b <= _tick('2014-11-01') else 'development_calibration') if parent == 'development' else parent
            result[name]['blocks'].append({'history_id':f'{parent}:{index:04d}', 'split':name,
                'index':index,'start':_date(a),'end':_date(b),'start_tick':a,'end_tick':b,
                'cluster_28d':f'{parent}:28d:{index//2:04d}', 'cluster_56d':f'{parent}:56d:{index//4:04d}'})
    # The development tail belongs only to calibration, not twice to both subsets.
    result['development_fit']['trailing_hours'] = 0
    return result


def fit_normalization(data):
    selected = data['values'][(data['times'] >= 0) & (data['times'] < _tick('2014-09-01'))]
    if not len(selected):
        raise ValueError('no observed training measurements')
    mean, scale = float(selected.mean()), float(selected.std(ddof=0))
    if not np.isfinite(mean) or not np.isfinite(scale) or scale <= 0:
        raise ValueError('training normalization requires finite nonconstant observations')
    return {'split':'training','source':'all_observed_training_events','count':len(selected),
            'mean':mean,'scale':scale,'variance_ddof':0,'clipping':False}


def _queries(block):
    keys, tasks, starts, ends = [], [], [], []
    for key in range(12):
        for width in (1,6,24,72,168):
            for task in ('mean','contrast'):
                keys.append(key); tasks.append(task)
                start = 0 if width == 168 else 1
                starts.append(start); ends.append(start+width)
    n = len(keys)
    return QueryBatch((block['history_id'],),torch.arange(n)[None],
        torch.full((1,n),block['end_tick'],dtype=torch.int64),torch.tensor([keys]),
        torch.eye(12,dtype=torch.float32)[keys][None],(tuple(tasks),),
        torch.tensor([starts],dtype=torch.float64),torch.tensor([ends],dtype=torch.float64),
        torch.ones((1,n),dtype=torch.bool),torch.tensor([n]))


def make_episode(data, block, normalization, *, normalized):
    mask = (data['times'] >= block['start_tick']) & (data['times'] < block['end_tick'])
    times,keys,values = (data[k][mask] for k in ('times','keys','values'))
    if normalized:
        values = (values-normalization['mean'])/normalization['scale']
    n = len(times)
    events = EventBatch((block['history_id'],),torch.arange(n)[None],torch.from_numpy(times)[None],
        torch.from_numpy(keys)[None],torch.eye(12,dtype=torch.float32)[keys][None],
        torch.from_numpy(values.copy())[None,:,None],torch.tensor([n]),torch.ones((1,n),dtype=torch.bool),
        torch.ones((1,n,1),dtype=torch.bool),TIME_UNIT)
    queries = _queries(block)
    target = exact_targets(events,queries)
    return Episode(events,queries,target.target,target.supported,
        {**block,'target_semantics':'observed_event_targets_v2','preparation_version':VERSION,'query_grid_version':QUERY_GRID,
         'normalization':'training_standardized' if normalized else 'raw_micrograms_per_m3',
         'target_valid':target.metadata['target_valid'], 'observed_counts':target.metadata['observed_counts'],
         'last_event_to_query_hours':block['end_tick']-int(times[-1]) if n else None,
         'status':'ok' if bool(target.supported.all()) else 'contains_unsupported_queries'})


def _seal(payload):
    return {**json.loads(canonical_json(payload)),'manifest_hash':canonical_hash(payload)}


def _verify_manifest(path):
    manifest = json.loads(Path(path).read_text())
    if manifest.get('manifest_hash') != canonical_hash({k:v for k,v in manifest.items() if k != 'manifest_hash'}):
        raise ValueError('Beijing manifest checksum mismatch')
    if manifest.get('preparation_version') not in (LEGACY_VERSION,VERSION) or manifest.get('query_grid_version') != QUERY_GRID:
        raise ValueError('unknown Beijing preparation/query version')
    return manifest


def _is_unavailable(payload):
    """Recognize only our explicit non-scientific availability record."""
    if not isinstance(payload,dict) or payload.get('status') != 'unavailable':
        return False
    required = {'schema_version','dataset','status','reason','archive','real_transfer','substitution'}
    if (set(payload) != required or payload['schema_version'] != 1 or payload['dataset'] != 'beijing'
            or payload['reason'] != 'local_archive_missing' or payload['real_transfer'] != 'untested'
            or payload['substitution'] is not False or not isinstance(payload['archive'],str)):
        raise ValueError('invalid Beijing unavailable record')
    return True


def prepare_beijing(archive: Path, out: Path, config: RunConfig) -> dict:
    """Pin and validate the official asset, prepare every split, seal protected files.

    No protected target summary, model output, score or method selection is
    computed. All raw/normalized labels are produced only by exact_targets.
    """
    validate_config(config)
    if config.data.length != 336:
        raise ValueError('Beijing requires 336-hour histories')
    if (config.data.key_dim,config.data.value_dim,config.data.key_features) != (12,1,'one_hot'):
        raise ValueError('Beijing requires 12 one-hot keys and scalar values')
    if config.data.beijing is None or config.data.beijing.query_grid_version != QUERY_GRID or config.data.queries_per_history != 120:
        raise ValueError('Beijing requires registered 120-query grid')
    archive,out = Path(archive),Path(out)
    if config.data.generator_version!=VERSION: raise ValueError('legacy target preparation requires original historical source')
    bulk = Path(config.data.beijing.derived_path)
    budget = config.resources.asset_disk_budget_bytes
    if budget < MAX_DECODED_BYTES:
        raise ValueError('declare at least 128MiB asset disk budget')
    out.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(out.parent).free < budget:
        raise ValueError('insufficient free capacity for declared asset disk budget')
    if archive.stat().st_size != 8192212 or _sha(archive) != ARCHIVE_SHA256:
        raise ValueError('official Beijing archive identity mismatch')
    previous = out.read_bytes() if out.exists() else None
    existing = None
    if previous is not None and not _is_unavailable(json.loads(previous)):
        existing = _verify_manifest(out)
        if not config_documents_equal(existing['config'], asdict(config)) or existing['archive']['sha256'] != _sha(archive):
            raise ValueError('existing Beijing manifest differs; choose a new output path')
        missing = False
        for info in existing['splits'].values():
            for block in info['blocks']:
                path = (out.parent/block['artifact']).resolve()
                if path.parent != bulk.resolve() or path.suffix != '.npz':
                    raise ValueError('unsafe Beijing artifact path')
                if path.exists():
                    if _sha(path) != block['sha256']:
                        raise ValueError('existing Beijing bulk artifact checksum mismatch')
                else:
                    missing = True
        if not missing:
            return existing
    data,audit = load_observations(archive,MAX_DECODED_BYTES)
    if (audit['inner_sha256'] != INNER_SHA256 or set(audit['stations']) != set(STATIONS)
            or audit['rows'] != 420768 or audit['missing_pm25'] != 8739 or audit['observed'] != 412029
            or any(a['rows'] != 35064 or a['first_tick'] != 0 or a['last_tick'] != 35063
                   or a['backward_steps'] or a['nonhourly_steps'] for a in audit['stations'].values())):
        raise ValueError('official Beijing structure/count audit mismatch')
    normalization = fit_normalization(data)
    inventory = block_inventory()
    bulk.mkdir(parents=True,exist_ok=True)
    # Stage the complete candidate before publishing arrays or availability state.
    # A sealed inventory is immutable; missing local bytes are reconstructible.
    with tempfile.TemporaryDirectory(prefix='.prepare-',dir=bulk) as directory:
        staging = Path(directory)
        staged = []
        for split,info in inventory.items():
            used = np.zeros(len(data['times']),dtype=bool)
            for block in info['blocks']:
                mask = (data['times'] >= block['start_tick']) & (data['times'] < block['end_tick'])
                used |= mask
                raw = make_episode(data,block,normalization,normalized=False)
                normalized = make_episode(data,block,normalization,normalized=True)
                path = bulk / f"{block['history_id'].replace(':','-')}.npz"
                temp_path = staging/path.name
                with temp_path.open('wb') as temporary:
                    np.savez_compressed(temporary,times=data['times'][mask],keys=data['keys'][mask],
                        raw_values=data['values'][mask],labels_raw=raw.labels.numpy(),
                        labels_normalized=normalized.labels.numpy(),supported=raw.supported.numpy(),
                        observed_counts=np.asarray(raw.metadata['observed_counts'],dtype=np.int64))
                    temporary.flush()
                    os.fsync(temporary.fileno())
                staged.append((temp_path,path))
                block['artifact'] = os.path.relpath(path,out.parent)
                block['sha256'] = _sha(temp_path)
                block['observed_events'] = int(mask.sum())
                # Structural count only: do not summarize protected labels/support.
            lo,hi = _tick(info['start']),_tick(info['end'])
            in_split = (data['times'] >= lo)&(data['times'] < hi)
            info['observed_events_in_calendar_range'] = int(in_split.sum())
            info['included_observed_events'] = int(used.sum())
            info['excluded_observed_events_in_calendar_range'] = int((in_split & ~used).sum())
        training = [make_episode(data,b,normalization,normalized=True) for b in inventory['training']['blocks']]
        statistics = fit_target_statistics(training)
        result = _seal({'schema_version':1,'status':'prepared','dataset':'beijing',
            'preparation_version':VERSION,'target_semantics':'observed_event_targets_v2','query_grid_version':QUERY_GRID,
            'query_convention':{'width_hours':[1,6,24,72,168],'tasks':['mean','contrast'],
                'recent_age_start_hours':'1 except width168 uses0','age_end':'start+width; exclusive',
                'contrast_older':'[start+width,start+2*width)','query_time':'block_end',
                'decay':'temporary_no_write_from_last_event'},
            'time_convention':{'unit':TIME_UNIT,'timezone':'unspecified dataset-local civil hours; no timezone/DST conversion'},
            'attribution':ATTRIBUTION,'archive':{'path':str(archive),'bytes':archive.stat().st_size,'sha256':_sha(archive)},
            'audit':audit,'normalization':normalization,'training_target_statistics':statistics,
            'config':asdict(config),'bulk_root':os.path.relpath(bulk,out.parent),'splits':inventory,
            'protected_access':{'status':'sealed_preparation_only','split':'test',
                'outputs_inspected':False,'iterator':'refuses_test',
                'future_gate':'authorized_frozen_manifest_runner_required; preparation seals do not establish scientific preregistration'}})
        if existing is not None and existing != result:
            raise ValueError('regenerated Beijing inventory differs from sealed manifest')
        # Validate every staged byte and collision before publishing any new file.
        for temporary,path in staged:
            if path.exists() and _sha(path) != _sha(temporary):
                raise ValueError('existing Beijing bulk artifact checksum mismatch')
        current = out.read_bytes() if out.exists() else None
        if current != previous:
            raise ValueError('Beijing manifest changed during preparation')
        published = []
        try:
            for temporary,path in staged:
                try:
                    os.link(temporary,path)  # same filesystem; never replace a good file
                    published.append(path)
                except FileExistsError:
                    if _sha(path) != _sha(temporary):
                        raise ValueError('existing Beijing bulk artifact checksum mismatch')
            if existing is None:
                atomic_json(out,result)  # old unavailable record survives until success
        except BaseException:
            for path in published:
                path.unlink(missing_ok=True)
            raise
        return existing if existing is not None else result


def iter_beijing_episodes(manifest: Path, split: str):
    """Yield normalized development/training episodes; refuse protected access."""
    if split == 'test':
        raise ValueError('protected test requires a later authorized frozen-manifest runner')
    if split not in {'training','development_fit','development_calibration'}:
        raise ValueError('unknown Beijing split')
    manifest = Path(manifest)
    payload = _verify_manifest(manifest)
    if payload['preparation_version']!=VERSION: raise ValueError('legacy target labels cannot supply current scientific episodes; v2 preparation pending')
    for block in payload['splits'][split]['blocks']:
        path = (manifest.parent/block['artifact']).resolve()
        # Paths are constrained to the configured bulk directory, including .. relpaths.
        root = (manifest.parent/payload['bulk_root']).resolve()
        if path.parent != root or path.suffix != '.npz' or _sha(path) != block['sha256']:
            raise ValueError('unsafe or modified Beijing artifact')
        with np.load(path,allow_pickle=False) as arrays:
            data = {'times':arrays['times'],'keys':arrays['keys'],'values':arrays['raw_values']}
            ep = make_episode(data,block,payload['normalization'],normalized=True)
            if not np.array_equal(ep.labels.numpy(),arrays['labels_normalized'],equal_nan=True):
                raise ValueError('Beijing oracle labels do not replay')
            yield ep
