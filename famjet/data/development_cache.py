"""External one-pass transport of exact fresh development training draws.

No states/features or repeated epochs; this object never enters TaskModel.
"""
from dataclasses import asdict,fields
from pathlib import Path
import hashlib
import io
import json
import shutil
import resource
import platform
import time
import torch
from famjet.artifacts import atomic_bytes,atomic_json
from famjet.provenance import canonical_hash
from famjet.types import EventBatch,QueryBatch,Episode


def cache_identity(config):
    from famjet.eval.isolation import source_identity
    from famjet.train import ROOT
    d=config.development
    if d is None or config.phase!='development' or config.data.generator.namespace!='training' or config.data.generator_version!='initial_spec_v2_targets':
        raise ValueError('cache requires current development training identity')
    return {'version':1,'source_hash':source_identity(),
            'lock_hash':hashlib.sha256((ROOT/'requirements.lock').read_bytes()).hexdigest(),
            'target_semantics':'observed_event_targets_v2','data':asdict(config.data),
            'data_seed':d.data_seed,'lengths':list(d.lengths),
            'namespace':'task18_shared_training_draws_v2',
            'order':'ordinal_length_cycle_then_regime_cycle',
            'count':config.training.optimizer_steps*config.training.effective_batch}


def prepare_cache(config,directory,*,projected_data_bytes,output_reserve_bytes):
    """Caller declares measured projection and explicit output reserve beforehand."""
    from famjet.analysis.development import draw_config
    from famjet.data.synthetic import generate_episode
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    identity=cache_identity(config);count=identity['count']
    # Manifest metadata projection is explicit, includes per-entry hashes/IDs.
    overhead_bytes=count*2048;required=projected_data_bytes+overhead_bytes+output_reserve_bytes
    free=shutil.disk_usage(directory).free
    record={'status':'preparing','identity':identity,'entries':[],
            'storage_projection':{'data_bytes':projected_data_bytes,'manifest_overhead_bytes':overhead_bytes,
                'output_reserve_bytes':output_reserve_bytes,'required_free_bytes':required,'observed_free_bytes':free}}
    atomic_json(directory/'preparation.json',record)
    if free<required: raise ValueError('insufficient measured cache disk capacity')
    tick=time.perf_counter();generation=0.;writing=0.;total=0
    factor=1 if platform.system()=='Darwin' else 1024
    baseline=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor
    try:
        for ordinal in range(count):
            cc,draw_id=draw_config(config,ordinal);start=time.perf_counter()
            ep=generate_episode(cc,config.development.data_seed,draw_id);generation+=time.perf_counter()-start
            wire={'events':{f.name:getattr(ep.events,f.name) for f in fields(EventBatch) if f.init},
                  'queries':asdict(ep.queries),'labels':ep.labels,'supported':ep.supported,
                  'metadata':ep.metadata,'schema_version':ep.schema_version}
            start=time.perf_counter();buffer=io.BytesIO();torch.save(wire,buffer);payload=buffer.getvalue()
            filename=f'{ordinal:012d}.pt';atomic_bytes(directory/filename,payload);writing+=time.perf_counter()-start
            total+=len(payload)
            record['entries'].append({'ordinal':ordinal,'episode_id':draw_id,'length':cc.data.length,
                'regime':ep.metadata['regime'],'file':filename,'bytes':len(payload),
                'sha256':hashlib.sha256(payload).hexdigest(),'hashes':ep.metadata['hashes']})
            if total>projected_data_bytes: raise ValueError('measured cache exceeds prospective disk projection')
        record.update(status='complete',total_bytes=total,generation_seconds=generation,
                      serialization_write_seconds=writing,total_seconds=time.perf_counter()-tick)
        atomic_json(directory/'manifest.json',record)
        return directory/'manifest.json'
    finally:
        record.update(elapsed_seconds=time.perf_counter()-tick,actual_bytes=total,
                      rss_highwater_baseline_bytes=baseline,
                      rss_highwater_additional_bytes=max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*factor-baseline),
                      disk_free_after_bytes=shutil.disk_usage(directory).free)
        atomic_json(directory/'preparation.json',record)


class TrainingDrawCache:
    def __init__(self,config,*,start_ordinal=0):
        from famjet.analysis.development import draw_config
        from famjet.train import ROOT
        self.path=ROOT/config.development.cache_manifest_path
        manifest=json.loads(self.path.read_text())
        if canonical_hash(manifest)!=config.development.cache_manifest_hash: raise ValueError('cache manifest hash mismatch')
        if manifest.get('status')!='complete' or canonical_hash(manifest['identity'])!=canonical_hash(cache_identity(config)):
            raise ValueError('cache identity mismatch')
        self.entries=manifest['entries'];count=manifest['identity']['count']
        if len(self.entries)!=count or not 0<=start_ordinal<=count: raise ValueError('cache count/order mismatch')
        for i,entry in enumerate(self.entries):
            cc,identity=draw_config(config,i)
            if (entry['ordinal']!=i or entry['episode_id']!=identity or entry['length']!=cc.data.length
                    or entry['regime']!=cc.data.generator.regime or entry['file']!=f'{i:012d}.pt'):
                raise ValueError('cache order/identity mismatch')
        start=time.perf_counter();total=0
        for entry in self.entries:
            payload=self._bytes(entry);total+=len(payload)
        if total!=manifest['total_bytes']: raise ValueError('cache total bytes mismatch')
        self.verification={'seconds':time.perf_counter()-start,'bytes_read':total,'boundary':'actual_disk_read_and_sha256_all_files'}
        self.next_ordinal=start_ordinal

    def _bytes(self,entry):
        payload=(self.path.parent/entry['file']).read_bytes()
        if len(payload)!=entry['bytes'] or hashlib.sha256(payload).hexdigest()!=entry['sha256']:
            raise ValueError('cache file bytes/hash mismatch')
        return payload

    def read(self,ordinal):
        if ordinal!=self.next_ordinal or ordinal>=len(self.entries): raise ValueError('cache order/replay forbidden')
        entry=self.entries[ordinal]
        raw=torch.load(io.BytesIO(self._bytes(entry)),weights_only=True,map_location='cpu')
        ep=Episode(EventBatch(**raw.pop('events')),QueryBatch(**raw.pop('queries')),**raw)
        if ep.events.history_ids!=(entry['episode_id'],) or ep.metadata['hashes']!=entry['hashes']:
            raise ValueError('cache episode identity mismatch')
        self.next_ordinal+=1
        return ep
