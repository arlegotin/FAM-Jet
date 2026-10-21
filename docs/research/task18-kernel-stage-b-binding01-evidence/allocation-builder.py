"""One prospective root allocation, no parent/model/scientific launch."""
import datetime
import hashlib
import json
import math
import platform
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path('/Users/artemlegotin/Documents/git_alter/FAM-Jet')
sys.path.insert(0, str(ROOT))
from validation.kernel_stage_b import authority as b
from validation.kernel_stage_a import authority as a
from validation.kernel_stage_a.commands import vector_hash

PREP = ROOT / 'artifacts/task18-kernel-stage-b-binding-01-prep'
OUT = ROOT / 'artifacts/task18-kernel-stage-b-binding-01'
PLAN = PREP / 'plan.json'
SOURCE = '9f47f8260374a0193198c6ba8faa3b68c5a016eb'
LIMITS = dict(outer_seconds=900., candidate_seconds=180., incremental_bytes=512*2**20,
              output_bytes=64*2**20, free_disk_bytes=4*2**30, numerical_threads=1)


def ref(path, kind):
    raw = path.read_bytes()
    return dict(kind=kind, path=str(path.relative_to(ROOT)), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def save(path, value):
    path.write_bytes(b.canonical(value))


def observe(name, argv):
    p = subprocess.run(argv, capture_output=True)
    stdout, stderr = PREP/(name+'.stdout'), PREP/(name+'.stderr')
    stdout.write_bytes(p.stdout); stderr.write_bytes(p.stderr)
    result = dict(argv=argv, returncode=p.returncode, stdout=ref(stdout,'bytes'), stderr=ref(stderr,'bytes'))
    save(PREP/(name+'.json'), result)
    if p.returncode != 0 or p.stderr:
        raise RuntimeError('read-only observation failed: '+name)
    return result, p.stdout


def main():
    assert not PREP.exists() and not OUT.exists(), 'one-use fresh allocation paths'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==SOURCE
    assert subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)==b''
    start, utc = time.monotonic(), time.time()
    PREP.mkdir()
    vm, raw = observe('vm-stat',['/usr/bin/vm_stat'])
    pressure, _ = observe('memory-pressure',['/usr/bin/memory_pressure','-Q'])
    power, _ = observe('power-admission',['/usr/bin/pmset','-g','batt'])
    text = raw.decode()
    page = int(re.search(r'page size of (\d+) bytes',text)[1])
    free = int(re.search(r'Pages free:\s+(\d+)\.',text)[1])
    spec = int(re.search(r'Pages speculative:\s+(\d+)\.',text)[1])
    available = (free+spec)*page
    reserve = math.ceil(available/4)
    disk = shutil.disk_usage(ROOT/'artifacts').free
    host = dict(node=platform.node(),system=platform.system(),release=platform.release(),machine=platform.machine())
    admission = dict(utc_epoch=utc,host=host,vm_stat=vm,memory_pressure=pressure,power=power,
                     page_size=page,free_pages=free,speculative_pages=spec,available_bytes=available,
                     reserve_bytes=reserve,planning_envelope_bytes=available-reserve,free_disk_bytes=disk)
    admitted = available>=2**30 and available-reserve>LIMITS['incremental_bytes'] and disk>=4*2**30
    save(PREP/'admission.json',dict(status='PASS' if admitted else 'REFUSED',admission=admission,
                                   limits=LIMITS,allocation_start_monotonic=start))
    if not admitted:
        print(json.dumps(dict(status='REFUSED_BEFORE_RELEASE',available_bytes=available,disk_bytes=disk)))
        return 2
    plan = b.strict_json((ROOT/'validation/kernel_stage_b/prospective-plan.json').read_bytes())
    review = ROOT/'docs/research/task18-kernel-stage-b-source-review/fix2-review.md'
    manifest = ROOT/'docs/research/task18-kernel-stage-b-source-evidence/source-manifest.json'
    historical = ROOT/'docs/research/task18-kernel-stage-b-source-review/historical-material-manifest.json'
    oldrows = b.strict_json(historical.read_bytes()); newrows = b.strict_json(manifest.read_bytes())
    newmap={r['path']:r for r in newrows}
    assert len(oldrows)==79 and len(newrows)==87 and all(newmap[r['path']]==r for r in oldrows)
    for row in newrows:
        raw=(ROOT/row['path']).read_bytes()
        assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
    changes=sorted(set(newmap)-{r['path'] for r in oldrows})
    assert len(changes)==8
    manual=PREP/'manual-source-and-failure-ruling.md'
    manual.write_text(f'''# Root source compatibility and manual failure dispositions — 21 October 2026

I adopt only descriptive actual-state use of the existing saved states. I individually inspected all24 row30 records in the archived A06 inventory: six original candidates times I/O/U/R. Every source and strict status remains FAILED; the exact24 prediction/window fields and contraction indices8–71 remain unchanged. Each listed disposition retains and scores the actual state. No failure is excluded, repaired, replayed or promoted to source-fidelity certification. Global AFAILED/rawSTOPPED/return1 remain.

Historical executed A source is81204796ade55ce9e7202bc9253b1b61db6a65a3. Current execution source is{SOURCE}. Independent final source review covers f390f2c2644dfe8815d48b724edaf043bc991b84; 9f47f82 adds reviewed custody/status/helper documents with the same87-path material manifest. I explicitly accept that full-Git difference. All79 historical material rows match exact current bytes; only the six external B modules and the two source-adoption amendments are added to the material inventory. The separately pinned one-use witness is reviewed as an execution helper. Famjet/package15cf84, all15 A files, lock2b1931, actual sealed additional paths and original config are unchanged. Full old/new manifests, source review and all24 machine-readable dispositions are bound in this Plan.

This ruling is not native certification or a panel release. Only the separately hashed binding release below may launch anything. Preserve the inherited sampled helper proof and its unknown-child caveats; do not replay it or broaden native mechanisms. Ruling risk: source rework/rejection if compatibility is wrong, never a concealed failure or stronger memory claim.
''')
    ruling_ref=ref(manual,'markdown')
    dispositions=b.strict_json((ROOT/'.superpowers/sdd/2026-10-16-famjet/task-18-kernel-stage-b-manual-dispositions-draft.json').read_bytes())['failures']
    for d in dispositions: d['ruling']=ruling_ref
    plan['approval']=dict(ruling=ruling_ref,approved=True,scope='descriptive_actual_state_only',
                         evidence_sha256=b.digest(plan['evidence']),failures=dispositions,
                         source_review=ref(review,'markdown'),compatibility=dict(
                          old_source='81204796ade55ce9e7202bc9253b1b61db6a65a3',new_source=SOURCE,
                          old_manifest=ref(historical,'source_manifest'),new_manifest=ref(manifest,'source_manifest'),
                          changed_paths=changes,decision='external_adapter_only'))
    runtime=a.runtime()
    bootstrap=ROOT/'validation/kernel_stage_b/bootstrap.py'
    worker=[runtime['executable'],'-I',str(bootstrap),'--worker','--seal',str(PLAN)]
    parent=[runtime['executable'],'-I',str(bootstrap),'--seal',str(PLAN)]
    environment={k:'1' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS',
                                'VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS')}
    environment.update(PYTORCH_ENABLE_MPS_FALLBACK='0',PYTORCH_MPS_FAST_MATH='0')
    launch_power,_=observe('power-launch',['/usr/bin/pmset','-g','batt'])
    plan['execution']=dict(source_full_git=SOURCE,source_manifest=ref(manifest,'source_manifest'),
       runtime=runtime,host=host,admission=admission,limits=LIMITS,
       boundary=dict(allocation_start_monotonic=start,allocation_start_utc_epoch=utc,
          deadline_monotonic=start+LIMITS['outer_seconds'],baseline='post-import/pre-allocation per worker',
          absolute_rss=True,process_tree_rss=True,sequential_workers=True,outputs_include_temporaries=True),
       launch=dict(bootstrap=ref(bootstrap,'python_source'),template_sha256=b.digest(b.TEMPLATE),
          argv=worker,argv_sha256=vector_hash(worker),monitor=ref(ROOT/'validation/kernel_stage_a/monitor.py','python_source'),
          environment=environment,fresh_utc_epoch=time.time(),free_disk_bytes=shutil.disk_usage(ROOT/'artifacts').free,
          power=launch_power),
       terminal=dict(witness=ref(ROOT/'docs/research/task18-kernel-stage-b-binding01-witness.py','python_source'),
          parent_argv=parent,parent_argv_sha256=vector_hash(parent),publication_seconds=180.,publication_bytes=4*2**20),
       qualification=None,preparation_output=str(PREP),output=str(OUT))
    payload=b.digest({k:v for k,v in plan.items() if k!='release'})
    release=PREP/'binding-release.md'
    release.write_text(f'''# One empty Stage B binding release — 21 October2026

Root releases exactly one parent invocation of the approved binding scope for payload {payload}, source {SOURCE}, original start {start} and deadline {start+900.}. No Backend construction, model, encode, read, factor, prediction, training, history generation or protected access. Keep zero scientific counts; no automatic retry. The full96/Q8 panel is unreleased.

Prospective resource choice:900s original outer interval/180s candidate/512MiB conservative incremental worker charge/64MiB output. The prior source-bound forecast motivates these upper limits; they are not measurements or promises. Admission follows the unchanged1GiB printed free+speculative minimum,25% reserve and4GiB disk floor. Binding includes both full stdlib evidence scans, scientific imports/baseline and supervisor completion. Allocation-origin common time includes preparation/startup/final commitment. The separately pinned witness observes actual parent exit. Reserve180s and4MiB for receipt and root post-wrapper verification within the original900s/64MiB caps. Root must include final witness-result/stdout/temporary bytes, not just the finalizer's intermediate totals. RootInvocation/Publication bookkeeping is separate external custody outside the self-measured interval; no claim that it costs zero. A surviving pending receipt is inadmissible without observed wrapper exit0, verified immutable bytes, deadline/reserve checks and separate root Publication.
''')
    plan['release']=dict(approved=True,scope='binding',payload_sha256=payload,ruling=ref(release,'markdown'))
    b.validate_plan(plan)
    save(PLAN,plan)
    save(PREP/'allocation-summary.json',dict(version=1,source=SOURCE,plan_sha256=b.digest(plan),
         plan_file_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),available_bytes=available,
         reserve_bytes=reserve,disk_bytes=disk,limits=LIMITS,outer_start=start,deadline=start+900.,
         admission_age_seconds=time.time()-utc,scientific_work_released=False,parent_launched=False))
    print(json.dumps(dict(status='BINDING_SEALED_NOT_LAUNCHED',source=SOURCE,plan=str(PLAN),
         available_GiB=available/2**30,disk_GiB=disk/2**30,admission_age=time.time()-utc,
         plan_sha256=b.digest(plan),deadline=start+900.),indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
