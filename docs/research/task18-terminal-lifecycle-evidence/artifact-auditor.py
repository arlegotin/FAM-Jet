import hashlib,json,os,subprocess
from pathlib import Path
root=Path.cwd(); evidence=root/'docs/research/task18-terminal-lifecycle-evidence'
base='1bc005abe7b323c7cc76358adecc6e71346296d2'; source='3044f3ca0cd935b4e3e53863cbe259fdcacd4c38'
def meta(path):
    raw=path.read_bytes(); return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
prior={}; mismatches=[]
for line in subprocess.check_output(['git','ls-tree','-r',base],text=True).splitlines():
    head,path=line.split('\t'); mode,kind,blob=head.split()
    if kind!='blob' or not path.startswith('docs/research/task18'): continue
    target=root/path
    if not target.is_file() and not target.is_symlink(): mismatches.append(path); continue
    raw=os.fsencode(os.readlink(target)) if mode=='120000' else target.read_bytes()
    actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    info=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),git_mode=mode); info.update(base_git_blob=blob,current_git_blob=actual,byte_exact_to_base=actual==blob)
    prior[path]=info
    if actual!=blob: mismatches.append(path)
(evidence/'prior-artifacts-audit.json').write_text(json.dumps(dict(base_git=base,files=prior,mismatches=mismatches,file_count=len(prior),bytes=sum(row['bytes'] for row in prior.values())),indent=2)+'\n')
source_paths=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r',source],text=True).splitlines()
source_paths+=['validation/kernel_stage_a/authority.py','validation/kernel_stage_a/commands.py','requirements.lock']
source_info={path:meta(root/path) for path in source_paths}
package={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((root/'famjet').rglob('*.py'))}
package_hash=hashlib.sha256(json.dumps(package,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
(evidence/'source-audit.json').write_text(json.dumps(dict(base_git=base,source_git=source,files=source_info,package_hash=package_hash,expected_package_hash='15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050',package_unchanged=package_hash=='15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050',authority_diff=subprocess.check_output(['git','diff',base,source,'--','validation/kernel_stage_a/authority.py','validation/kernel_stage_a/commands.py','requirements.lock','famjet'],text=True)),indent=2)+'\n')
print(json.dumps(dict(prior_file_count=len(prior),prior_bytes=sum(row['bytes'] for row in prior.values()),mismatches=mismatches,package_hash=package_hash,source_files=source_info),indent=2))
