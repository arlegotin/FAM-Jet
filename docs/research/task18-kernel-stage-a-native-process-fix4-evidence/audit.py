"""Pure-file audit: no package imports, native sampling or scientific execution."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[3]
EVIDENCE=Path(__file__).resolve().parent
BASE='6ae27aa9ceacd83905d47de60bfee5961cf752e1'
SOURCE='daa89fcd7986e9a4c600869d256451fbba65c927'
AUTHORED={'validation/kernel_stage_a/monitor.py','tests/test_kernel_stage_a_native_process_fix3.py'}
PACKAGE='15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050'
def sha(data): return hashlib.sha256(data).hexdigest()
def info(path):
    data=path.read_bytes()
    return dict(sha256=sha(data),bytes=len(data))
def write(path,value): path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)

assert set(git('diff','--name-only',BASE,SOURCE).decode().splitlines())==AUTHORED
for name in AUTHORED: assert (ROOT/name).read_bytes()==git('show',SOURCE+':'+name),name
prior={}
for row in git('ls-tree','-rz',BASE).split(b'\0'):
    if not row: continue
    header,name=row.split(b'\t',1)
    name=name.decode()
    if name in AUTHORED: continue
    mode,kind,oid=header.split()
    assert kind==b'blob',name
    data=(ROOT/name).read_bytes()
    actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    assert actual==oid.decode(),name
    prior[name]=dict(sha256=sha(data),bytes=len(data))
write(EVIDENCE/'prior-byte-inventory.json',prior)
files={str(path.relative_to(ROOT)):sha(path.read_bytes()) for path in sorted((ROOT/'famjet').rglob('*.py'))}
package=sha(json.dumps(files,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())
assert package==PACKAGE

attempts={}
mapping_count=0
specimens=[]
for attempt,expected_exit in [('red',1),('green',0),('cover',0)]:
    dest=EVIDENCE/attempt
    command=json.loads((dest/'command.json').read_text())
    assert command['exit_code']==expected_exit
    assert command['basetemp']=='/tmp/task18-native-fix4/pytest-'+attempt
    for name,expected in command['inputs'].items(): assert info(dest/'inputs'/name)==expected,name
    for name in AUTHORED:
        expected=git('show',(BASE if attempt=='red' and name.endswith('monitor.py') else SOURCE)+':'+name)
        assert (dest/'inputs'/name).read_bytes()==expected,(attempt,name)
    mappings=json.loads((dest/'mappings.json').read_text())
    with tarfile.open(dest/'all-specimens.tar.gz') as tar:
        regular={member.name for member in tar.getmembers() if member.isfile()}
        assert regular=={row['member'] for row in mappings if 'archive' in row}
        for row in mappings:
            expected=dict(sha256=row['sha256'],bytes=row['bytes'])
            assert info(Path(row['original']))==expected,row['original']
            if 'archive' in row:
                data=tar.extractfile(row['member']).read()
                assert dict(sha256=sha(data),bytes=len(data))==expected,row['member']
            else: assert info(ROOT/row['durable'])==expected,row['durable']
    mapping_count+=len(mappings)
    outputs=[]
    for path in sorted((dest/'specimens').rglob('monitor.json')):
        if not path.read_bytes().strip(): continue
        value=json.loads(path.read_bytes())
        outputs.append(path)
        specimens.append(dict(attempt=attempt,path=str(path.relative_to(ROOT)),
                              directory_bytes=sum(p.stat().st_size for p in path.parent.rglob('*') if p.is_file()),
                              verdict=info(path),status=value['status'],reason=value['reason'],
                              authority_rss=value.get('authority_full_rss_peak_bytes'),
                              incremental_rss=value['incremental_worker_peak_bytes'],
                              raw_peak=value['absolute_process_tree_peak_bytes'],
                              accounting=value.get('source_event_accounting'),
                              unresolved_count=value.get('unresolved_worker_count')))
    attempts[attempt]=dict(command=command['shell_command'],exit_code=expected_exit,
                          mapped_files=len(mappings),verdicts=len(outputs),raw=info(dest/'output.txt'),
                          all_specimens_archive=info(dest/'all-specimens.tar.gz'),
                          preservation='All actual attempts retained; unique basetemp, full archive, readable verdict directories and input snapshots.')
write(EVIDENCE/'specimens.json',specimens)

cover=EVIDENCE/'cover/specimens'
for index,authority_rss in [(2,0),(3,60)]:
    out=cover/f'test_post_authority_baseline_b{index}'/'copy_failure'
    value=json.loads((out/'monitor.json').read_bytes())
    assert value['status']=='STOPPED' and value['reason']=='output cap'
    assert value['authority_full_rss_peak_bytes']==authority_rss
    assert value['incremental_worker_peak_bytes']==value['absolute_process_tree_peak_bytes']==value['observed_pid_peak_sum_bytes']==500
    assert value['source_event_accounting']['complete'] is True and value['source_event_accounting']['identity_complete'] is False
    worker=next(iter(value['workers'].values()))
    assert worker['role']=='unaccounted' and value['unresolved_worker_count']==1
    assert worker.get('authority_phase_peak_bytes',0)==authority_rss
    source=[json.loads(line) for line in (out/'monitor-events.jsonl').read_text().splitlines()]
    assert [row['event'] for row in source]==['authority_start','authority_end','observer_sample','baseline']
    assert source[2]['processes'][0]['sample_start']>source[1]['monotonic']
    rows=[json.loads(line) for line in (out/'monitor-evidence.jsonl').read_text().splitlines()]
    sample=next(row for row in rows if row['kind']=='sample' and list(row['rss'].values())==[500])
    resolution=next(row for row in rows if row['kind']=='resolution' and row['sample_id']==sample['sample_id'])
    assert list(resolution['roles'].values())==['unaccounted']
    assert all(identity is None for identity in resolution['identities'].values())

local=ROOT/'.superpowers/sdd/2026-10-16-famjet/task-18-native-process-fix4-report.md'
report=ROOT/'docs/research/task18-kernel-stage-a-native-process-fix4-report.md'
assert local.read_bytes()==report.read_bytes()
summary=f'PASS: {len(prior)} prior tracked files unchanged; {mapping_count} artifact mappings verified; {len(specimens)} actual verdicts retained; package {package}\n'
(EVIDENCE/'audit.txt').write_text(summary)
artifacts={str(path.relative_to(ROOT)):info(path) for path in sorted(EVIDENCE.rglob('*')) if path.is_file() and not path.is_symlink()}
artifacts[str(report.relative_to(ROOT))]=info(report)
artifacts[str(local.relative_to(ROOT))]=info(local)
write(ROOT/'docs/research/task18-kernel-stage-a-native-process-fix4-verification.json',dict(
    BASE=BASE,actual_source_HEAD=SOURCE,current_HEAD_at_audit=git('rev-parse','HEAD').decode().strip(),
    source_files={name:info(ROOT/name) for name in sorted(AUTHORED)},package_sha256=package,
    prior_unchanged_files=len(prior),artifact_mapping_count=mapping_count,actual_verdict_count=len(specimens),
    attempts=attempts,artifacts=artifacts,artifact_status='All round4 attempts and specimens retained. No reconstruction of missing round3 specimens.',
    audit_command='.venv/bin/python docs/research/task18-kernel-stage-a-native-process-fix4-evidence/audit.py',audit_exit_code=0,
    native_functional_attempts=0,scientific_factor_constructions=0,scientific_model_reads=0,
    scientific_release=False,lifetime_policy='HELD; strict per-sample Python ESRCH unchanged',
    exclusions='Verification JSON excludes its own hash. No whole suite/native/scientific execution.'))
print(summary,end='')
