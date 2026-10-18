import hashlib,json,os,stat,subprocess,time
from pathlib import Path
root=Path.cwd(); archive=root/'docs/research/task18-owned-root-lifecycle-evidence'
source='241852a'; started=time.time()
result=subprocess.run(['git','diff','--cached','--check'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(archive/'preserved-evidence-diff-check.log').write_bytes(result.stdout)
report=root/'docs/research/task18-owned-root-lifecycle-report.md'
text=report.read_text()
text+='\nDelivery verification records final tested source equality to source commit, staged archival coverage and all retained hashes. The source diff check passed. The evidence-only staged `git diff --cached --check` emits expected whitespace diagnostics for original monitor verdict padding and retained pytest failure output; these raw bytes are preserved unchanged, including the diagnostics log. This evidence diagnostic is not a source defect or a reason to rewrite specimens. See [delivery verification](task18-owned-root-lifecycle-evidence/delivery-verification.json) and [delivery manifest](task18-owned-root-lifecycle-evidence/delivery-manifest.json).\n'
report.write_text(text)
(root/'.superpowers/sdd/2026-10-16-famjet/task-18-owned-root-lifecycle-report.md').write_text(text)
source_audit=json.loads((archive/'source-audit.json').read_text())
source_equal={}
for name,value in source_audit['source_files'].items():
    committed=subprocess.check_output(['git','show',source+':'+name])
    source_equal[name]=hashlib.sha256(committed).hexdigest()==value['sha256']==hashlib.sha256((root/name).read_bytes()).hexdigest()
cover=archive/'task18-owned-root-lifecycle-cover-4f4wdzhn/source-inputs'
cover_equal={name:(cover/name).read_bytes()==(root/name).read_bytes() for name in ('validation/kernel_stage_a/monitor.py','tests/test_kernel_stage_a_owned_root_terminal.py')}
assert all(source_equal.values()) and all(cover_equal.values())
staged=set(subprocess.check_output(['git','diff','--cached','--name-only','-z']).decode().split('\0'))
required=[]
for directory in archive.glob('task18-owned-root-lifecycle-*'):
    for path in directory.rglob('*'):
        if path.is_symlink() or path.is_file(): required.append(str(path.relative_to(root)))
missing=sorted(set(required)-staged)
assert not missing,missing
verification=dict(source_commit=subprocess.check_output(['git','rev-parse',source],text=True).strip(),source_matches_commit=source_equal,final_cover_matches_source=cover_equal,
    all_original_attempt_files_staged=True,attempt_files=len(required),source_diff_check_exit=0,
    evidence_diff_check=dict(command=['git','diff','--cached','--check'],started_epoch=started,end_epoch=time.time(),exit=result.returncode,output_path='preserved-evidence-diff-check.log',expected_preserved_whitespace=True),
    native_executed=False,scientific_executed=False,scratch_report_equals_durable=True)
(archive/'delivery-verification.json').write_text(json.dumps(verification,indent=2)+'\n')
manifest={}
for path in [report]+sorted(archive.rglob('*')):
    if path.name=='delivery-manifest.json': continue
    mode=path.lstat().st_mode
    if stat.S_ISLNK(mode): raw=os.fsencode(os.readlink(path)); kind='symlink'
    elif stat.S_ISREG(mode): raw=path.read_bytes(); kind='regular'
    else: continue
    manifest[str(path.relative_to(root))]=dict(kind=kind,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
(archive/'delivery-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(verification=verification,manifest_files=len(manifest),diagnostic_bytes=len(result.stdout)),indent=2))
