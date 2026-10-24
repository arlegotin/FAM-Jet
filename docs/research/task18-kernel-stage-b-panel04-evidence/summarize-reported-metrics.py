"""Reformat completed immutable reported metrics only; no rescore or inference."""
from pathlib import Path
import datetime,hashlib,json
R=Path('/Users/artemlegotin/Documents/git_alter/FAM-Jet');W=R/'.superpowers/sdd/2026-10-16-famjet'
O=R/'artifacts/task18-kernel-stage-b-panel-04';C=R/'artifacts/task18-kernel-stage-b-panel-04-custody'
def load(p):return json.loads(p.read_bytes())
def ref(p):
 raw=p.read_bytes();return dict(path=str(p.relative_to(R)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def main():
 publication=load(C/'publication.json');verification=load(C/'publication-verification.json');run=load(O/'stage-b.json');monitor=load(O/'monitor.json')
 assert publication['approved'] and verification['observed_actual_wrapper_returncode']==0
 assert run['status']=='COMPLETED' and run['counts']['predictions_scored']==4608 and run['counts']['worker_factors']==0
 costs={x['candidate']:x for x in verification['outcome']['costs']};rows=[]
 for r in run['combined']:
  assert r['complete'] and r['query_count']==768
  lengths=[x for x in run['summaries'] if x['candidate']==r['candidate']]
  rows.append(dict(candidate=r['candidate'],ridge=float.fromhex(r['candidate'].split(':',1)[1]),status=r['status'],normalized_loss=r['loss'],query_count=r['query_count'],fallback_count=sum(x['summary']['fallback_count'] for x in lengths),by_length=[dict(length=x['length'],summary=x['summary']) for x in lengths],charged_standalone_seconds=costs[r['candidate']]['standalone_total_seconds']))
 selected=verification['outcome']['selection'];byid={r['candidate']:r for r in rows}
 delta=(byid[selected['bank']]['normalized_loss']-byid[selected['jet']]['normalized_loss']) if all(selected.values()) else None
 result=dict(version=1,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='descriptive_exposed_development_only_no_confirmatory_inference',run=ref(O/'stage-b.json'),publication=ref(C/'publication.json'),counts=run['counts'],configurations=rows,selected=selected,selected_loss_difference_bank_minus_jet=delta,allocation_and_receipt_campaign_seconds=verification['outcome']['campaign_seconds'],charged_output_bytes=publication['charged_output_bytes'],sampled_memory={k:monitor[k] for k in ('incremental_worker_peak_bytes','absolute_process_tree_peak_bytes','observed_pid_peak_sum_bytes')},no_new_scores_or_training=True)
 p=W/'task-18-panel04-descriptive-summary.json';p.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='configurations'},indent=2))
 print(json.dumps([dict(candidate=r['candidate'],loss=r['normalized_loss'],fallbacks=r['fallback_count'],seconds=r['charged_standalone_seconds']) for r in rows],indent=2))
if __name__=='__main__':main()
