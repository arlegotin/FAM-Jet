from pathlib import Path
import torch,json,time,hashlib,resource,platform
from famjet.eval.oracle import exact_targets
from famjet.data.synthetic import batch_hash,batch_hash_tensor
from famjet.artifacts import atomic_json
from famjet.train import _source
start=time.perf_counter();base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;factor=1 if platform.system()=='Darwin' else 1024
out={'source':_source(),'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'reason':'External fixture Episode.metadata omitted target_semantics; fit_target_statistics defaults metadata to schema1. Exact label construction used current oracle default version2. Original artifacts are unchanged.','scope':'reader-only control normalization; no scientific central scorer/schema2 path certification','families':{}}
for family in ('jet','bank'):
 p=Path(f'artifacts/task18/reader-sufficiency-{family}/external-features.pt');saved=torch.load(p,map_location='cpu',weights_only=False);checks={}
 for name in ('train','heldout'):
  ep=saved[name];truth=exact_targets(ep.events,ep.queries,arithmetic_version=2);identity=saved['fixture_identity'][name];checks[name]={'histories':len(ep.events.history_ids),'queries':int(ep.queries.present.sum()),'oracle_semantics':truth.metadata['target_semantics'],'exact_label_hash_matches':batch_hash_tensor(truth.target)==identity['exact_labels'],'presented_label_bitwise_matches':torch.equal(ep.labels,truth.target.float()),'events_hash_matches':batch_hash(ep.events)==identity['events'],'query_hash_matches':batch_hash(ep.queries)==identity['queries'],'metadata_target_semantics':ep.metadata.get('target_semantics'),'failed_queries':int(truth.failure.sum())};assert all(checks[name][k] for k in ('exact_label_hash_matches','presented_label_bitwise_matches','events_hash_matches','query_hash_matches'));assert checks[name]['failed_queries']==0
 out['families'][family]={'saved_transport_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'statistics_schema':saved['target_statistics']['schema_version'],'checks':checks};del saved
 assert (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss-base)*factor<=201326592
out['status']='all_saved_exact_and_presented_labels_match_current_v2';out['seconds']=time.perf_counter()-start;out['rss_additional_bytes']=(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss-base)*factor
atomic_json(Path('artifacts/task18/reader-sufficiency-label-audit.json'),out);print(json.dumps(out))
