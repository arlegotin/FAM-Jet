"""External production orchestration. Imported only after complete authority.

Helpers below do not run on import. No source definition/history crosses into
the clean reader worker; it receives the existing closed numeric request only.
"""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time

import torch
from famjet.eval import isolation
from famjet.eval.state_io import (snapshot_record,snapshot_from_record,snapshot_hash,
                                  tensor_record,tensor_from_record,state_bytes,_decode)
from famjet.memory._fixed_writer import _digest_tensor
from famjet.types import EventBatch,QueryBatch
from . import authority,reference
from .descriptors import fixtures,timeline
from .driver import CommonFailure,CandidateFailure


def clone(state):
    return snapshot_from_record(snapshot_record(state),state.parameter_hash)


def inject(state,*,scale,poison):
    copied=clone(state)
    for key in ('z','h'):
        if key in copied.payload: copied.payload[key]*=scale
    if poison:
        # Exact sentinel bits; never an event value or JSON NaN literal.
        copied.payload['z'][0,0,0,0,0]=struct.unpack('<d',struct.pack('<Q',0x7ff8000000000000))[0]
    return copied


def transport_snapshot(state,slot,family,parameter_hash):
    copied=clone(state)
    copied.payload['history_hash'][0]=_digest_tensor(slot.history_id)
    if slot.transform=='O': copied=replace(copied,last_time=copied.last_time+16 if bool(copied.valid[0]) else copied.last_time)
    elif slot.transform=='U':
        copied=replace(copied,last_time=copied.last_time*8,parameter_hash=parameter_hash)
        if bool(copied.payload['time_unit_hash'].any()): copied.payload['time_unit_hash']=_digest_tensor('task18-unit8')
    elif slot.transform=='R' and family=='jet':
        z,h=copied.payload['z'],copied.payload['h']
        l0=z.clone(); l1=z-2*h
        copied.payload['z']=l0; copied.payload['h']=(l0-l1)/2
    elif slot.transform=='R':
        copied=_decode(state_bytes(copied),copied.parameter_hash)
    return copied


def make_events(row,history_id):
    records=timeline(row,'I'); n=len(records)
    keys=torch.zeros((1,n,16),dtype=torch.float64)
    for j,event in enumerate(records): keys[0,j,event['key']]=1
    return EventBatch((history_id,),torch.arange(n)[None],
            torch.tensor([[e['time'] for e in records]],dtype=torch.float64),
            torch.tensor([[e['key'] for e in records]],dtype=torch.int64),keys,
            torch.tensor([[e['values'] for e in records]],dtype=torch.float64).reshape(1,n,8),
            torch.tensor([n]),torch.ones((1,n),dtype=torch.bool),
            torch.tensor([[[e['observed']]*8 for e in records]],dtype=torch.bool).reshape(1,n,8),'task18-unit1')


def make_query(row,slot):
    unit=8. if slot.transform=='U' else 1.; shift=16. if slot.transform=='O' else 0.
    key=torch.zeros((1,1,16),dtype=torch.float64); key[0,0,0]=1
    return QueryBatch((slot.history_id,),torch.tensor([[slot.query_id]]),
            torch.tensor([[row.T*unit+shift]],dtype=torch.float64),torch.zeros((1,1),dtype=torch.int64),key,
            ((row.task,),),torch.tensor([[row.lower*unit]],dtype=torch.float64),
            torch.tensor([[row.upper*unit]],dtype=torch.float64),torch.ones((1,1),dtype=torch.bool),torch.ones(1,dtype=torch.int64))


def finite(value):
    if isinstance(value,Decimal): return str(value)
    if isinstance(value,torch.Tensor): return finite(value.tolist())
    if isinstance(value,dict): return {k:finite(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [finite(v) for v in value]
    if type(value) is float and not math.isfinite(value): return None
    return value


class Backend:
    def __init__(self,seal,root):
        self.seal=seal; self.root=Path(root); self.out=Path(seal['pending']['output_directory'])
        self.models={}; self.canonical={}; self.references={}; self.rows=fixtures(); self.baselines={}
        self.metadata=json.loads((self.root/'validation/kernel_stage_a/frozen-training-metadata.json').read_bytes())
        torch.set_num_threads(1); torch.set_num_interop_threads(1)

    def event(self,kind,**fields):
        with (self.out/'monitor-events.jsonl').open('a') as f:
            f.write(json.dumps(dict(event=kind,monotonic=time.monotonic(),**fields))+'\n')

    def setup(self,candidate,ledger):
        family,rho=candidate; self.event('candidate_start')
        record=self.seal['pending']['static_exports'][f'{family}:{rho.hex()}']
        spec=json.loads((self.root/record['path']).read_bytes())
        if type(spec) is dict and set(spec)=={'candidate','status','factor_diagnostics'}:
            if spec['candidate']!=[family,rho.hex()] or spec['status']!='FAILED':
                raise CommonFailure('failed-factor record schema mismatch')
            ledger.events.append(dict(kind='factor_applicability_failure',**spec))
            self.event('candidate_end')
            raise CandidateFailure('sealed static factor applicability failure: '+repr(spec['factor_diagnostics']))
        model=ledger.call('static_reconstruction',isolation._reconstruct,spec,freeze_rates=True)
        if model.reader.family!=family or model.reader.ridge!=rho: raise CommonFailure('static candidate mismatch')
        meta=self.metadata[family]
        if model.fit_provenance!=meta['fit_provenance'] or model.target_statistics!=meta['target_statistics']:
            raise CommonFailure('frozen training metadata mismatch')
        rate_file=self.seal['pending']['represented_rate_records'][family]['path']
        rates=json.loads((self.root/rate_file).read_bytes())
        if rates!=[x.hex() for x in model.kernel.rates[0].tolist()]: raise CommonFailure('represented rate mismatch')
        unit_spec=deepcopy(spec); kernel_spec=unit_spec['schema']['kernel']
        transported=model.kernel.rates/8
        kernel_spec['weights']['rates']=tensor_record(transported); kernel_spec['schema']['t_ref']*=8
        unit_kernel=ledger.call('unit_kernel_reconstruction',isolation._reconstruct,kernel_spec,freeze_rates=True)
        parent={k:meta[k] for k in ('fit_provenance','target_statistics')}
        derived,audit=authority.unit_metadata(parent,unit_kernel._parameter_hash(),model.kernel.rates[0].tolist(),transported[0].tolist())
        unit_spec['schema'].update(derived)
        config=unit_spec['schema']['reader']['config']; config['t_ref']*=8; config['prior_scale']*=8
        unit_model=ledger.call('unit_static_reconstruction',isolation._reconstruct,unit_spec,freeze_rates=True)
        self.models[candidate]=(model,unit_model,spec,unit_spec)
        self.references[candidate]={}
        for precision in (80,160):
            with reference.context(precision):
                factors=ledger.call('reference_setup',reference.Factors,family,model.kernel.rates[0].tolist(),model.kernel.t_ref,model.reader.prior_scale,rho)
                self.references[candidate][precision]=factors
        with reference.context(160):
            a,b=(self.references[candidate][p] for p in (80,160))
            reference.agree(a.gram,b.gram)
            factor_check=reference.compare({'code':0,'prediction':sum(model.reader.gram.tolist(),[])},
                                           {'code':0,'prediction':sum(b.gram,[])})
        if factor_check['status']!='PASS': raise CommonFailure('production/reference Gram gate failed')
        (self.out/f'statics-{family}-{rho.hex()}.json').write_bytes(authority.canonical(finite(dict(
             unit_transport=audit,ownership=model.ownership_ledger(),unit_ownership=unit_model.ownership_ledger(),
             factor_diagnostics=model.reader.factor_diagnostics(),gram_gate=factor_check))))

    def canonical_snapshot(self,candidate,row,slot,ledger):
        family=candidate[0]; key=(family,row.number)
        if key not in self.canonical:
            if slot.transform!='I': raise CommonFailure('missing originally listed cold snapshot')
            model=self.models[candidate][0]
            if row.events:
                events=ledger.call('event_materialization',make_events,row,slot.history_id)
                state=ledger.call('encode',model.encode,events)
            else: state=ledger.call('empty_snapshot',model.init_state,1,device='cpu',dtype='float64')
            state=ledger.call('injection_copy',inject,state,scale=row.scale,poison=row.poison)
            raw=ledger.call('state_serialization',state_bytes,state)
            path=self.out/f'canonical-{family}-{row.number:02}.json'
            ledger.call('artifact_write',path.write_bytes,raw)
            self.canonical[key]=path
        return ledger.call('state_deserialization',_decode,self.canonical[key].read_bytes())

    def clean_read(self,spec,state,query,ledger):
        request=dict(method=spec,state=ledger.call('state_record',snapshot_record,state),
                     queries=isolation._query_record(query),operation='read',model_hash=authority.digest(spec),source_hash=authority.PACKAGE)
        raw=ledger.call('request_serialization',authority.canonical,request)
        bootstrap='import sys; sys.path.insert(0,'+repr(str(self.root))+'); from validation.kernel_stage_a.reader_worker import main; main()'
        env={'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','VECLIB_MAXIMUM_THREADS':'1',
             'NUMEXPR_NUM_THREADS':'1','PYTORCH_ENABLE_MPS_FALLBACK':'0','PYTORCH_MPS_FAST_MATH':'0'}
        ordinal=ledger.counts['read_dispatch']
        stdout_path=self.out/f'reader-{ordinal:03}.jsonl'; stderr_path=self.out/f'reader-{ordinal:03}.stderr'
        with tempfile.TemporaryDirectory(prefix='reader-',dir=self.out) as work,stdout_path.open('wb') as stdout,stderr_path.open('wb') as stderr:
            result=ledger.call('read_dispatch',subprocess.run,[sys.executable,'-I','-c',bootstrap,str(self.out/'monitor-events.jsonl')],
                   input=raw,stdout=stdout,stderr=stderr,cwd=work,env=env,timeout=90,close_fds=True)
        # Flushed entry counters persist even when the whole group is killed.
        lines=stdout_path.read_bytes().splitlines(); response=None
        for line in lines:
            item=json.loads(line)
            if set(item)=={'counter'}:
                ledger.counts['worker:'+item['counter']]+=1
                if item['counter']=='read': ledger.counts['read']+=1
            else: response=item
        if result.returncode: raise CommonFailure('reader engine/prerequisite failure: '+stderr_path.read_text(errors='replace')[-2000:])
        if response is None: raise CommonFailure('missing reader result')
        if response['counts'].get('factor',0): raise CommonFailure('unexpected reader factorization')
        return response

    def slot(self,candidate,slot,ledger):
        family,rho=candidate; row=self.rows[slot.row-1]; unit=slot.transform=='U'
        model,umodel,spec,uspec=self.models[candidate]; active=umodel if unit else model
        state=self.canonical_snapshot(candidate,row,slot,ledger)
        state=ledger.call('transform_copy',transport_snapshot,state,slot,family,active._parameter_hash())
        path=self.out/f'input-{family}-{rho.hex()}-{slot.row:02}-{slot.transform}.json'
        ledger.call('artifact_write',path.write_bytes,ledger.call('state_serialization',state_bytes,state))
        state=ledger.call('state_deserialization',_decode,path.read_bytes(),active._parameter_hash())
        query=make_query(row,slot); before=snapshot_hash(state)
        response=self.clean_read(uspec if unit else spec,state,query,ledger)
        if before!=snapshot_hash(state): raise CommonFailure('saved snapshot mutated')
        resumed=ledger.call('resume_ownership_copy',clone,state)
        if snapshot_hash(resumed)!=before or any(a.untyped_storage()._cdata==resumed.payload[k].untyped_storage()._cdata for k,a in state.payload.items()):
            raise CommonFailure('resume ownership mismatch')
        result=response['numeric']; diagnostics=result['diagnostics']; code=diagnostics['failure_code'][0][0]
        p=dict(code=next((c for c in code if c),0),prediction=result['prediction'][0][0],windows=response['windows'],
               coefficients=response['coefficients'],window_vectors=response['window_vectors'])
        if row.poison:
            if not diagnostics['quarantined'][0][0] or code[0]!=1 or not result['failure'][0][0]:
                raise CommonFailure('nonfinite quarantine policy mismatch')
            fallback=self.metadata[family]['target_statistics']['tasks'][row.task]['mean']
            ok=p['prediction']==fallback
            return dict(reader_arithmetic='PASS' if ok else 'FAILED',source_state_fidelity='NONFINITE_POLICY_SENTINEL',
                        strict_end_to_end='NONFINITE_POLICY_SENTINEL',end_to_end_gate='PASS' if ok else 'FAILED',
                        stop='continue' if ok else 'candidate',snapshot_sha256=before,worker_counts=response['counts'])
        fallback=self.metadata[family]['target_statistics']['tasks'][row.task]['mean']
        parts=[state.payload[k][0,0,:,0,:] for k in active.kernel._state_keys]
        canonical=torch.stack(parts,1).flatten(0,1) if family=='jet' else parts[0]
        values={}
        for precision in (80,160):
            with reference.context(precision):
                f=self.references[candidate][precision]
                n=[reference.exact(x) for x in canonical[:,-1].tolist()]
                u=[[reference.exact(x) for x in col] for col in canonical[:,:-1].tolist()]
                delay=reference.exact(query.T[0,0].item())-reference.exact(state.last_time[0].item())
                na,ua=reference.advance(f,n,u,delay,active.kernel.t_ref)
                shift=16. if slot.transform=='O' else 0.
                nb,ub=reference.event_state(f,timeline(row,slot.transform),shift,active.kernel.t_ref,row.scale)
                nb,ub=reference.advance(f,nb,ub,reference.exact(query.T[0,0].item())-reference.exact(shift),active.kernel.t_ref)
                kw=dict(lower=reference.exact(query.age_start[0,0].item())/reference.exact(active.kernel.t_ref),
                        upper=reference.exact(query.age_end[0,0].item())/reference.exact(active.kernel.t_ref),
                        task=row.task,fallback=fallback,solve_call=lambda fn:ledger.call('reference_solve',fn),invalid=not bool(state.valid[0]))
                a=reference.evaluate(f,na,ua,**kw); b=reference.evaluate(f,nb,ub,**kw)
                values[precision]=(a,b,na,ua,nb,ub)
        with reference.context(160):
            a,b,na,ua,nb,ub=values[160]
            for low,high in zip(values[80][:2],values[160][:2]): reference.validate_pair(low,high)
            for low,high in zip(values[80][2:],values[160][2:]): reference.agree(low,high)
            outcome=reference.compare_three(p,a,b)
            state_check=reference.compare({'code':0,'prediction':na+sum(ua,[])},{'code':0,'prediction':nb+sum(ub,[])})
            if state_check['status']=='FAILED': outcome.update(source_state_fidelity='FAILED',end_to_end_gate='FAILED')
            outcome['source_contractions']=state_check
            if slot.transform=='I': self.baselines[(candidate,slot.row)]=(p,a,b)
            else:
                originals=self.baselines.get((candidate,slot.row))
                if originals:
                    checks=[reference.compare(now,old) for now,old in zip((p,a,b),originals)]
                    outcome['transform_checks']=checks
                    if checks[0]['status']=='FAILED' and checks[1]['status']=='PASS':
                        outcome.update(reader_arithmetic='FAILED',stop='candidate')
                    if checks[1]['status']=='FAILED' or checks[2]['status']=='FAILED':
                        outcome.update(source_state_fidelity='FAILED',end_to_end_gate='FAILED')
            evidence=finite(dict(P=p,A=a,B=b,snapshot_sha256=before,outcome=outcome,counts=response['counts']))
        ledger.call('artifact_write',(self.out/f'result-{family}-{rho.hex()}-{slot.row:02}-{slot.transform}.json').write_bytes,
                    ledger.call('result_serialization',authority.canonical,evidence))
        if slot.transform=='R' and slot.row==32: self.event('candidate_end')
        return outcome
