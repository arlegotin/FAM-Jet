import hashlib,json,subprocess
from pathlib import Path
BASE='1b0bb18aed81bcb88a0faec5f6d56397fb2de5d7'
def sha(data): return hashlib.sha256(data).hexdigest()
files={str(p):sha(p.read_bytes()) for p in sorted(Path('famjet').rglob('*.py'))}
package=sha(json.dumps(files,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())
assert package=='15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050'
prior={}
for name in subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],text=True).splitlines():
    if (name.startswith('famjet/') or
        name.startswith('docs/research/task18-kernel-stage-a-native-process') or
        name in ['validation/kernel_stage_a/authority.py','validation/kernel_stage_a/commands.py','validation/kernel_stage_a/production.py','validation/kernel_stage_a/__main__.py','validation/kernel_stage_a/fixture-descriptors.json','validation/kernel_stage_a/frozen-training-metadata.json','validation/kernel_stage_a/prospective-seal.json','requirements.lock','docs/research/task18-kernel-stage-a-preflight-source-acceptance.json']):
        actual=Path(name).read_bytes(); old=subprocess.check_output(['git','show',BASE+':'+name])
        assert actual==old,name
        prior[name]=dict(sha256=sha(actual),bytes=len(actual))
Path('/tmp/task18-native-fix3/prior-byte-inventory.json').write_text(json.dumps(prior,indent=2)+'\n')
print(f'PASS: {len(prior)} frozen/prior files byte-preserved against {BASE}; package {package}')
