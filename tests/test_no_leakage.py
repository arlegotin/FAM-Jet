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
