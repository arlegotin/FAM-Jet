"""FIXROUND1 artifact/dataflow audit; no process sampler or project imports."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
BASE='dcd0a4f1265314485577637860b427e97a992b5e'
EXPECTED_PACKAGE='15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
frozen=json.loads((OUT/'frozen-source.json').read_text())
for path,want in frozen['source_hashes'].items():
    assert sha(ROOT/path)==want
    assert hashlib.sha256(subprocess.check_output(['git','show',frozen['source_commit']+':'+path],cwd=ROOT)).hexdigest()==want
for names in [('famjet','requirements.lock'),('validation/kernel_stage_a/authority.py','validation/kernel_stage_a/production.py',
            'validation/kernel_stage_a/commands.py','validation/kernel_stage_a/reader_worker.py','validation/kernel_stage_a/__main__.py')]:
    subprocess.run(['git','diff','--exit-code',BASE,frozen['source_commit'],'--',*names],cwd=ROOT,check=True,stdout=subprocess.PIPE)
package={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'famjet').rglob('*.py'))}
package_hash=hashlib.sha256(json.dumps(package,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
assert package_hash==EXPECTED_PACKAGE
prior=ROOT/'docs/research/task18-native-python-lifetime-evidence'
subprocess.run(['git','diff','--exit-code',BASE,'--',str(prior.relative_to(ROOT)),
               'docs/research/task18-native-python-lifetime-report.md'],cwd=ROOT,check=True,stdout=subprocess.PIPE)
prior_manifest=json.loads((prior/'artifact-manifest.json').read_text())
prior_regular=0
for path,item in prior_manifest['files'].items():
    if item['type']=='file': assert sha(ROOT/path)==item['sha256']; prior_regular+=1
    elif item['type']=='symlink': assert str((ROOT/path).readlink())==item['target']
native=json.loads((prior/'native-01/result.json').read_text())
assert native['source_commit']=='18c7753e982b9ea2a8d6191a35970c5151403ab7' and native['seconds']==2.031376834027469
attempts=[]; cases=[]
for name,want_exit in [('red-01',1),('green-01',0),('cover-01',0)]:
    folder=OUT/name; attempt=json.loads((folder/'attempt.json').read_text())
    assert attempt['exit']==want_exit
    summary=(folder/'output.log').read_text().strip().splitlines()[-1]
    assert name=='red-01' or ('6 passed' if name=='green-01' else '105 passed, 24 deselected') in summary
    mappings=json.loads((folder/'specimen-mappings.json').read_text())
    for item in mappings:
        if item.get('type')=='symlink': assert str(Path(item['durable']).readlink())==item['target']
        else: assert sha(Path(item['durable']))==item['sha256']
    attempts.append(dict(name=name,summary=summary,**attempt,mapping_count=len(mappings)))
final=OUT/'cover-01/specimens'
for folder in sorted(final.glob('test_valid_reader_join_publish[0-9]*')):
    result=json.loads((folder/'monitor/monitor.json').read_text()); worker=result['workers']['400002']
    assert result['status']=='COMPLETED' and result['reason'] is None and result['unresolved_worker_count']==0
    assert worker['baseline_bytes']==100 and worker['role']=='worker' and worker['incremental_peak_bytes']==0
    rows=[json.loads(line) for line in (folder/'monitor/monitor-evidence.jsonl').read_text().splitlines()]
    resolutions=[row for row in rows if row['kind']=='resolution' and '400002' in row['roles']]
    samples=[row for row in rows if row['kind']=='sample' and '400002' in row['rss']]
    index=int(folder.name[-1]); want_count=2 if index==2 else 1
    assert len(resolutions)==len(samples)==want_count
    cases.append(dict(join=('baseline','launch','self')[index],status=result['status'],worker=worker,
                      reader_sample_count=len(samples),reader_resolution_count=len(resolutions),seconds=result['outer_seconds']))
assert len(cases)==3
cap=json.loads(next(final.glob('test_late_reader_join_retains_[0-9]*/monitor/monitor.json')).read_text())
assert cap['status']=='STOPPED' and cap['reason']=='incremental worker memory cap' and cap['incremental_worker_peak_bytes']>=100
failed=json.loads(next(final.glob('test_late_valid_reader_join_ca[0-9]*/monitor/monitor.json')).read_text())
assert failed['workers']['400002']['role']=='unaccounted' and failed['workers']['400002']['baseline_bytes']==0
assert failed['source_event_accounting']['identity_complete'] is True
invalid=[]
for path in final.glob('test_late_reader_join_never_by[0-9]*/monitor/monitor.json'):
    result=json.loads(path.read_text())
    assert result['status']=='STOPPED' and result['workers']['400002']['baseline_bytes']==0
    assert result['source_event_accounting']['identity_complete'] is False
    invalid.append(str(path))
assert len(invalid)==4
raw_padding=[str(path.relative_to(OUT)) for path in OUT.glob('*/specimens/**/monitor.json')
             if any(line.endswith((b' ',b'\t')) for line in path.read_bytes().splitlines())]
record=dict(status='VERIFIED_L1_ARTIFACTS_ONLY_NOT_SOURCE_ACCEPTANCE',base=BASE,source_commit=frozen['source_commit'],
            source_hashes=frozen['source_hashes'],attempts=attempts,joined_reader_cases=cases,
            cap=dict(status=cap['status'],reason=cap['reason'],peak=cap['incremental_worker_peak_bytes']),
            invalid_join_cases=invalid,persistent_failed_identity_preserved=True,
            prior_regular_files_byte_verified=prior_regular,package_hash=package_hash,
            prior_native=dict(source_commit=native['source_commit'],seconds=native['seconds'],
                              returncodes=[case['returncode'] for case in native['cases']],rerun=False),
            raw_padding_files=raw_padding,new_native_attempts=0,numerical_requests=0,reads=0,factors=0,models=0)
(OUT/'verification.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
