"""Catch query-dependent writes, namespace overlap and protected data access."""
from dataclasses import replace
import json

import pytest
import torch

from test_synthetic import config


def test_history_hash_independent_of_query_seed():
    from famjet.data.synthetic import generate_episode,queries_for_history
    c=config(query_seed=1)
    a=generate_episode(c,4,'a')
    b=generate_episode(replace(c,data=replace(c.data,generator=replace(c.data.generator,query_seed=2))),4,'a')
    assert a.metadata['hashes']['events']==b.metadata['hashes']['events']
    assert a.metadata['hashes']['queries']!=b.metadata['hashes']['queries']
    # Alter values only: support/placement sampling must not inspect labels.
    changed=replace(a.events,values=a.events.values*100+37)
    queries,_=queries_for_history(changed,c,4,'a')
    assert torch.equal(a.queries.age_start,queries.age_start)
    assert torch.equal(a.queries.key_ids,queries.key_ids)


def test_delayed_query_does_not_change_history():
    from famjet.data.synthetic import generate_episode
    c=config()
    a=generate_episode(c,18,'same')
    A0=(a.events.timestamps[0,-1]-a.events.timestamps[0,0]).item()
    for delay in [0,.125,1,10]:
        d=replace(c.data.generator,population='delayed',delay_multiplier=delay)
        b=generate_episode(replace(c,data=replace(c.data,generator=d)),18,'same')
        assert a.metadata['hashes']['events']==b.metadata['hashes']['events']
        assert (b.queries.T==a.events.timestamps[0,-1]+delay*A0).all()


def test_split_namespaces_disjoint(tmp_path):
    from famjet.eval.splits import build_split_manifest,verify_split_manifest
    c=config()
    manifest=build_split_manifest(c,tmp_path/'splits.json')
    assert len(set(x['root'] for x in manifest['splits'].values()))==6
    assert set(manifest['populations'])>={'primary','presence','corrected_categorical','random_binding','boundary'}
    for name in ['pilot','confirmation','replication']:
        assert manifest['splits'][name]['status']=='reserved'
        assert manifest['splits'][name]['episodes']==[]
    assert verify_split_manifest(tmp_path/'splits.json')==manifest
    assert build_split_manifest(c,tmp_path/'splits.json')==manifest
    bad=json.loads((tmp_path/'splits.json').read_text())
    bad['splits']['confirmation']['root']=bad['splits']['training']['root']
    (tmp_path/'splits.json').write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        verify_split_manifest(tmp_path/'splits.json')
    with pytest.raises(ValueError):
        build_split_manifest(c,tmp_path/'splits.json')


def test_dense_split_ids_disjoint():
    from famjet.data.synthetic import generate_episode
    c=config()
    sets=[]
    for ns in ['training','development_fit','development_calibration']:
        g=replace(c.data.generator,namespace=ns)
        e=generate_episode(replace(c,data=replace(c.data,key_features='dense',generator=g)),8,'same')
        sets.append(set(e.events.key_ids[0].tolist()))
    assert all(not a&b for i,a in enumerate(sets) for b in sets[i+1:])


@pytest.mark.parametrize('namespace',['pilot','confirmation','replication'])
def test_exploratory_generator_rejects_protected_namespace(namespace):
    from famjet.data.synthetic import generate_episode
    c=config(namespace=namespace)
    with pytest.raises(ValueError,match='protected'):
        generate_episode(c,5,'never-open')


def test_key_load_varies_independently_of_history_span():
    from famjet.data.synthetic import generate_episode
    histories=[]
    for load in [8,16,64]:
        c=config(key_load=load,population='random_binding')
        c=replace(c,data=replace(c.data,key_features='dense',value_dim=32))
        histories.append(generate_episode(c,91,'same').events)
    assert all(torch.equal(histories[0].timestamps,h.timestamps) for h in histories[1:])
    assert all(max(h.key_ids[0].tolist())>2**63 for h in histories)


def test_manifest_verifier_rejects_incomplete_resealed_inventory(tmp_path):
    from famjet.eval.splits import build_split_manifest,verify_split_manifest
    from famjet.provenance import canonical_hash
    p=tmp_path/'splits.json'
    m=build_split_manifest(config(),p)
    m['populations']={}
    m['manifest_hash']=canonical_hash({k:v for k,v in m.items() if k!='manifest_hash'})
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='population'):
        verify_split_manifest(p)


def test_boundary_query_ids_do_not_encode_support():
    from famjet.data.synthetic import generate_episode
    patterns=[generate_episode(config(population='boundary'),13,str(i)).supported[0].tolist() for i in range(4)]
    assert any(p!=patterns[0] for p in patterns[1:])


def test_manifest_roundtrip_accepts_direct_integer_delay_config(tmp_path):
    from famjet.eval.splits import build_split_manifest,verify_split_manifest
    c=config(population='delayed',delay_multiplier=1,max_query_attempts=1)
    c=replace(c,data=replace(c.data,length=3,queries_per_history=2))
    p=tmp_path/'direct.json'
    assert build_split_manifest(c,p)==verify_split_manifest(p)


def test_hidden_cache_rejected():
    from famjet.eval.isolation import isolated_read
    from famjet.memory.exact_store import PackedHistoryMemory
    from test_exact_store import batches
    m=PackedHistoryMemory(4,2,'recent',key_dim=1); e,q=batches(); s=m.encode(e)
    m.hidden_cache=e.values.clone()
    with pytest.raises(ValueError,match='unregistered|hidden'):
        isolated_read(m,s,q)


def test_disk_history_accessor_rejected(tmp_path):
    from famjet.eval.isolation import isolated_read
    from famjet.memory.exact_store import PackedHistoryMemory
    from test_exact_store import batches
    p=tmp_path/'history'; p.write_text('forbidden history')
    class DiskReader(PackedHistoryMemory):
        def read(self,state,queries):
            p.read_text()
            return super().read(state,queries)
    m=DiskReader(4,2,'recent',key_dim=1); e,q=batches(); s=m.encode(e)
    with pytest.raises(ValueError,match='registered'):
        isolated_read(m,s,q)


def test_read_order_preserves_state_hash(tmp_path):
    from famjet.eval.isolation import isolated_read
    from famjet.eval.state_io import snapshot_hash
    from famjet.memory.exact_store import PackedHistoryMemory
    from test_exact_store import batches
    e,q=batches(); m=PackedHistoryMemory(4,2,'recent',key_dim=1); s=m.encode(e)
    original=snapshot_hash(s)
    # No raw file survives; the worker receives no raw events or path.
    p=tmp_path/'raw'; p.write_text('raw'); p.unlink(); del e
    a=isolated_read(m,s,q)
    perm=torch.tensor([3,1,0,2])
    reordered=replace(q,query_ids=q.query_ids[:,perm],tasks=(tuple(q.tasks[0][j] for j in perm),))
    b=isolated_read(m,s,reordered)
    assert snapshot_hash(s)==original
    torch.testing.assert_close(a.prediction[:,perm],b.prediction,equal_nan=True)
    assert a.prediction.tolist()==[[[12.,7.],[6.,0.],[14.,7.],[1.,0.]]]
    assert torch.equal(a.diagnostics['prediction_valid'],torch.ones(1,4,dtype=torch.bool))


def test_later_query_then_resume(tmp_path):
    from famjet.eval.isolation import isolated_read
    from famjet.eval.state_io import save_state,load_state,snapshot_hash
    from famjet.memory.exact_store import PackedHistoryMemory
    from test_exact_store import batches
    e,q=batches(); m=PackedHistoryMemory(4,2,'recent',key_dim=1); s=m.encode(e)
    p=tmp_path/'state.json'; save_state(p,s)
    r=isolated_read(m,s,replace(q,T=torch.full_like(q.T,100)))
    assert torch.isnan(r.prediction[0,0]).all() and not r.diagnostics['prediction_valid'][0,0]
    e2=replace(e,event_ids=e.event_ids+4,timestamps=e.timestamps+3)
    resumed=m.encode(e2,load_state(p,s.parameter_hash))
    uninterrupted=m.encode(e2,s)
    assert snapshot_hash(resumed)==snapshot_hash(uninterrupted)
    assert load_state(p,s.parameter_hash).last_time.item()==2


def test_old_query_rejected():
    from famjet.eval.isolation import isolated_read
    from famjet.memory.exact_store import PackedHistoryMemory
    from test_exact_store import batches
    e,q=batches(); m=PackedHistoryMemory(4,2,'recent',key_dim=1); s=m.encode(e)
    with pytest.raises(ValueError,match='before|earlier'):
        isolated_read(m,s,replace(q,T=torch.zeros_like(q.T)))
    with pytest.raises(ValueError,match='identity'):
        isolated_read(m,s,replace(q,history_ids=('wrong',)))


def test_stale_rate_state_rejected():
    from famjet.eval.isolation import isolated_features
    from famjet.memory.jet import JetMemory
    from test_exact_store import batches
    e,q=batches(); e=replace(e,key_features=e.key_features.double()); q=replace(q,key_features=q.key_features.double())
    m=JetMemory(torch.ones(1,2,dtype=torch.float64),1,2); s=m.encode(e)
    m.rates.mul_(2)
    with pytest.raises(ValueError,match='parameter'):
        isolated_features(m,s,q)
    with pytest.raises(ValueError,match='parameter'):
        m.encode(e,s)


def test_kernel_features_keep_diagnostics_without_fabricated_predictions():
    from famjet.eval.isolation import isolated_features,isolated_read
    from famjet.memory.jet import JetMemory
    from test_exact_store import batches
    e,q=batches(); e=replace(e,key_features=e.key_features.double()); q=replace(q,key_features=q.key_features.double())
    m=JetMemory(torch.ones(1,2,dtype=torch.float64,requires_grad=True),1,2); s=m.encode(e)
    expected=m.features(s,q); actual=isolated_features(m,s,q)
    torch.testing.assert_close(actual.values,expected.values)
    assert actual.values.grad_fn is None
    assert actual.diagnostics.keys()==expected.diagnostics.keys()
    for k in actual.diagnostics: torch.testing.assert_close(actual.diagnostics[k],expected.diagnostics[k],equal_nan=True)
    with pytest.raises(ValueError,match='TaskModel|read'):
        isolated_read(m,s,q)


def test_worker_denies_disk_io_and_times_out():
    import subprocess,sys
    code="from famjet.eval.isolation import _install_io_guard; _install_io_guard(); open('/dev/null').read()"
    p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=20)
    assert p.returncode!=0 and 'forbidden' in p.stderr
    from famjet.eval.isolation import isolated_read
    from famjet.memory.exact_store import PackedHistoryMemory
    from test_exact_store import batches
    e,q=batches(); m=PackedHistoryMemory(4,2,'recent',key_dim=1)
    with pytest.raises(TimeoutError): isolated_read(m,m.encode(e),q,timeout=.001)


@pytest.mark.parametrize('kind',['reservoir','hybrid','buckets','bank_learned'])
def test_registered_summary_and_learned_rate_roundtrips(kind):
    from famjet.eval.isolation import isolated_read,isolated_features
    from famjet.memory.reservoir import ReservoirMemory,HybridMemory
    from famjet.memory.buckets import TemporalBucketsMemory
    from famjet.memory.expbank import ExpBankMemory,BoundedRates
    from test_exact_store import batches
    e,q=batches()
    if kind=='bank_learned':
        m=ExpBankMemory(BoundedRates(2,-2.,1.).double(),1,2)
        e=replace(e,key_features=e.key_features.double()); q=replace(q,key_features=q.key_features.double())
        s=m.encode(e); a=isolated_features(m,s,q); b=m.features(s,q)
        torch.testing.assert_close(a.values,b.values)
    else:
        m={'reservoir':lambda:ReservoirMemory(4,2,5,key_dim=1),
           'hybrid':lambda:HybridMemory(2,4,2,5,key_dim=1),
           'buckets':lambda:TemporalBucketsMemory(4,2,key_dim=1)}[kind]()
        s=m.encode(e); a=isolated_read(m,s,q); b=m.read(s,q)
        torch.testing.assert_close(a.prediction,b.prediction,equal_nan=True)
        assert a.diagnostics.keys()==b.diagnostics.keys()
        for k in a.diagnostics: torch.testing.assert_close(a.diagnostics[k],b.diagnostics[k],equal_nan=True)


def _worker_redteam(behavior):
    """Patch trusted test process code, never a callable in the production wire."""
    import subprocess,sys
    from famjet.eval.isolation import export_method,source_identity,_query_record
    from famjet.eval.state_io import snapshot_record
    from famjet.provenance import canonical_hash,canonical_json
    from famjet.memory.exact_store import PackedHistoryMemory
    from test_exact_store import batches
    e,q=batches(); m=PackedHistoryMemory(4,2,'recent',key_dim=1); spec=export_method(m)
    request=dict(method=spec,state=snapshot_record(m.encode(e)),queries=_query_record(q),operation='read',
                 model_hash=canonical_hash(spec),source_hash=source_identity())
    patch={
        'disk':"def bad(self,s,q):\n    open('/dev/null').read()\n    return original(self,s,q)",
        'mutation':"def bad(self,s,q):\n    s.payload['values'].zero_()\n    return original(self,s,q)",
        'cache':"def bad(self,s,q):\n    self.cache=s.payload['values']\n    return original(self,s,q)",
        'source':None,
    }[behavior]
    code='from famjet.eval.isolation import _main, PackedHistoryMemory\n'
    if patch:
        code+='original=PackedHistoryMemory.read\n'+patch+'\nPackedHistoryMemory.read=bad\n'
    else: request['source_hash']='0'*64
    code+='_main()\n'
    completed=subprocess.run([sys.executable,'-c',code],input=canonical_json(request),capture_output=True,timeout=20)
    assert completed.returncode==0,completed.stderr
    return json.loads(completed.stdout)


@pytest.mark.parametrize('behavior,message',[('disk','forbidden'),('mutation','read-only'),('cache','hidden'),('source','source identity')])
def test_worker_enforces_boundary_during_actual_read(behavior,message):
    response=_worker_redteam(behavior)
    assert response['ok'] is False and message in response['error']


def test_result_json_keeps_absence_distinct_from_failure():
    from famjet.eval.isolation import isolated_read,result_json
    from famjet.memory.exact_store import PackedHistoryMemory
    from test_exact_store import batches
    e,q=batches(tasks=('mean','latest'))
    m=PackedHistoryMemory(1,2,'recent',key_dim=1); s=m.encode(e)
    q=replace(q,age_start=torch.ones_like(q.age_start),age_end=torch.full_like(q.age_end,2))
    result=isolated_read(m,s,q); report=result_json(result)
    assert torch.isnan(result.prediction[0,0]).all()
    assert report['prediction'][0][0]==[None,None]
    assert report['failure'][0][0] is False
    assert report['support'][0][0] is False
    assert report['diagnostics']['prediction_valid'][0][0] is False
    json.dumps(report,allow_nan=False)


@pytest.mark.parametrize('kind',['packed','jet'])
def test_erased_identity_cannot_rebind_nonempty_snapshot(kind):
    from famjet.memory.exact_store import PackedHistoryMemory
    from famjet.memory.jet import JetMemory
    from famjet.eval.isolation import isolated_read,isolated_features
    from test_exact_store import batches
    e,q=batches(); e=replace(e,key_features=e.key_features.double()); q=replace(q,key_features=q.key_features.double())
    method=PackedHistoryMemory(4,2,'recent',key_dim=1) if kind=='packed' else JetMemory(torch.ones(1,2,dtype=torch.float64),1,2)
    state=method.encode(e)
    state=replace(state,payload={**state.payload,'time_unit_hash':torch.zeros(32,dtype=torch.uint8)})
    next_events=replace(e,history_ids=('other',),timestamps=e.timestamps+3,event_ids=e.event_ids+4)
    with pytest.raises(ValueError,match='identity'):
        method.encode(next_events,state)
    with pytest.raises(ValueError,match='identity'):
        (isolated_read if kind=='packed' else isolated_features)(method,state,replace(q,history_ids=('other',)))


def test_failed_kernel_state_preserves_diagnostics_and_nan_reporting(tmp_path):
    from famjet.eval.isolation import isolated_features,result_json
    from famjet.eval.state_io import save_state,load_state
    from famjet.memory.jet import JetMemory
    from test_exact_store import batches
    e,q=batches(); e=replace(e,key_features=e.key_features.double()); q=replace(q,key_features=q.key_features.double())
    m=JetMemory(torch.ones(1,2,dtype=torch.float64),1,2); s=m.encode(e)
    s=replace(s,payload={**s.payload,'z':torch.full_like(s.payload['z'],float('inf'))})
    path=tmp_path/'failed.json'; save_state(path,s)
    result=isolated_features(m,load_state(path,s.parameter_hash),q)
    assert result.diagnostics['failure'].all()
    assert not result.supported.any()
    assert torch.isnan(result.diagnostics['b']).all()
    assert result_json(result)['diagnostics']['b'][0][0]==[[None,None]]
    json.dumps(result_json(result),allow_nan=False)


def test_isolated_read_batches_independent_histories():
    from famjet.eval.isolation import isolated_read
    from famjet.memory.exact_store import PackedHistoryMemory
    from test_exact_store import batches
    from dataclasses import fields
    e,q=batches(tasks=('latest',))
    def two_rows(record):
        return {f.name:torch.cat((getattr(record,f.name),getattr(record,f.name)),dim=0)
                for f in fields(record) if isinstance(getattr(record,f.name),torch.Tensor)}
    e=replace(e,**two_rows(e),history_ids=('left','right'))
    e.values[1].add_(100)
    q=replace(q,**two_rows(q),history_ids=('left','right'),tasks=(('latest',),('latest',)))
    m=PackedHistoryMemory(4,2,'recent',key_dim=1)
    result=isolated_read(m,m.encode(e),q)
    assert result.prediction.tolist()==[[[14.,7.]],[[114.,107.]]]


def test_native_learned_bank_preserves_represented_rates_in_cpu_worker():
    from famjet.eval.isolation import isolated_features,export_method,_reconstruct,model_identity
    from famjet.eval.state_io import inference_snapshot
    from famjet.memory.expbank import ExpBankMemory,BoundedRates
    from test_exact_store import batches
    if not torch.backends.mps.is_available(): pytest.skip('native MPS unavailable')
    method=ExpBankMemory(BoundedRates(8,-8.,4.).to('mps'),1,2)
    events,queries=batches()
    events=replace(events,values=events.values.to('mps',dtype=torch.float32),
                   key_features=events.key_features.to('mps'),present=events.present.to('mps'),
                   observed=events.observed.to('mps'))
    state=method.encode(events)
    # This path fails today despite successful native encode: reconstructing
    # sigmoid/exp on CPU changes rate bits and therefore the writer hash.
    actual=isolated_features(method,state,queries)
    spec=export_method(method)
    frozen=_reconstruct(spec,freeze_rates=True)
    assert torch.equal(frozen.rates,method.rates.detach().cpu())
    assert frozen._parameter_hash()==state.parameter_hash
    expected=frozen.features(inference_snapshot(state),queries)
    torch.testing.assert_close(actual.values,expected.values,rtol=0,atol=0)
    assert spec['schema']['rate_source']==dict(count=8,log_min=-8.,log_max=4.)
    assert set(spec['weights'])=={'logits','represented_rates'}
    original_identity=model_identity(method)
    with torch.no_grad(): method.rate_source.logits.add_(.25)
    assert model_identity(method)!=original_identity
    with pytest.raises(ValueError,match='parameter hash'):
        isolated_features(method,state,queries)


def test_target_version_change_does_not_open_protected_namespaces():
    from famjet.data.synthetic import generate_episode
    c=config()
    for version in ('initial_spec_v1','initial_spec_v2_targets'):
        for namespace in ('pilot','confirmation','replication'):
            candidate=replace(c,data=replace(c.data,generator_version=version,generator=replace(c.data.generator,namespace=namespace)))
            with pytest.raises(ValueError,match='protected'):
                generate_episode(candidate,37,'forbidden')
