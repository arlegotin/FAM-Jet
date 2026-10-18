"""Package existing controlled evidence only; does not execute any test or probe."""
import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path.cwd(); scratch=Path('/tmp/task18-native-fix3')
DEST=ROOT/'docs/research/task18-kernel-stage-a-native-process-fix3-evidence'; DEST.mkdir(exist_ok=True)
sha=lambda data: hashlib.sha256(data).hexdigest()
mappings=[]
def copy(src,dest):
    dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,dest)
    raw=src.read_bytes(); assert dest.read_bytes()==raw
    mappings.append(dict(original=str(src),durable=str(dest.relative_to(ROOT)),bytes=len(raw),sha256=sha(raw)))
for src in sorted(scratch.iterdir()):
    if src.is_file() and src.name not in ('verification-draft.json',): copy(src,DEST/src.name)
for name in ['task-18-native-process-fix3-brief.md','task-18-native-process-fix2-review.md']:
    copy(ROOT/'.superpowers/sdd/2026-10-16-famjet'/name,DEST/'contract'/name)
base=Path('/private/var/folders/q3/tm7kkng56417wgzydc4q8p8r0000gn/T/pytest-of-artemlegotin')
prefixes=('test_post_authority_baseline_b','test_source_sample_overlapping','test_late_inner_rss_survives_f','test_unscanned_complete_source','test_unrecoverable_source_jour','test_minimum_failure_budget_st')
retained=[]; specimens={}
for run,label in [(4357,'covering-initial'),(4358,'adjacent-green'),(4359,'final')]:
    for test in sorted((base/f'pytest-{run}').iterdir()):
        if test.is_symlink() or not test.is_dir() or not test.name.startswith(prefixes): continue
        for verdict in sorted(test.rglob('monitor.json')):
            source=verdict.parent; relative=Path(label)/source.relative_to(base/f'pytest-{run}')
            for src in sorted(source.rglob('*')):
                if src.is_file(): copy(src,DEST/'specimens'/relative/src.relative_to(source))
            summary=json.loads(verdict.read_bytes())
            specimens[str(relative)]=dict(original=str(source),durable=str((DEST/'specimens'/relative).relative_to(ROOT)),
                directory_bytes=sum(p.stat().st_size for p in source.rglob('*') if p.is_file()),
                verdict_bytes=verdict.stat().st_size,verdict_payload_bytes=len(verdict.read_bytes().rstrip()),summary=summary)
    retained.append(dict(attempt=label,pytest_root=str(base/f'pytest-{run}'),status='retained_selected_actual_specimens'))
missing=[]
for run,label in [(4354,'RED'),(4355,'intermediate_GREEN_attempt_failed'),(4356,'focused_GREEN')]:
    missing.append(dict(attempt=label,pytest_root=str(base/f'pytest-{run}'),status='pruned_by_pytest_before_packaging',
                        actual_output_byte_preservation_claim=False,raw_log_retained=True,test_inputs_retained=True))
(DEST/'specimens.json').write_text(json.dumps(specimens,indent=2)+'\n')
source_paths=['validation/kernel_stage_a/monitor.py','validation/kernel_stage_a/README.md','tests/test_kernel_stage_a_native_process_fix3.py']
command=".venv/bin/python -m pytest -q tests/test_kernel_stage_a_native_process_fix3.py tests/test_kernel_stage_a_native_process_fix2.py tests/test_kernel_stage_a_native_process_fix1.py tests/test_kernel_stage_a_native_process.py tests/test_kernel_stage_a_preflight_fix2.py tests/test_kernel_stage_a_preflight.py tests/test_kernel_stage_a_preflight_fix1.py -k 'native or monitor or authority or observer or baseline or f3 or f5 or same_interpreter or prospective'"
verification=dict(version=1,scope='Task18 native adapter ROUND3 N1 phase-independent numerical recovery and narrowly adjacent root authority charge',
 base='1b0bb18aed81bcb88a0faec5f6d56397fb2de5d7',source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 source_files={p:sha(Path(p).read_bytes()) for p in source_paths},package_sha256='15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050',
 source_self_accepted=False,scientific_release=False,full_stage_a_pass=False,lifetime_design_status='HELD; unchanged',
 native_functional_attempts=0,scientific_factor_constructions=0,scientific_reads=0,full_suite_run=False,
 focused_command=command,focused_exit_code=0,focused_output=(scratch/'final-focused.txt').read_text(),
 attempts=[dict(log=name,exit_code=code,summary=summary) for name,code,summary in [('red.txt',1,'4 failed, 1 passed'),('green.txt',1,'2 failed, 10 passed; missing unresolved role metadata'),('green2.txt',0,'12 passed'),('covering-initial.txt',0,'63 passed, 24 deselected'),('adjacent-green.txt',0,'6 passed'),('final-focused.txt',0,'64 passed, 24 deselected')]],
 artifact_status=dict(pruned_early_specimens=missing,retained_runs=retained,early_missing_outputs_recreated=False,packaging_reruns=0),
 accounting=dict(raw_recovery_phase_independent=True,root_authority_attribution='sample interval overlap against ordered semantic start/end boundaries',
  copy_failure='full known per-PID peak sum; identity/phase not supplied from raw numerical cursor',
  adjacent_charge_branch='authority_worker uses attributed phase RSS rather than whole-lifetime maximum',
  additional_pending_state='one root RSS integer per already-retained pending batch',new_monitor_files=0,new_raw_duplicates=0,
  identity_and_lifetime_policy_unchanged=True,initialized_output_exact_five_files_unchanged=True,original_deadline_and_output_cap=True),
 limits=dict(outer_seconds=600,candidate_seconds=90,incremental_worker_bytes=201326592,output_bytes=67108864,free_disk_bytes=4294967296,cpu_budget_seconds=64,numerical_threads_max=4),
 scientific_nulls=[*json.loads(Path('validation/kernel_stage_a/prospective-seal.json').read_text())['pending'],'root_stage_A_release'],
 prior_byte_inventory_files=173,specimens=specimens,mappings=mappings)
(scratch/'verification-draft.json').write_text(json.dumps(verification,indent=2)+'\n')
print(f'Packaged {len(mappings)} exact copies; {len(specimens)} controlled specimen directories; no execution')
