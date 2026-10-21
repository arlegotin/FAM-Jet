"""Root post-wrapper custody; only run with actual tool-observed wrapper outcome."""
from pathlib import Path
import hashlib,json,sys,time
ROOT=Path('/Users/artemlegotin/Documents/git_alter/FAM-Jet')
sys.path.insert(0,str(ROOT))
from validation.kernel_stage_b import authority as b
PREP=ROOT/'artifacts/task18-kernel-stage-b-binding-02-prep'
OUT=ROOT/'artifacts/task18-kernel-stage-b-binding-02'
CUSTODY=ROOT/'artifacts/task18-kernel-stage-b-binding-02-custody'
def ref(p,kind):
 raw=p.read_bytes();return dict(kind=kind,path=str(p.relative_to(ROOT)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def save(p,v):p.write_bytes(b.canonical(v))
def main():
 actual=int(sys.argv[1]);assert actual==0,'tool observed wrapper failure: publication forbidden'
 assert not CUSTODY.exists(),'one-use root publication'
 plan=b.strict_json((PREP/'plan.json').read_bytes())
 terminal=b.strict_json((OUT/'terminal-report.json').read_bytes())
 result=b.strict_json((PREP/'witness-result.json').read_bytes())
 assert result['status']==terminal['status']=='ELIGIBLE_PENDING_PUBLICATION'
 tr=result['terminal']; raw=(OUT/tr['path']).read_bytes()
 assert tr['bytes']==len(raw) and tr['sha256']==hashlib.sha256(raw).hexdigest()
 assert terminal['exit']==b.strict_json((PREP/'exit-witness.json').read_bytes())
 b.validate_exit_witness(plan,ROOT,terminal['exit'])
 assert terminal['exit']['returncode']==0 and terminal['failure'] is None
 charged=b.charged_bytes(str(OUT),str(PREP))
 verified=time.monotonic();receipt=verified-terminal['program_end']
 limits=plan['execution']['limits'];reserve=plan['execution']['terminal']
 assert verified<plan['execution']['boundary']['deadline_monotonic']
 assert 0<=receipt<=reserve['publication_seconds']
 assert 0<=charged-terminal['program_output_bytes']<=reserve['publication_bytes']
 assert charged<=limits['output_bytes']
 CUSTODY.mkdir()
 ruling=CUSTODY/'root-publication-ruling.md'
 ruling.write_text('''# Root post-return publication — 21 October 2026

Root observed the one-use witness command finish with actual returncode 0. Its retained terminal bytes agree with the wrapper commitment. The recorded observation includes final witness-result, stdout, preparation and output trees after the wrapper returned; no model or scientific work was released. Original deadline, receipt reserve and output caps passed. The separately recorded observer bookkeeping and this validation are external custody outside the self-measured program/receipt boundary, not a claim of zero cost. This accepts only the empty binding and leaves any numerical panel separately unreleased. Binding01 remains FAILED.
''')
 invocation=dict(version=1,witness=reserve['witness'],plan_sha256=b.digest(plan),actual_returncode=actual,publication_verified_monotonic=verified,output_bytes=charged,commit_success=True)
 save(CUSTODY/'root-invocation.json',invocation)
 pub=dict(version=1,approved=True,terminal=ref(OUT/'terminal-report.json','terminal_report'),witness=reserve['witness'],invocation=ref(CUSTODY/'root-invocation.json','root_invocation_record'),observed_witness_returncode=actual,receipt_commit_observed=True,receipt_phase_seconds=receipt,charged_output_bytes=charged,within_original_deadline=True,within_publication_budget=True,ruling=ref(ruling,'markdown'))
 outcome=b.validate_completion(plan,terminal,pub,ROOT)
 save(CUSTODY/'publication.json',pub)
 save(CUSTODY/'publication-verification.json',dict(status='ACCEPTED_EMPTY_BINDING_ONLY',observed_actual_wrapper_returncode=actual,receipt_phase_seconds=receipt,charged_output_bytes=charged,outcome=outcome,panel_released=False))
 print(json.dumps(dict(status='ACCEPTED_EMPTY_BINDING_ONLY',receipt_phase_seconds=receipt,charged_output_bytes=charged,outcome=outcome,panel_released=False),indent=2))
 return 0
if __name__=='__main__':raise SystemExit(main())
