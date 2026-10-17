from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timezone
import json,hashlib,io,time,torch,platform,resource
from famjet.types import Episode,EventBatch,QueryBatch
from famjet.train import move_episode,_source
from famjet.artifacts import atomic_json
from famjet.eval.splits import _write_immutable
root=Path('artifacts/task18');out=root/'fixed-basis-feature-size-audit';out.mkdir(exist_ok=False);tick=time.perf_counter();utc=datetime.now(timezone.utc);factor=1 if platform.system()=='Darwin' else 1024;base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor
rawpath=root/'cache-fixed-basis-6144/manifest.json';raw=json.loads(rawpath.read_text());partial=json.loads((root/'features-fixed-basis-6144-jet/preparation.json').read_text());existing={e['ordinal']:e for e in partial['entries']};_write_immutable(out/'procedure.json',{'source':_source(),'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'read-only existing raw payload and metadata, dummy shape-identical transport byte sizing ONLY; no generation/model/encoding/fit; validate all retained6105 real transport lengths','raw_manifest_file_sha256':hashlib.sha256(rawpath.read_bytes()).hexdigest(),'partial_preparation_file_sha256':hashlib.sha256((root/'features-fixed-basis-6144-jet/preparation.json').read_bytes()).hexdigest(),'utc_start':utc.isoformat()});rows=[]
for entry in raw['entries']:
 payload=(rawpath.parent/entry['file']).read_bytes();assert hashlib.sha256(payload).hexdigest()==entry['sha256'];w=torch.load(io.BytesIO(payload),weights_only=True);ep=move_episode(Episode(EventBatch(**w.pop('events')),QueryBatch(**w.pop('queries')),**w),'cpu',dtype=torch.float64)
 wire={'values':torch.zeros(1,8,97,dtype=torch.float64),'feature_supported':torch.zeros(1,8,dtype=torch.bool),'failure':torch.zeros(1,8,dtype=torch.bool),'queries':asdict(ep.queries),'labels':ep.labels.clone(),'supported':ep.supported.clone(),'metadata':ep.metadata,'event_count':int(ep.events.lengths[0])};b=io.BytesIO();torch.save(wire,b);n=b.getbuffer().nbytes;i=entry['ordinal'];actual=existing.get(i,{}).get('bytes')
 if i in existing:
  old=(root/'features-fixed-basis-6144-jet'/existing[i]['file']).read_bytes();assert len(old)==actual and hashlib.sha256(old).hexdigest()==existing[i]['sha256']
 assert actual is None or actual==n,(i,n,actual);rows.append({'ordinal':i,'bytes':n,'actual_retained_bytes':actual})
end=datetime.now(timezone.utc);total=sum(r['bytes'] for r in rows);maximum=max(r['bytes'] for r in rows);atomic_json(out/'sizes.json',{'rows':rows});summary={'status':'all6144_measured_and6105_real_lengths_exactly_verified','source':_source(),'total_exact_transport_bytes':total,'max_record_bytes':maximum,'prospective_max_record_times6144':maximum*6144,'same_shape_all_families':True,'scope':'size only, synthetic dummyfeature values NEVER used for training','perf_seconds':time.perf_counter()-tick,'utc_seconds':(end-utc).total_seconds(),'net_peak_bytes':max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-base),'sizes_sha256':hashlib.sha256((out/'sizes.json').read_bytes()).hexdigest()};atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)
