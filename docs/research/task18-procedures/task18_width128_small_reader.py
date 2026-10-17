from pathlib import Path
import copy,json,hashlib,time,resource,platform,torch
from famjet.config import load_config
from famjet.train import make_model,move_episode,history_loss,_source,check_smoke_memory
from famjet.analysis.development import draw_config
from famjet.data.synthetic import generate_episode
from famjet.types import FeatureBatch
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
out=Path('artifacts/task18/width128-initial-reader');out.mkdir(exist_ok=False);torch.set_num_threads(4);started=time.perf_counter();factor=1 if platform.system()=='Darwin' else 1024;base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor
procedure={'source':_source(),'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'fixture':'predeclared first training ordinal0, N128 piecewise_stationary; both families; same captured independently summed memory features','scope':'fresh actual width128 production reader task prediction/loss/reader parameters/raw-feature-input gradients; no fit or full upstream task-gradient certification before actualcoldfit','normalization':'fresh identity feature/output transforms; no training statistics fitted here','rtol':1e-12,'atol':1e-12,'net_cap_bytes':201326592,'power_override':False};_write_immutable(out/'procedure.json',procedure)
def metric(a,b):
 if a is None or b is None:return {'accepted':a is None and b is None,'inactive':a is None and b is None}
 a=a.detach();b=b.detach();ratio=(a-b).abs()/(1e-12+1e-12*b.abs());return {'accepted':bool(torch.isfinite(ratio).all() and (ratio<=1).all()),'max_pointwise_ratio':float(ratio.max()),'max_absolute_error':float((a-b).abs().max())}
records={}
for family in ('jet','bank'):
 c=load_config(Path(f'artifacts/task18/width128-initial-gate/{family}-numeric.yaml'));torch.manual_seed(c.seed);m=make_model(c);ref=copy.deepcopy(m)
 tensorpath=Path(f'artifacts/task18/width128-initial-{family}/case-00.pt');saved=torch.load(tensorpath,map_location='cpu',weights_only=True);x=saved['features'].clone().requires_grad_();xr=saved['reference_features'].clone().requires_grad_();dc,hid=draw_config(c,0);ep=move_episode(generate_episode(dc,c.development.data_seed,hid),'cpu',dtype=torch.float64)
 flags={'failure':torch.zeros_like(ep.supported)};a=m.read_features(FeatureBatch(x,ep.supported,flags),ep.queries);b=ref.read_features(FeatureBatch(xr,ep.supported,flags),ep.queries);la=history_loss(m,a,ep);lb=history_loss(ref,b,ep);params=list(m.reader.named_parameters());rparams=list(ref.reader.named_parameters());ga=torch.autograd.grad(la,(x,*[p for _,p in params]),allow_unused=True);gb=torch.autograd.grad(lb,(xr,*[p for _,p in rparams]),allow_unused=True)
 checks={'prediction':metric(a.prediction,b.prediction),'task_loss':metric(la,lb),'raw_feature_gradient':metric(ga[0],gb[0]),**{f'reader_gradient.{n}':metric(v,w) for (n,_),v,w in zip(params,ga[1:],gb[1:])}}
 records[family]={'history_id':hid,'candidate_capture_sha256':hashlib.sha256(tensorpath.read_bytes()).hexdigest(),'checks':checks,'rates':m.kernel.rates.detach().tolist(),'input_width':m.reader.input_dim,'reader_width':m.reader.width,'fit_provenance':m.fit_provenance,'max_ratio':max(v.get('max_pointwise_ratio',0) for v in checks.values()),'accepted':all(v['accepted'] for v in checks.values())};atomic_json(out/'progress.json',records);check_smoke_memory(c,max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base))
 del m,ref,saved,x,xr,ep,a,b,la,lb,params,rparams,ga,gb
summary={'status':'passed' if all(r['accepted'] for r in records.values()) else 'failed','source':_source(),'families':records,'seconds':time.perf_counter()-started,'rss_additional_bytes':max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base),'scope':procedure['scope']};atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)
