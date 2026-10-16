"""Task14 common-reader diagnostic inventory for the actual delta task objective."""
import json,sys
from dataclasses import replace
from pathlib import Path
import torch
sys.path.insert(0,'tests')
from test_delta import delta_config,delta_events,queries
from famjet.train import make_model
from famjet.types import Episode
from famjet.eval.isolation import export_method,_reconstruct

torch.set_num_threads(1); rows=[]
def report(a,b):
 a=a.detach().cpu().double(); b=b.detach().cpu().double(); error=(a-b).abs(); ratio=error/(1e-6+1e-5*b.abs())
 i=int(ratio.flatten().argmax())
 return {'max_abs':float(error.max()),'pointwise_ratio':float(ratio.max()),'norm_ratio':float(error.norm()/(1e-6+1e-5*b.norm())),
         'reference_norm':float(b.norm()),'actual_norm':float(a.norm()),'worst_flat_index':i,
         'worst_actual':float(a.flatten()[i]),'worst_reference':float(b.flatten()[i]),'shape':list(a.shape)}
for device in ('cpu','mps'):
 if device=='mps' and not torch.backends.mps.is_available(): raise RuntimeError('native MPS unavailable')
 torch.manual_seed(150); m=make_model(delta_config(device=device,erase_policy='pinned_guarded'))
 e=delta_events(torch.float32,device); q=queries(e,[[8,10],[7,11]])
 ep=Episode(e,q,torch.ones(2,2,2,device=device),torch.ones(2,2,dtype=torch.bool,device=device),metadata={'split':'training'})
 m.fit_statistics([ep]); wire=export_method(m); oracle=_reconstruct(wire).double()
 Path(f'artifacts/task15-evidence/task-gradient-model-{device}.json').write_text(json.dumps(wire)+'\n')
 e64=replace(e,values=e.values.cpu().double().requires_grad_(),key_features=e.key_features.cpu().double().requires_grad_(),present=e.present.cpu(),observed=e.observed.cpu())
 q64=replace(q,key_features=q.key_features.cpu().double(),present=q.present.cpu())
 e=replace(e,values=e.values.clone().requires_grad_(),key_features=e.key_features.clone().requires_grad_())
 ref=oracle(e64,q64,encode_mode='stream'); got=m(e,q,encode_mode='stream')
 lr=oracle.loss(ref,replace(ep,events=e64,queries=q64,labels=ep.labels.cpu().double(),supported=ep.supported.cpu()))
 la=m.loss(got,replace(ep,events=e)); lr.backward(); la.backward()
 gradients={name:report(p.grad,r.grad) for (name,p),(_,r) in zip(m.named_parameters(),oracle.named_parameters()) if p.grad is not None}
 row={'device':device,'seed':150,'loss_fp32':float(la.detach()),'loss_fp64':float(lr.detach()),
      'prediction':report(got.prediction,ref.prediction),'input_value_gradient':report(e.values.grad,e64.values.grad),
      'input_key_gradient':report(e.key_features.grad,e64.key_features.grad),'parameter_gradients':gradients,
      'limits':'native/input/output pointwise1e-5/1e-6; common-reader Frobenius same numbers, original diagnostics retained'}
 rows.append(row)
Path('artifacts/task15-evidence/task-gradient-audit.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps([{'device':r['device'],'loss_fp32':r['loss_fp32'],'loss_fp64':r['loss_fp64'],
                  'output_pointwise':r['prediction']['pointwise_ratio'],
                  'max_parameter_pointwise':max(g['pointwise_ratio'] for g in r['parameter_gradients'].values()),
                  'max_parameter_norm':max(g['norm_ratio'] for g in r['parameter_gradients'].values())} for r in rows],indent=2))
