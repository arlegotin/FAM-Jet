"""Bounded external fixed-feature transport for declared finite training corpora."""
from dataclasses import asdict,dataclass
from pathlib import Path
import hashlib
import io
import json
import platform
import resource
import shutil
import time
import torch
from famjet.artifacts import atomic_bytes,atomic_json
from famjet.provenance import canonical_hash
from famjet.types import FeatureBatch,QueryBatch
from famjet.data.development_cache import TrainingDrawCache


def _require_fixed_upstream(model):
    family=model.kernel.reader_feature_spec['family']
    if (family not in {'jet','bank','multiscale'}
            or (family=='multiscale' and model.kernel.reference_tensor.dtype!=torch.float64)
            or model.inference_config['writer']!='fixed' or model.inference_config['rate_mode']!='fixed'
            or model.writer is not None or model.query_map is not None
            or any(p.requires_grad for n,p in model.named_parameters() if not n.startswith('reader.'))):
        raise ValueError('fixed features forbid learned upstream parameters')


def feature_identity(config,model):
    _require_fixed_upstream(model)
    from famjet.eval.state_io import tensor_record
    from famjet.eval.isolation import source_identity
    from famjet.train import ROOT
    from famjet.analysis.development import fixed_basis_cpu64
    d=config.development
    if (model.kernel.reference_tensor.dtype!=getattr(torch,config.model.precision)
            or model.kernel.reference_tensor.device.type!=config.resources.device
            or model.kernel.reader_feature_spec['family']!=config.model.method):
        raise ValueError('feature cache model/config precision or family identity mismatch')
    read_policy={}
    if config.model.method in {'jet','bank'}:
        if (model.kernel.eps!=config.model.epsilon
                or model.kernel.support_floor!=config.model.numerical_support_floor):
            raise ValueError('feature cache read policy identity mismatch')
        read_policy={'epsilon':model.kernel.eps,
                     'numerical_support_floor':model.kernel.support_floor}
    if (d is None or d.corpus_histories is None or d.cache_manifest_path is None
            or config.resources.device!='cpu'
            or not (fixed_basis_cpu64(config) or (config.model.precision=='float32' and config.model.method in {'jet','bank'})) or config.model.writer!='fixed'
            or (config.model.rates is not None and config.model.rates.mode!='fixed') or model.writer is not None or model.query_map is not None
            or any(p.requires_grad for n,p in model.named_parameters() if not n.startswith('reader.'))):
        raise ValueError('fixed features require authorized CPU finite corpus with no learned upstream parameters')
    if model.fit_provenance is None:raise ValueError('fixed features require frozen training preprocessing')
    return {'version':2,'source_hash':source_identity(),'read_policy':read_policy,
            'lock_hash':hashlib.sha256((ROOT/'requirements.lock').read_bytes()).hexdigest(),
            'raw_manifest_hash':d.cache_manifest_hash,'corpus_histories':d.corpus_histories,
            'writer_rates_hash':model._parameter_hash(),'reader_schema':model.reader.schema,
            'feature_mean':tensor_record(model.reader.feature_mean),'feature_scale':tensor_record(model.reader.feature_scale),
            'target_statistics_hash':canonical_hash(model.target_statistics),'fit_provenance':model.fit_provenance,
            't_ref':model.kernel.t_ref,'device':'cpu','precision':config.model.precision,'encode':config.model.encode,
            'queries':config.data.queries_per_history,'input_dim':model.reader.input_dim,'value_dim':config.data.value_dim}


@dataclass(frozen=True)
class FeatureTrainingExample:
    features: FeatureBatch
    queries: QueryBatch
    labels: torch.Tensor
    supported: torch.Tensor
    metadata: dict
    event_count: int

    @property
    def history_id(self):return self.queries.history_ids[0]


def feature_record(model,episode,encode_mode):
    """Only fixed upstream parameters may be detached; no history is retained."""
    _require_fixed_upstream(model)
    from famjet.train import move_episode
    episode=move_episode(episode,'cpu',dtype=model.kernel.reference_tensor.dtype)
    with torch.no_grad():f=model.features(model.encode(episode.events,mode=encode_mode),episode.queries)
    return {'values':f.values.detach().clone(),'feature_supported':f.supported.clone(),
            'failure':f.diagnostics['failure'].clone(),'queries':asdict(episode.queries),
            'labels':episode.labels.clone(),'supported':episode.supported.clone(),
            'metadata':episode.metadata,'event_count':int(episode.events.lengths[0])}


def prepare_feature_cache(config,model,directory,*,projected_data_bytes,output_reserve_bytes):
    identity=feature_identity(config,model)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    count=config.development.corpus_histories;overhead=count*2048
    free=shutil.disk_usage(directory).free
    record={'status':'preparing','identity':identity,'entries':[],
            'storage_projection':{'data_bytes':projected_data_bytes,'manifest_overhead_bytes':overhead,
                'output_reserve_bytes':output_reserve_bytes,'observed_free_bytes':free,
                'required_free_bytes':projected_data_bytes+overhead+output_reserve_bytes}}
    atomic_json(directory/'preparation.json',record)
    if free<projected_data_bytes+overhead+output_reserve_bytes:raise ValueError('insufficient feature-cache disk capacity')
    factor=1 if platform.system()=='Darwin' else 1024
    baseline=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor
    started=time.perf_counter();total=0;delivery=0.;encoding=0.;writing=0.
    preparation={'scope':'unique_corpus_encode_and_feature_reads_forward_only',
        'cpu_fp64_exponentials':0,'matrix_cubic_work':0,'encode_advances':0,'query_advances':0}
    record['upstream_preparation_totals']=preparation
    try:
        raw=TrainingDrawCache(config);record['raw_verification']=raw.verification
        for i in range(count):
            tick=time.perf_counter();ep=raw.read(i);delivery+=time.perf_counter()-tick
            if config.model.method=='multiscale':
                cost=model.kernel.call_preparation_cost(ep.events,ep.queries,mode=config.model.encode,reader_kind=config.model.reader.kind)
                for key in preparation:
                    if key!='scope':preparation[key]+=cost[key]
            tick=time.perf_counter();wire=feature_record(model,ep,config.model.encode);encoding+=time.perf_counter()-tick
            tick=time.perf_counter();buffer=io.BytesIO();torch.save(wire,buffer);payload=buffer.getvalue()
            filename=f'{i:012d}.pt';atomic_bytes(directory/filename,payload);writing+=time.perf_counter()-tick
            total+=len(payload)
            record['entries'].append({'ordinal':i,'episode_id':ep.events.history_ids[0],
                'length':wire['event_count'],'file':filename,'bytes':len(payload),
                'sha256':hashlib.sha256(payload).hexdigest(),'raw_sha256':raw.entries[i]['sha256'],
                'hashes':ep.metadata['hashes']})
            if total>projected_data_bytes:raise ValueError('feature cache exceeds prospective disk projection')
        record.update(status='complete',total_bytes=total,total_seconds=time.perf_counter()-started,
            raw_delivery_seconds=delivery,encoding_seconds=encoding,serialization_write_seconds=writing)
        atomic_json(directory/'manifest.json',record);return directory/'manifest.json'
    finally:
        record.update(elapsed_seconds=time.perf_counter()-started,actual_bytes=total,
            rss_highwater_baseline_bytes=baseline,rss_highwater_additional_bytes=max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-baseline),
            disk_free_after_bytes=shutil.disk_usage(directory).free)
        atomic_json(directory/'preparation.json',record)


class TrainingFeatureCache:
    def __init__(self,config,model,*,start_ordinal=0):
        from famjet.train import ROOT
        self.path=ROOT/config.development.feature_cache_manifest_path
        manifest=json.loads(self.path.read_text());identity=feature_identity(config,model)
        if canonical_hash(manifest)!=config.development.feature_cache_manifest_hash:raise ValueError('feature cache manifest hash mismatch')
        if manifest.get('status')!='complete' or canonical_hash(manifest['identity'])!=canonical_hash(identity):
            raise ValueError('feature cache identity mismatch')
        raw=TrainingDrawCache(config,start_ordinal=start_ordinal)
        self.entries=manifest['entries'];self.count=config.development.corpus_histories
        self.limit=config.training.optimizer_steps*config.training.effective_batch
        if len(self.entries)!=self.count or not 0<=start_ordinal<=self.limit:raise ValueError('feature cache count/order mismatch')
        tick=time.perf_counter();total=0
        for i,(entry,source) in enumerate(zip(self.entries,raw.entries)):
            if (entry['ordinal']!=i or entry['file']!=f'{i:012d}.pt' or entry['episode_id']!=source['episode_id']
                    or entry['length']!=source['length'] or entry['hashes']!=source['hashes'] or entry['raw_sha256']!=source['sha256']):
                raise ValueError('feature cache order/identity mismatch')
            total+=len(self._bytes(entry))
        if total!=manifest['total_bytes']:raise ValueError('feature cache total bytes mismatch')
        self.verification={'seconds':time.perf_counter()-tick,'bytes_read':total,
            'boundary':'actual_disk_read_sha256_all_feature_files','raw_verification':raw.verification}
        self.next_ordinal=start_ordinal;self.input_dim=model.reader.input_dim
        self.dtype=model.kernel.reference_tensor.dtype

    def _bytes(self,entry):
        payload=(self.path.parent/entry['file']).read_bytes()
        if len(payload)!=entry['bytes'] or hashlib.sha256(payload).hexdigest()!=entry['sha256']:
            raise ValueError('feature cache file bytes/hash mismatch')
        return payload

    def read(self,ordinal):
        if ordinal!=self.next_ordinal or not 0<=ordinal<self.limit:raise ValueError('feature cache order/replay forbidden')
        entry=self.entries[ordinal%self.count]
        raw=torch.load(io.BytesIO(self._bytes(entry)),weights_only=True,map_location='cpu')
        q=QueryBatch(**raw['queries']);values=raw['values']
        if (q.history_ids!=(entry['episode_id'],) or raw['metadata']['hashes']!=entry['hashes']
                or raw['event_count']!=entry['length'] or tuple(values.shape)!=(*q.T.shape,self.input_dim)
                or values.dtype!=self.dtype):raise ValueError('feature cache record identity/shape mismatch')
        f=FeatureBatch(values,raw['feature_supported'],{'failure':raw['failure']})
        self.next_ordinal+=1
        return FeatureTrainingExample(f,q,raw['labels'],raw['supported'],raw['metadata'],raw['event_count'])
