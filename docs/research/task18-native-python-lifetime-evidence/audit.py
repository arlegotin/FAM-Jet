"""Read-only verification of frozen source and the single native sequence."""
import errno
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
EVIDENCE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from validation.kernel_stage_a import authority as a
frozen=json.loads((EVIDENCE/'frozen-source.json').read_text())
result=json.loads((EVIDENCE/'native-01/result.json').read_text())
raw=[json.loads(line) for line in (EVIDENCE/'native-01/raw.jsonl').read_text().splitlines()]
assert result['status']=='PASS_IDENTITY_ONLY_EXPECTED_WORKER_FAILURES'
assert result['seconds']<10 and len(result['cases'])==2
assert (EVIDENCE/'native-01.exit').read_text().strip()=='0'
for key in ('factors','factorizations','model_constructions','numerical_requests','request_bytes','reads'): assert result[key]==0
assert result['package_hash']==frozen['package_hash']=='15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050'
assert not any(row['kind']=='watchdog_cleanup_kill' for row in raw)
checks=[]
for case in result['cases']:
    name=case['case']; pid=case['pid']
    row=next(row for row in raw if row['kind']==name+'_attribution')
    sample=row['row']; generation=row['generation']; proof=generation['proof']
    assert sample['image']['errno']==errno.ESRCH and sample['image']['reason']=='native_lookup_failed'
    assert sample['identity']['image_evidence']=='unavailable_exited'
    assert sample['identity']['launch_evidence']=='source_owned_python_lifetime'
    assert proof['launch_id']==case['launch_id']==generation['launch_id'] and sample['pid']==pid
    assert generation['launch_start']<=proof['lookup_start']<=proof['lookup_end']<generation['completion_end']<=sample['image']['lookup_start']
    assert sample['sample_start']<=generation['completion_end'] and sample['sample_end']>=generation['launch_start']
    assert case['returncode']==generation['returncode']==(2 if name=='root' else 1) and generation['reaped']
    assert case['worker_execution'].startswith('failed_expected') and not case['watchdog_kill']
    assert (EVIDENCE/'native-01'/name/'stdout').read_bytes()==b''
    assert proof['origin']==('unreaped_owned_root' if name=='root' else 'trusted_emitter_self_row')
    assert generation['completion_end']-generation['launch_start']<=5
    checks.append(dict(case=name,pid=pid,returncode=case['returncode'],proof=proof,launch_start=generation['launch_start'],
                       completion_end=generation['completion_end'],rss_bytes=sample['rss_bytes'],
                       baseline_bytes=generation.get('baseline'),esrch=sample['image']))
for path,sha in frozen['source_hashes'].items():
    assert a.file_hash(ROOT/path)==sha
    git_bytes=subprocess.check_output(['git','show',frozen['source_commit']+':'+path],cwd=ROOT)
    assert hashlib.sha256(git_bytes).hexdigest()==sha
for path,sha in result['executed_source_hashes'].items(): assert a.file_hash(path)==sha
assert (EVIDENCE/'native-01-source/native-normal-exit.py').read_bytes()==(EVIDENCE/'native-normal-exit.py').read_bytes()
original=EVIDENCE/'contract/task-18-native-python-lifetime-brief-original.md'
assert original.stat().st_size==9367 and a.file_hash(original)=='e301c3db11381e615fbf512c207d7bbd1778c9be82e75b08e4a594e753ce4f64'
record=dict(status='VERIFIED_ARTIFACTS_ONLY_NO_SOURCE_ACCEPTANCE',source_commit=frozen['source_commit'],
            source_hashes=frozen['source_hashes'],native_cases=checks,package_hash=result['package_hash'],
            seconds=result['seconds'],import_seconds=result['import_seconds'],
            raw_bytes=sum(p.stat().st_size for p in (EVIDENCE/'native-01').rglob('*') if p.is_file()))
(EVIDENCE/'verification.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
