from pathlib import Path
import argparse,json,time,hashlib,resource,platform,torch
from famjet.config import load_config
from famjet.analysis.development import run_development
from famjet.train import _source
import famjet.train as train
from famjet.models.task_model import TaskModel
from famjet.artifacts import atomic_json,append_jsonl
from famjet.eval.splits import _write_immutable
from famjet.provenance import canonical_hash
P=argparse.ArgumentParser();P.add_argument('family',choices=['jet','bank']);args=P.parse_args();family=args.family
configpath=Path(f'artifacts/task18/learned-rate-cpu64-preparation/calibration-{family}.yaml');c=load_config(configpath);out=Path(f'artifacts/task18/calibration-{family}-learned-cpu64');telemetry=Path(f'artifacts/task18/telemetry-{family}-learned-cpu64');telemetry.mkdir(exist_ok=False)
factor=1 if platform.system()=='Darwin' else 1024;base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor;started=time.perf_counter();source=_source();step=0
_write_immutable(telemetry/'procedure.json',{'source':source,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'config':str(configpath),'config_sha256':hashlib.sha256(configpath.read_bytes()).hexdigest(),'scope':'cold actual raw scan+768fit+96dev+2updates/checkpoints; configured32768, not quality','precision':'CPU float64 parameters/buffers/gradients/moments; actual AdamW step scalar float32','net_limit_bytes':201326592,'peak_boundary':'process cumulative highwater; not isolated stage live allocations','instrumentation':'external fit wrapper and optimizer pre/post hooks; no candidate arithmetic/optimizer mutation'})
def peak():return {'rss_highwater_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor,'additional_since_external_start':max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base)}
def note(stage,**kw):append_jsonl(telemetry/'stages.jsonl',{'stage':stage,'elapsed_seconds':time.perf_counter()-started,**peak(),**kw})
originalfit=TaskModel.fit_statistics

def fit(self,*a,**kw):
 note('fit_start');tick=time.perf_counter();result=originalfit(self,*a,**kw)
 note('fit_end',seconds=time.perf_counter()-tick,fit_provenance=self.fit_provenance,target_statistics_hash=canonical_hash(self.target_statistics),target_statistics=self.target_statistics,rate_logits=self.kernel.rate_source.logits.detach().tolist(),rates=self.kernel.rates.detach().tolist())
 assert canonical_hash(self.target_statistics)=='0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21'
 return result
TaskModel.fit_statistics=fit
originalopt=train.make_optimizer

def optimizer(model,config):
 opt=originalopt(model,config)
 def before(opt,a,kw):
  global step
  step+=1;gradients={name:p.grad.detach().cpu().clone() for name,p in model.named_parameters() if p.grad is not None};path=telemetry/f'gradients-step{step}.pt';torch.save(gradients,path)
  note('before_optimizer',step=step,rates=model.kernel.rates.detach().tolist(),logits=model.kernel.rate_source.logits.detach().tolist(),rate_logit_gradients=model.kernel.rate_source.logits.grad.detach().tolist(),all_gradients_finite=all(bool(torch.isfinite(g).all()) for g in gradients.values()),gradient_dtypes=sorted({str(g.dtype) for g in gradients.values()}),gradient_bytes=sum(g.numel()*g.element_size() for g in gradients.values()),gradient_file_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
 def after(opt,a,kw):
  states=list(opt.state.values());note('after_optimizer',step=step,rates=model.kernel.rates.detach().tolist(),logits=model.kernel.rate_source.logits.detach().tolist(),optimizer_tensor_bytes=sum(v.numel()*v.element_size() for s in states for v in s.values() if isinstance(v,torch.Tensor)),moment_dtypes=sorted({str(s['exp_avg'].dtype) for s in states}),step_counter_dtypes=sorted({str(s['step'].dtype) for s in states}))
 opt.register_step_pre_hook(before);opt.register_step_post_hook(after);return opt
train.make_optimizer=optimizer
try:
 result=run_development(c,out);assert result['training_run']['completed_step']==2 and result['configured_training_horizon']==32768
 note('profile_complete',profile_seconds=result['total_seconds'],profile_net_peak=result['rss_highwater_additional_bytes']);assert source==_source()
 print(json.dumps({'family':family,'status':result['status'],'completed':2,'configured':32768,'profile_seconds':result['total_seconds'],'net_peak_bytes':result['rss_highwater_additional_bytes'],'checkpoint':result['checkpoint'],'external_seconds':time.perf_counter()-started}),flush=True)
except BaseException as exc:
 note('profile_failed',error_type=type(exc).__name__,message=str(exc));raise
finally:
 atomic_json(telemetry/'cost.json',{'full_external_seconds':time.perf_counter()-started,**peak(),'source':source})
