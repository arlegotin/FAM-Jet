from pathlib import Path
import datetime,hashlib,json,shutil,subprocess
w=Path('.superpowers/sdd/2026-10-16-famjet');d=Path('docs/research/e2e-measured-execution-acceptance');d.mkdir(exist_ok=False);base='17ce406d596c1a50a306c6af0d0f08769eca7c07'
def rec(p):
 b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
e=Path('docs/research/e2e-measured-execution-evidence');logs=0
for p in list(e.glob('commands*.json'))+[e/'fixround1/commands.json']:
 for x in json.loads(p.read_bytes()):
  assert rec(Path(x['log_path']))=={'bytes':x['log_bytes'],'sha256':x['log_sha256']};logs+=1
v=json.loads((e/'fixround1/source-hashes.json').read_bytes())
for category in ['changed','preserved']:
 for name,r in v[category].items():assert rec(Path(name))==r,(category,name)
preserved=['famjet','famjet_poc/contracts.py','famjet_poc/data.py','famjet_poc/models.py','famjet_poc/inference.py','famjet_poc/cache.py','famjet_poc/wire.py','famjet_poc/worker.py','famjet_poc/comparators.py','famjet_poc/study.py','famjet_poc/timing.py','famjet_poc/transfer.py','requirements.lock','docs/reporting-requirements.lock','docs/research/e2e-study-config.json','configs/manifests/beijing_v2_targets.json','docs/research/e2e-evaluation-v2-selection-baseline.json','docs/research/e2e-evaluation-v2-public-model-baseline','docs/research/e2e-development-resource-policy.json','docs/research/e2e-inference-qualification.json','docs/research/e2e-coordinate-source-evidence']
assert subprocess.check_output(['git','diff',base,'--',*preserved])==b''
oldnames=set(subprocess.check_output(['git','ls-tree','-r','--name-only',base],text=True).splitlines());changed=sorted(oldnames.intersection(subprocess.check_output(['git','diff','--name-only',base],text=True).splitlines()))
assert set(changed)=={'famjet_poc/pipeline.py','famjet_poc/protected.py','famjet_poc/report_inputs.py','famjet_poc/resources.py','preregistration.md','tests/test_poc_protected.py','tests/test_poc_report_inputs.py'},changed
old=json.loads(Path('docs/research/e2e-evaluation-budget-stop/run04-index.json').read_bytes());out=Path(old['run_root']);files={str(p.relative_to(out)):rec(p) for p in out.rglob('*') if p.is_file()};assert files==old['files']
for name,target in [('e2e-measured-execution-brief.md','requirements.md'),('e2e-measured-execution-review.md','review-initial.md'),('e2e-measured-execution-fix1-review.md','review-fix1.md')]:shutil.copyfile(w/name,d/target)
shutil.copyfile(w/'e2e-r6-root-audit.py',d/'root-audit.py')
r={'schema_version':1,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'base':base,'reviewed_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'verdict':'R6SOURCEaccepted_SPEC_YES_QUALITY_APPROVED_R6_1_through4_addressed','raw_log_pairs_verified':logs,'source_inventory_verified':True,'preserved_source_and_assets_diff_empty':True,'existing_old_paths_unchanged':len(oldnames)-len(changed),'existing_changed_paths':changed,'old_run04_files_byte_unchanged':len(files),'old_run04_bytes':old['total_bytes'],'baseline':rec(Path('docs/research/e2e-evaluation-v2-selection-baseline.json')),'public_driver':rec(Path('docs/research/e2e-guard-cadence-public-check.py')),'native_public_qualification':'NOT_RUN_NEXT_GATE','fresh_full_run':'NOT_RUN','uncaptured_interactive_RED_receipts':'disclosed_not_reconstructed'}
(d/'acceptance.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
