import time
allocation_start_monotonic = time.monotonic()
allocation_start_utc_epoch = time.time()
deadline = allocation_start_monotonic + 600.0
import hashlib, json, os, pathlib, sys
ROOT = pathlib.Path('/Users/artemlegotin/Documents/git_alter/FAM-Jet')
PREPARATION = pathlib.Path('/ABS/FRESH/task18-kernel-stage-a-setup')
OUT = PREPARATION/'worker-output'
PRELAUNCH = PREPARATION/'prelaunch'
SOURCE_FULL_GIT = 'ROOT_VERIFIED_FINAL_CLEAN_FULL_GIT'
assert PREPARATION.is_absolute() and not PREPARATION.exists() and PREPARATION.parent.is_dir()
assert len(SOURCE_FULL_GIT) == 40 and all(c in '0123456789abcdef' for c in SOURCE_FULL_GIT)
sys.path.insert(0, str(ROOT))
from validation.kernel_stage_a.monitor import supervise, directory_bytes
from validation.kernel_stage_a.commands import vector_hash
worker = r'''
import gc, hashlib, json, math, os, pathlib, sys, time
ROOT = pathlib.Path(sys.argv[1])
SOURCE_FULL_GIT = sys.argv[2]
START = float(sys.argv[3]); UTC = float(sys.argv[4]); DEADLINE = float(sys.argv[5])
sys.path.insert(0, str(ROOT))
OUT = pathlib.Path.cwd()
def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
def durable(path, raw):
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
def event(kind, **fields):
    with (OUT/'setup-events.jsonl').open('ab') as stream:
        stream.write(canonical(dict(kind=kind, monotonic=time.monotonic(), utc_epoch=time.time(), **fields))+b'\n')
        stream.flush(); os.fsync(stream.fileno())
def check():
    if time.monotonic() >= DEADLINE: raise TimeoutError('original setup-plus-Stage-A deadline')
def record(name, value):
    check(); raw=canonical(value); path=OUT/name
    event('serialization_start', name=name, bytes=len(raw))
    durable(path, raw)
    event('serialization_end', name=name, bytes=len(raw))
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())
event('setup_start', allocation_start_monotonic=START, allocation_start_utc_epoch=UTC,
      deadline_monotonic=DEADLINE, source_full_git=SOURCE_FULL_GIT, actual_reads=0)
try:
    event('imports_start')
    import torch
    from famjet.memory.jet import JetMemory
    from famjet.memory.expbank import ExpBankMemory
    from famjet.models.kernel_read_model import KernelReadModel
    from famjet.readers.kernel_projection import FactorApplicabilityError
    from famjet.eval.isolation import export_method
    from validation.kernel_stage_a.descriptors import candidates
    from validation.kernel_stage_a.monitor import record_baseline
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    event('imports_end')
    check()
    baseline=record_baseline(OUT/'monitor-events.jsonl', deadline=DEADLINE)
    with (OUT/'monitor-events.jsonl').open('rb') as stream: os.fsync(stream.fileno())
    event('baseline_recorded', baseline=baseline)
    package={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted((ROOT/'famjet').rglob('*.py'))}
    package_hash=hashlib.sha256(canonical(package)).hexdigest()
    assert package_hash == '15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050'
    metadata_raw=(ROOT/'validation/kernel_stage_a/frozen-training-metadata.json').read_bytes()
    meta=json.loads(metadata_raw)
    event('source_metadata_checked', package_hash=package_hash,
          metadata_sha256=hashlib.sha256(metadata_raw).hexdigest())
    check()
    event('rate_grid_start', family='jet', count=4)
    jet_rates=torch.logspace(math.log10(1/5224), math.log10(1.), 4,
                            dtype=torch.float64).reshape(1,-1).to('cpu')
    event('rate_grid_end', family='jet', count=4)
    event('rate_grid_start', family='bank', count=8)
    bank_rates=torch.logspace(math.log10(1/5224), math.log10(1.), 8,
                             dtype=torch.float64).reshape(1,-1).to('cpu')
    event('rate_grid_end', family='bank', count=8)
    event('kernel_construction_start', family='jet')
    jet=JetMemory(jet_rates,16,8,eps=1e-8,support_floor=1e-12,t_ref=1.,chunk_size=128)
    event('kernel_construction_end', family='jet')
    event('kernel_construction_start', family='bank')
    bank=ExpBankMemory(bank_rates,16,8,eps=1e-8,support_floor=1e-12,t_ref=1.,chunk_size=128,no_decay=False)
    event('kernel_construction_end', family='bank')
    kernels={'jet':jet,'bank':bank}
    for family,kernel in kernels.items():
        assert kernel._parameter_hash() == meta[family]['fit_provenance']['writer_hash']
        assert kernel.t_ref == meta[family]['fit_provenance']['t_ref'] == 1.
    event('both_frozen_writer_hashes_match')
    rates={family:record('rates-'+family+'.json', [v.hex() for v in kernel.rates[0].tolist()])
           for family,kernel in kernels.items()}
    exports={}; outcomes=[]; attempts=0; completed_exports=0
    for index,(family,rho) in enumerate(candidates()):
        check(); key=family+':'+rho.hex()
        attempts+=1
        event('factor_construction_start', candidate=[family,rho.hex()], index=index,
              actual_factor_constructions=attempts)
        started=time.monotonic()
        try:
            model=KernelReadModel(kernels[family],rho,meta[family]['fit_provenance'],
                                  meta[family]['target_statistics'],prior_scale=5224.)
        except FactorApplicabilityError as exc:
            spec=dict(candidate=[family,rho.hex()],status='FAILED',factor_diagnostics=exc.diagnostics)
            outcome=dict(candidate=[family,rho.hex()],status='FAILED',factor_diagnostics=exc.diagnostics)
            event('factor_construction_end', **outcome, seconds=time.monotonic()-started)
        else:
            event('factor_construction_end', candidate=[family,rho.hex()],status='CONSTRUCTED',
                  seconds=time.monotonic()-started)
            event('export_start', candidate=[family,rho.hex()])
            export_started=time.monotonic()
            spec=export_method(model)
            completed_exports+=1
            event('export_end', candidate=[family,rho.hex()], seconds=time.monotonic()-export_started,
                  actual_completed_top_level_exports=completed_exports,
                  source_derived_copy_consequences=dict(kernel_constructor_calls=4,
                      projection_from_statics_calls=2,model_from_statics_calls=2))
            outcome=dict(candidate=[family,rho.hex()],status='EXPORTED')
            del model
        exports[key]=record('factor-'+str(index)+'.json',spec)
        outcomes.append(outcome)
        del spec
        gc.collect()
        event('candidate_setup_end', candidate=[family,rho.hex()])
    assert attempts == 6
    record('setup-worker.json', dict(actual_factor_constructions=attempts,actual_reads=0,
           allocation_start_monotonic=START,allocation_start_utc_epoch=UTC,deadline_monotonic=DEADLINE,
           source_full_git=SOURCE_FULL_GIT,package_hash=package_hash,output_directory=str(OUT),
           represented_rate_records=rates,static_exports=exports,outcomes=outcomes,
           ownership_ledger_calls=0,actual_rate_grid_constructions=2,
           actual_completed_top_level_exports=completed_exports))
    event('setup_worker_completed', actual_factor_constructions=attempts,actual_reads=0)
except BaseException as exc:
    event('setup_worker_failed', exception_type=type(exc).__name__,message=str(exc))
    raise
'''
worker_path=PRELAUNCH/'setup-worker.py'
worker_bytes=worker.encode('utf-8')
worker_sha256=hashlib.sha256(worker_bytes).hexdigest()
command=[sys.executable,'-I','-B',str(worker_path),str(ROOT),SOURCE_FULL_GIT,
         repr(allocation_start_monotonic),repr(allocation_start_utc_epoch),repr(deadline)]
def durable(path, raw):
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
# The parent contains no numerical backend; monitor owns the worker process group.
# Keep a 1MiB finalizer allowance INSIDE the unchanged total64MiB ceiling.
PRELAUNCH.mkdir(parents=True)
sys.stdout=(PRELAUNCH/'parent-stdout.log').open('w', buffering=1)
sys.stderr=(PRELAUNCH/'parent-stderr.log').open('w', buffering=1)
clock=dict(allocation_start_monotonic=allocation_start_monotonic,
           allocation_start_utc_epoch=allocation_start_utc_epoch,deadline_monotonic=deadline,
           source_full_git=SOURCE_FULL_GIT)
raw=canonical(dict(command=command,sha256=vector_hash(command),
                   setup_worker=dict(path=str(worker_path),sha256=worker_sha256),**clock))
assert len(raw)+len(worker_bytes)<1048576
# Flush the fixed reviewed body and its exact short launch evidence before spawn.
durable(PRELAUNCH/'parent-command.py',pathlib.Path(__file__).read_bytes())
durable(worker_path,worker_bytes)
durable(PRELAUNCH/'setup-command.json',raw)
assert hashlib.sha256(worker_path.read_bytes()).hexdigest()==worker_sha256
result=None; parent_failure=None
try:
    if time.monotonic()>=deadline: raise TimeoutError('original deadline expired before setup spawn')
    result=supervise(command,OUT,outer_seconds=deadline-time.monotonic(),deadline=deadline,
                     preparation_output=PRELAUNCH, output_bytes=67108864-1048576,
                     free_disk_bytes=4294967296,incremental_bytes=201326592)
except BaseException as exc:
    parent_failure=dict(exception_type=type(exc).__name__,message=str(exc))
worker_report=OUT/'setup-worker.json'
ledger=json.loads(worker_report.read_bytes()) if worker_report.exists() else dict(actual_reads=0,**clock)
# Missing factor count means INCOMPLETE: never invent six after a kill/failure.
ledger.update(status='COMPLETED' if result and result['status']=='COMPLETED' and
              ledger.get('actual_factor_constructions')==6 and not parent_failure else 'STOPPED',
              output_directory=str(PREPARATION),monitor=result,parent_failure=parent_failure,
              setup_elapsed_at_finalization_start=time.monotonic()-allocation_start_monotonic,
              setup_command_sha256=vector_hash(command),setup_worker_sha256=worker_sha256,
              incremental_worker_peak_bytes=result['incremental_worker_peak_bytes'] if result else None)
if time.monotonic()>=deadline: ledger['status']='STOPPED'
# Only append-only files were created; final resident file bytes are also their peak.
existing=directory_bytes(PREPARATION)
ledger['output_peak_bytes']=existing
for unused in range(20):
    raw=canonical(ledger); total=existing+len(raw)
    if ledger['output_peak_bytes']==total: break
    ledger['output_peak_bytes']=total
else: raise RuntimeError('ledger byte count did not stabilize; retained partial setup blocks Stage A')
assert len(raw)<=1048576 and existing+len(raw)<=67108864
# If evidence is already too large, do not create another over-budget artifact.
# The prelaunch record and fsynced journals still establish the failed attempt.
durable(PREPARATION/'setup-ledger.json',raw)
raise SystemExit(0 if ledger['status']=='COMPLETED' else 1)
