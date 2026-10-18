# Task18 Kernel Stage A: held, external setup command proposal

Read-only reconnaissance, 18 October 2026. No constructor, import of torch/famjet, native probe, fixture, reference, fit, cache load, test, or Git mutation was executed to prepare this proposal. This file is the only write. This proposes one root-reviewed command; it is not an execution release, a new CLI, or a setup framework.

## Exact operational choice

Use the existing `monitor.supervise(command, ...)` with ONE frozen `-I -B /absolute/prelaunch/setup-worker.py ...` setup worker vector. Materialize the one root-reviewed literal body as a fixed hashed setup artifact outside the checkout; charge its bytes before spawn. The short vector contains no multiline or long `-c` body whose native command rendering would need separate verification. The root PID already matches the exact supplied `command` through `classify(..., stage_vector=command)`; it need not equal `commands.stage_command`. Thus a new production setup entry point is unnecessary. Root must adopt the literal worker body and its complete launch vector/hash for this allocation only. Do not admit arbitrary Python bootstraps, add a basename exemption, replace the sampler, or change the Stage A seal's runtime/identity rules.

The setup worker has no authority phase, Git child, Python child, reader context, or scientific reader. Before allocating rates or models it imports every module used below, sets torch numerical threads to one, and calls existing `record_baseline` once. That call samples current native resident RSS; `ru_maxrss`, a pre-import measurement, or an invented subtraction is not equivalent. The baseline observer's exact declaration goes into `monitor-events.jsonl`. Before the declaration/baseline arrives, the fixed root is pending; final reconciliation must resolve it. The existing monitor recognizes that exact root's observer child. Its outer observer is also charged in full. No `authority_start` is needed merely to recognize the setup Python worker; source setup checks below do not spawn Git.

The existing scope excludes the supervising Python parent's RSS, as in the later Stage A parent. It measures worker/descendant sampled absolute tree RSS and post-import incremental worker RSS, with conservative native observer charges. Do not silently rename that scope as total machine/parent RSS or allocator peak. Sampling is 0.02s and cannot certify between-sample peaks.

Concrete missing capability/release gate: current source must have an independently accepted, native-compatible `process_tree` implementation that observes the *actual* resolved interpreter executable and exact expected command display on this host. Neither a source read nor controlled-sampler tests establish that native compatibility. If that component is not accepted, this command remains HELD; no alternative sampler, interpreter identity normalization, or relaxed bootstrap policy is proposed here. The interface below is based on the current `supervise`, `record_baseline`, and event schemas and must be rechecked after concurrent native-monitor work.

## One concrete command body to freeze

Root supplies only the final clean full Git identity and fresh absolute output path. Resolve these literals before review and freeze the whole resulting command/vector; unresolved placeholders are not launch authority. `SOURCE_FULL_GIT` comes from root's independently verified clean source observation, not an arbitrary environment claim. Its later equality is checked by existing `authority.verify`; setup does not manufacture a different Git identity. Root also verifies the frozen metadata/helper bytes against its accepted inventory before releasing this exact command. Package identity is recomputed before factors below. Setup output is outside the checkout, with no symlinks, and initially absent. The only executable setup artifact is `prelaunch/setup-worker.py`, containing exactly the root-reviewed literal below. It is an allocation input with its own SHA256, independent of the unchanged repository/package identity; it is not a new repository entry point, factory, framework, or admitted family of scripts. Root freezes that exact body hash and full short vector before spawn.

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python -I -B - <<'PY'
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
PY
```

This command is prospective text, not an executed artifact. Its `-B` flags prevent bytecode writes to the checkout. The supervisor writes worker stdout/stderr itself, and parent logs are captured under `prelaunch/`; any additional outer capture or root release/seal files produced during the allocation must also live under and be counted in the preparation parent. Root must retain the exact shell bytes, hashed external worker body, short vector hash and parent invocation as allocation evidence, while leaving the later scientific seal separate. Read the known `setup-ledger.json` path and exit status for the result. `setup_elapsed_at_finalization_start` names its reached boundary honestly; final serialization/fsync and root inspection remain charged through the unchanged absolute deadline, without pretending an earlier timestamp includes future work.

## Binding counts and failure handling

`descriptors.candidates()` is exactly `(jet,1e-10),(bank,1e-10),(bank,1e-6),(jet,1e-6),(jet,1e-2),(bank,1e-2)`. The two existing training-caller expressions above produce the four/eight represented rates once, with no independently regenerated grid or Decimal/exp replacement. Both fixed writer hashes must match the frozen records **before any factor attempt**. Writer hash does not include epsilon/support/chunk configuration; those are explicitly fixed in the constructor and full exported schema. Prior5224/t_ref1, one head, CPU64 K16/V8 and Jet4/Bank8 are retained.

There are six direct `KernelReadModel`/`KernelProjection` attempts, including `FactorApplicabilityError` failures. Each such failure produces exactly the existing three-field failed-factor record consumed by `production.Backend.setup`; no replacement or alternate solve occurs. Only that typed factor-applicability failure permits the next original candidate. Other exceptions, timeout, output/resource failure and cancellation stop setup. Such a stopped setup is retained but cannot be sealed as six completed attempts. A started counter is fsynced immediately before every constructor/export; killed or failed work therefore survives as an unmatched start event. Never fill missing attempts with six in a failure ledger or retry remaining factors under a fresh clock.

Required `export_method(model)` already reconstructs statics for its strict audit. The source-derived consequences of a completed top-level model export are four kernel copies, two `KernelProjection.from_statics` instances and two `KernelReadModel.from_statics` instances in current accepted source. These are static deductions from the export implementation, not individually measured constructor/copy counts. Their time/RSS is included in the monitored top-level call; they do not call the projection constructor/eigendecomposition. `actual_completed_top_level_exports` increments only after an actual top-level export returns, and each durable `export_end` records the reached total. The numeric nested consequences are explicitly labeled `source_derived_copy_consequences`. Retain unmatched export starts if interrupted; never infer actual partial nested completion from them. Tensor/wire conversions, JSON serialization, stored bytes, garbage collection and all stdout/stderr/events remain charged. Explicit rate tensor tolist/hex conversion is two calls; successful top-level method exports are at most six; static record serializations are exactly six only on completed setup, plus two rates and the worker/final ledgers. Lower-level clone/temporary counts are consequences of the accepted source operations, not measured allocator totals; do not relabel these as a full allocator census.

Do **not** call `model.ownership_ledger()` just to fill this ledger. Its signature is parameterless and its implementation calls `export_method(self)` again, adding another full audit/reconstruction/serialization pass, while its Python/tensor accounting still does not measure process RSS. `ownership_ledger_calls:0` is deliberate. The existing later production diagnostic already records ownership under its own charged operations. There are no reads, snapshots, states, references, training objects, fits or cache loads in setup.

## Artifact ordering and finalization

The fresh preparation parent has `prelaunch/` and `worker-output/`. The literal body is durably materialized once as `prelaunch/setup-worker.py`; `prelaunch/setup-command.json` records that artifact's absolute path/SHA256, the exact short vector/hash and original clock before spawn. The parent checks the persisted body hash immediately before launch. Its root-reviewed input provenance is separate from repository source/package provenance, and both remain retained. This exact short invocation uses no new command parser or generic script admission policy. Existing `supervise` creates its initially absent `worker-output` and charges its own bytes plus `prelaunch`, without overlap or double counting. Later Stage A charges the whole preparation parent through its existing `preparation_output` interface.

A1MiB parent-finalizer reservation is inside64MiB: the setup monitor stops at63MiB combined worker/prelaunch bytes, and the finalizer refuses a ledger larger than1MiB or a combined final directory above64MiB. This is a conservative stop below the authorized ceiling, not a larger output allowance. Only append-only/no-delete files are created, so final bytes upper-bound their earlier resident file bytes. The final size calculation stabilizes after the final status is selected. Interrupted/failed attempts remain retained; missing six-attempt evidence blocks Stage A. Setup timing includes imports, serialization, monitor cleanup and parent finalization, not merely constructor timings. Root inspection starts afterward and continues to consume the original600s.

The monitor's process-group cleanup runs before its return or propagated cancellation. A parent-side monitor exception becomes a failed ledger when possible. A hard parent/machine kill may prevent that summary; prelaunch evidence and fsynced worker starts remain the authoritative incomplete record. Do not rerun under a new clock. Before root adopts this literal it must check the unchanged native-monitor final-report behavior and its accepted current interfaces, including its own final-report output accounting; this proposal makes no native execution claim.

## Seal handoff

Root reads the completed durable ledger and checks its real native monitor result, exact six attempts (failed factors included), zero reads, both rate maps, six static maps, full Git/package, absolute preparation parent, measured peak fields, started/completed times and retained failure evidence. `authority.verify` currently checks the listed fields but does not itself validate the entire event/monitor history; root must not treat a syntactically valid ledger as measurement proof.

The final setup ledger supplies `actual_factor_constructions:6`, `actual_reads:0`, `allocation_start_monotonic`, `source_full_git`, accepted package hash, exact `static_exports`/`represented_rate_records` path/hash maps, absolute `output_directory`, `output_peak_bytes`, and `incremental_worker_peak_bytes`. Retain UTC/start/deadline, absolute/tree RSS, baseline/worker tables, observer charges, operation events and all failure costs alongside these. The resource seal has exactly the current five constants (`baseline:'post-import/pre-allocation per worker'`, `absolute_rss:true`, `process_tree_rss:true`, `sequential_workers:true`, `outputs_include_temporaries:true`) plus original monotonic/UTC start, original `start+600` deadline and final setup-ledger path/hash. Limits remain201326592B,67108864B,>=4294967296B free and <=four numerical threads.

Root inspection and the later separately sealed `python -m validation.kernel_stage_a --seal ...` consume that **same** original600s. Never call `authority.entry` with a renewed600s allocation or rerun setup for more time. The later output remains initially absent; its monitor charges the complete preparation parent. Stage A reconstructs the sealed method bytes via the existing frozen-static route and uses the sealed hex rates; it does not fit or eigendecompose. Failed-factor candidates receive no reads. The original execution adoption remains source-only; no setup ruling alone releases scientific Stage A, Stage B or broader Task18 work.
