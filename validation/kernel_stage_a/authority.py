"""Read-only identities and closed, null-blocking launch authority."""
from copy import deepcopy
import decimal
import _decimal
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

BASE='62456be3e6e6cbe3b2a058bd38ade744edc3c628'
PACKAGE='15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050'
LIMITS=dict(outer_seconds=600,candidate_seconds=90,incremental_worker_bytes=201326592,
            output_bytes=67108864,free_disk_bytes=4294967296,numerical_threads=4,
            factors=6,reads=768)
PENDING=('implementation_review','represented_rate_records','static_exports',
         'resource_measurement_boundary_seal','fresh_launch_snapshot','output_directory')


class AuthorityError(ValueError): pass


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def digest(value): return hashlib.sha256(canonical(value)).hexdigest()
def file_hash(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()


def runtime():
    return dict(python=sys.version,executable=str(Path(sys.executable).resolve()),
                executable_sha256=file_hash(Path(sys.executable).resolve()),implementation=platform.python_implementation(),
                decimal_version=decimal.__version__,libmpdec_version=decimal.__libmpdec_version__,
                decimal_extension=_decimal.__file__,decimal_extension_sha256=file_hash(_decimal.__file__),
                byteorder=sys.byteorder,machine=platform.machine(),context='80/160 ROUND_HALF_EVEN Emin=-999999999 Emax=999999999 traps=InvalidOperation,DivisionByZero,Overflow')


def observe(root):
    root=Path(root)
    paths=['docs/amendments/2026-10-18-kernel-projection-adoption.md',
           'docs/amendments/2026-10-18-kernel-projection-diagnostic.md',
           'docs/research/task18-kernel-reader-fixture-manifest-draft.md',
           'docs/research/task18-kernel-projection-source-acceptance.json',
           'docs/research/task18-kernel-projection-source-review.md',
           'docs/research/task18-kernel-projection-source-verification.json',
           'docs/research/task18-kernel-reader-fixture-manifest-fix1-review.md',
           'docs/research/task18-training-horizon-statistics.json','requirements.lock',
           'famjet/readers/kernel_projection.py','famjet/models/kernel_read_model.py','famjet/eval/isolation.py']
    paths += [str(p.relative_to(root)) for p in sorted((root/'validation/kernel_stage_a').glob('*.py'))]
    paths += ['validation/kernel_stage_a/fixture-descriptors.json','validation/kernel_stage_a/frozen-training-metadata.json']
    package={str(p.relative_to(root)):file_hash(p) for p in sorted((root/'famjet').rglob('*.py'))}
    memory={k:v for k,v in package.items() if k.startswith('famjet/memory/')}
    previous=json.loads((root/'docs/research/task18-kernel-projection-source-verification.json').read_bytes())
    if any(memory[k]!=v['current_sha256'] for k,v in previous['identities']['memory_components'].items()):
        raise AuthorityError('unchanged-kernel proof mismatch')
    return dict(source_full_git=git(root,'rev-parse','HEAD'),package_hash=digest(package),
                adopted_amendment=dict(path=paths[1],sha256=file_hash(root/paths[1]),adoption_date='2026-10-18',
                                       adoption_record=paths[0],adoption_record_sha256=file_hash(root/paths[0])),
                dependency_lock_hash=file_hash(root/'requirements.lock'),python_decimal_runtime_identity=runtime(),
                files={p:file_hash(root/p) for p in paths},unchanged_kernel_components=memory,
                snapshot_schema=dict(schema_version=1,format='famjet.snapshot',format_version=1,registry_version=2),
                host_identity=dict(node=platform.node(),system=platform.system(),release=platform.release(),machine=platform.machine()))


def unit_metadata(parent,writer_hash,canonical_rates,transported_rates):
    """Root-adopted deterministic U metadata, never a new fit/cache signature."""
    if len(canonical_rates)!=len(transported_rates) or any(x!=8*y for x,y in zip(canonical_rates,transported_rates)):
        raise ValueError('dimensionless rate transport mismatch')
    derived=deepcopy(parent)
    derived['fit_provenance']['t_ref']*=8
    derived['fit_provenance']['writer_hash']=writer_hash
    audit=dict(kind='DERIVED unit transport',parent=deepcopy(parent),parent_sha256=digest(parent),
               physical_time_multiplier=8,physical_rate_divisor=8,prior_scale_multiplier=8,
               canonical_rate_hex=[v.hex() for v in canonical_rates],transported_rate_hex=[v.hex() for v in transported_rates],
               source_writer_hash=parent['fit_provenance']['writer_hash'],derived_writer_hash=writer_hash,
               derived_sha256=digest(derived))
    return derived,audit


def _null(value):
    if value is None: return True
    if isinstance(value,dict): return any(_null(v) for v in value.values())
    if isinstance(value,list): return any(_null(v) for v in value)
    return False


def verify(seal,root,*,fresh=True,output_initialized=False):
    """Must finish BEFORE importing backend, constructing state or evaluating math."""
    if type(seal) is not dict or set(seal)!={'version','scope','observed','pending','limits','root_stage_A_release'}:
        raise AuthorityError('closed seal schema mismatch')
    if _null(seal): raise AuthorityError('null execution authority blocks work')
    if seal['version']!=1 or seal['scope']!='Task18 kernel Stage A only' or seal['limits']!=LIMITS:
        raise AuthorityError('seal scope/limits mismatch')
    if type(seal['pending']) is not dict or set(seal['pending'])!=set(PENDING):
        raise AuthorityError('pending authority schema mismatch')
    current=observe(root)
    if current!=seal['observed'] or current['package_hash']!=PACKAGE:
        raise AuthorityError('observed source/package/runtime/helper identity mismatch')
    if git(root,'status','--porcelain'): raise AuthorityError('clean sealed source required')
    p=seal['pending']
    review=p['implementation_review']
    if type(review) is not dict or set(review)!={'path','sha256','approved'} or review['approved'] is not True or file_hash(Path(root)/review['path'])!=review['sha256']:
        raise AuthorityError('implementation review mismatch')
    for field in ('represented_rate_records','static_exports'):
        records=p[field]
        expected={'jet','bank'} if field=='represented_rate_records' else {f'{family}:{rho.hex()}' for family,rho in __import__('validation.kernel_stage_a.descriptors',fromlist=['candidates']).candidates()}
        if type(records) is not dict or set(records)!=expected: raise AuthorityError(field+' inventory mismatch')
        for record in records.values():
            if type(record) is not dict or set(record)!={'path','sha256'} or file_hash(Path(root)/record['path'])!=record['sha256']:
                raise AuthorityError(field+' hash mismatch')
    boundary=p['resource_measurement_boundary_seal']
    expected_boundary={'baseline':'post-import/pre-allocation per worker','absolute_rss':True,'process_tree_rss':True,
                       'sequential_workers':True,'outputs_include_temporaries':True}
    if type(boundary) is not dict or set(boundary)!=set(expected_boundary)|{'allocation_start_monotonic','deadline_monotonic','allocation_start_utc_epoch','setup_ledger'} or any(boundary[k]!=v for k,v in expected_boundary.items()):
        raise AuthorityError('resource boundary mismatch')
    if boundary['deadline_monotonic']!=boundary['allocation_start_monotonic']+600 or not boundary['allocation_start_monotonic']<=time.monotonic()<boundary['deadline_monotonic']:
        raise AuthorityError('original 600s allocation deadline expired/mismatched')
    setup=boundary['setup_ledger']
    if type(setup) is not dict or set(setup)!={'path','sha256'} or file_hash(Path(root)/setup['path'])!=setup['sha256']:
        raise AuthorityError('setup ledger mismatch')
    prior=json.loads((Path(root)/setup['path']).read_bytes())
    if prior.get('actual_factor_constructions')!=6 or prior.get('actual_reads')!=0 or prior.get('allocation_start_monotonic')!=boundary['allocation_start_monotonic']:
        raise AuthorityError('one-time setup counts/boundary mismatch')
    if (prior.get('package_hash')!=PACKAGE or prior.get('source_full_git')!=current['source_full_git'] or
        prior.get('static_exports')!=p['static_exports'] or prior.get('represented_rate_records')!=p['represented_rate_records'] or
        type(prior.get('output_directory')) is not str or not Path(prior['output_directory']).is_absolute() or
        not Path(prior['output_directory']).is_dir() or
        type(prior.get('output_peak_bytes')) is not int or not 0<=prior['output_peak_bytes']<=LIMITS['output_bytes'] or
        type(prior.get('incremental_worker_peak_bytes')) is not int or not 0<=prior['incremental_worker_peak_bytes']<=LIMITS['incremental_worker_bytes']):
        raise AuthorityError('setup source/output/resource identity mismatch')
    release=seal['root_stage_A_release']
    body={k:v for k,v in seal.items() if k!='root_stage_A_release'}
    if type(release) is not dict or set(release)!={'approved','scope','payload_sha256','ruling_path','ruling_sha256'} or release['approved'] is not True or release['scope']!='Stage A scientific execution' or release['payload_sha256']!=digest(body) or file_hash(Path(root)/release['ruling_path'])!=release['ruling_sha256']:
        raise AuthorityError('root execution release mismatch')
    launch=p['fresh_launch_snapshot']
    if type(launch) is not dict or set(launch)!={'utc_epoch','free_disk_bytes','power_observation','host_identity'}:
        raise AuthorityError('fresh launch schema mismatch')
    out=Path(p['output_directory'])
    if not out.is_absolute() or not out.parent.is_dir(): raise AuthorityError('fresh absolute output directory required')
    if output_initialized:
        if not out.is_dir() or {p.name for p in out.iterdir()}!={'stdout.log','stderr.log'}:
            raise AuthorityError('initialized output boundary mismatch')
    elif out.exists(): raise AuthorityError('fresh absolute output directory required')
    if fresh and (not 0<=time.time()-launch['utc_epoch']<=60 or launch['host_identity']!=current['host_identity'] or
                  launch['free_disk_bytes']<LIMITS['free_disk_bytes'] or shutil.disk_usage(out.parent).free<LIMITS['free_disk_bytes']):
        raise AuthorityError('fresh launch/disk prerequisite failed')
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
        if os.environ.get(key) not in ('1','2','3','4'): raise AuthorityError('explicit <=four numerical threads required: '+key)
    return p
