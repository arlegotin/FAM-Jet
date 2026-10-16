"""Bounded native N128 numeric audit against independent CPU64 unrolling."""
import json,sys
from pathlib import Path
import torch
sys.path.insert(0,'tests')
from test_delta import independent_native
from famjet.memory.delta import DeltaMixer

torch.set_num_threads(1); rows=[]
def errors(g,r):
    g=g.detach().cpu().double(); r=r.detach().cpu().double(); e=(g-r).abs()
    return {'max_abs':float(e.max()),'pointwise_ratio':float((e/(1e-6+1e-5*r.abs())).max()),
            'gradient_norm':float(r.norm()),'frobenius_ratio':float(e.norm()/(1e-6+1e-5*r.norm()))}
for variant in ('gdn2','kda','gdn'):
    torch.manual_seed(15128)
    base=DeltaMixer(16,8,dim=16,head_key_dim=4,head_value_dim=4,variant=variant)
    x=torch.randn(1,128,16)
    native={n:p for n,p in base.named_parameters() if not n.startswith(('event_adapter','query_adapter'))}
    w={n:p.detach().double().requires_grad_() for n,p in native.items()}; xx=x.double().requires_grad_()
    expected=independent_native(xx,w,base)
    reference_grads=torch.autograd.grad(expected.square().sum(),(xx,*w.values()))
    for device in ('cpu','mps'):
        if device=='mps' and not torch.backends.mps.is_available(): raise RuntimeError('native MPS unavailable')
        m=DeltaMixer(16,8,dim=16,head_key_dim=4,head_value_dim=4,variant=variant).to(device)
        m.load_state_dict(base.state_dict()); inp=x.to(device).requires_grad_()
        actual,_=m.native_sequence(inp)
        params={n:p for n,p in m.named_parameters() if n in native}
        grads=torch.autograd.grad(actual.square().sum(),(inp,*params.values()))
        row={'variant':variant,'device':device,'precision':'float32','reference':'independent_cpu64_matrix_unroll',
             'seed':15128,'shape':{'B':1,'N':128,'D':16,'H':1,'K':4,'V':4,'L':4},
             'output':errors(actual,expected),'gradients':{n:errors(g,r) for n,g,r in zip(('input',*params),grads,reference_grads)}}
        row['accepted_original_pointwise']=row['output']['pointwise_ratio']<=1 and all(v['pointwise_ratio']<=1 for v in row['gradients'].values())
        rows.append(row)
Path(sys.argv[1]).write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps([{'variant':r['variant'],'device':r['device'],'output':r['output'],
                  'max_gradient_pointwise_ratio':max(v['pointwise_ratio'] for v in r['gradients'].values()),
                  'accepted_original_pointwise':r['accepted_original_pointwise']} for r in rows],indent=2))
assert all(r['accepted_original_pointwise'] for r in rows)
