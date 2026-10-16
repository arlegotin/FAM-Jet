"""Generator behavior: deterministic identities, exact populations and failures."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import torch

from famjet.config import load_config


def config(**settings):
    from famjet.config import GeneratorConfig
    c = load_config(Path('configs/smoke.yaml'))
    return replace(c, data=replace(c.data, generator=GeneratorConfig(**settings)))


def test_generator_reproducible_across_processes():
    from famjet.data.synthetic import generate_episode
    script = "from pathlib import Path; from famjet.config import load_config; from famjet.data.synthetic import generate_episode; import json; print(json.dumps(generate_episode(load_config(Path('configs/smoke.yaml')),42,'a').metadata['hashes'],sort_keys=True))"
    outputs = [subprocess.check_output([sys.executable, '-c', script], env={**os.environ, 'PYTHONHASHSEED': seed}, text=True) for seed in ['1', '900']]
    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0]) == generate_episode(config(),42,'a').metadata['hashes']


def test_dense_key_golden_features():
    from famjet.data.synthetic import key_features
    # Versioned, hand-pinned output is stored as exact float32 bit patterns.
    got = key_features(2**64-1,17,4)
    assert got.dtype == np.float32
    assert got.view(np.uint32).tolist() == [1044830160, 1014767053, 1042407669, 1059184984]
    assert np.isclose(got.sum(),1)
    with pytest.raises(ValueError):
        key_features(2**64,17,4)


def test_primary_query_time_is_last_event():
    from famjet.data.synthetic import generate_episode
    e = generate_episode(config(),52,'primary')
    assert e.metadata['status'] == 'ok'
    assert (e.queries.T == e.events.timestamps[0,-1]).all()
    assert e.queries.tasks[0] == ('mean','contrast')*4
    assert e.supported.all()
    assert e.events.values.shape == (1,128,8)
    assert e.events.auxiliary == {}
    gaps = np.diff(e.events.timestamps[0].numpy())
    assert set(gaps) <= {0,1,2,4,16}


def test_no_future_reversal_flag():
    from famjet.data.synthetic import generate_episode
    e = generate_episode(config(regime='irregular_revisions'),33,'revisions')
    assert e.events.auxiliary == {}
    assert e.events.key_features.shape[-1] == 16
    assert 'schedule' not in e.metadata and 'reversal' not in e.metadata


def test_span_and_sampling_exhaustion_explicit():
    from famjet.data.synthetic import generate_episode
    c = config()
    tiny = generate_episode(replace(c,data=replace(c.data,length=1)),1,'tiny')
    assert tiny.metadata['status'] == 'insufficient_span'
    assert tiny.queries.lengths.item() == 0
    exhausted = generate_episode(config(max_query_attempts=1),1,'sparse')
    assert exhausted.metadata['status'] == 'sampling_exhausted'
    assert exhausted.metadata['diagnostics']['failed_queries'] > 0
    assert exhausted.metadata['diagnostics']['attempts'] <= 8
    assert exhausted.queries.lengths.item() == 8
    assert (~torch.tensor(exhausted.metadata['target_valid'])).any()


@pytest.mark.parametrize('regime',['piecewise_stationary','trend_reset','periodic_impulses','irregular_revisions'])
def test_each_regime_reproducible_and_coordinates_independent(regime):
    from famjet.data.synthetic import generate_episode
    e = generate_episode(config(regime=regime),11,'regime')
    assert e.metadata['regime'] == regime
    assert not torch.equal(e.events.values[:,:,0],e.events.values[:,:,1])
    assert e.events.observed.all()


@pytest.mark.parametrize('population,task,V',[('latest','latest',8),('presence','presence',8),('interval_support','interval_support',8),('change_sign','change_sign',8),('corrected_categorical','corrected_categorical',32),('random_binding','random_binding',32),('boundary','mean',8),('constant','mean',8),('impulse','mean',8),('random','mean',8),('full_history','mean',8)])
def test_all_populations_use_oracle(population,task,V):
    from famjet.data.synthetic import generate_episode
    from famjet.eval.oracle import exact_targets
    c=config(population=population)
    if V==32:
        c=replace(c,data=replace(c.data,value_dim=32))
    e=generate_episode(c,4,population)
    assert task in e.queries.tasks[0]
    assert e.events.values.shape[-1]==V
    oracle=exact_targets(e.events,e.queries)
    torch.testing.assert_close(e.labels,oracle.target,equal_nan=True)
    assert e.metadata['target_valid']==oracle.metadata['target_valid']
    if V==32:
        assert (e.events.values.sum(-1)==1).all()
        assert e.labels.shape==(1,8)


def test_absent_key_has_valid_query_features():
    from famjet.data.synthetic import generate_episode
    e=generate_episode(config(population='presence'),9,'absence')
    written=set(e.events.key_ids[0].tolist())
    assert len(written)==12
    assert sorted(e.labels[0,:,0].tolist())==[0.]*4+[1.]*4
    assert e.supported.sum().item()==4
    assert all(e.metadata['target_valid'][0])
    assert (e.queries.key_features.sum(-1)==1).all()
    assert e.queries.query_ids[0].tolist()==list(range(8))
    e2=generate_episode(config(population='presence'),9,'different')
    assert set(e2.events.key_ids[0].tolist())!=written
    assert not any(x in e.metadata for x in ['active_keys','absent_keys','oov'])


@pytest.mark.parametrize('robustness',['zipf','lognormal_gaps','heavy_gaps','heavy_noise','fast_resets','broad_periods','unseen_reversals'])
def test_named_robustness_populations(robustness):
    from famjet.data.synthetic import generate_episode
    e=generate_episode(config(robustness=robustness),17,'robust')
    assert e.metadata['robustness']==robustness
    assert torch.isfinite(e.events.values).all()
    assert e.metadata['status'] in {'ok','sampling_exhausted'}


def test_dense_key_loads_and_absence_features():
    from famjet.data.synthetic import generate_episode,key_features
    for load in [8,16,64]:
        c=config(key_load=load,population='presence')
        c=replace(c,data=replace(c.data,key_features='dense',length=2048))
        e=generate_episode(c,2,str(load))
        for k,f in zip(e.queries.key_ids[0].tolist(),e.queries.key_features[0]):
            np.testing.assert_array_equal(f.numpy(),key_features(k,c.data.generator.feature_seed,16))
        assert sorted(e.labels[0,:,0].tolist())==[0.]*4+[1.]*4


def test_semantic_fixture_populations():
    from famjet.data.synthetic import generate_episode
    for population in ['empty','same_time']:
        e=generate_episode(config(population=population),2,population)
        assert e.metadata['status']=='ok'
        assert e.queries.tasks[0]==('presence',)*8
        assert e.labels[0,:,0].tolist()==([0.]*8 if population=='empty' else [1.]*8)
    e=generate_episode(config(population='constant'),2,'constant')
    assert e.labels[0,0].tolist()==[1.]*8
    assert e.labels[0,1].tolist()==[0.]*8


def test_generator_settings_validation_and_smoke_roundtrip(tmp_path):
    from famjet.config import GeneratorConfig,save_resolved_config
    c=config()
    save_resolved_config(tmp_path/'c.json',c)
    assert load_config(tmp_path/'c.json')==c
    with pytest.raises(ValueError):
        replace(c,data=replace(c.data,generator=GeneratorConfig(max_query_attempts=0)))
    with pytest.raises(ValueError):
        replace(c,data=replace(c.data,generator=GeneratorConfig(delay_multiplier=3)))


def test_generator_training_statistics_keep_absent_labels():
    from famjet.data.synthetic import generate_episode
    from famjet.eval.metrics import fit_target_statistics
    e=generate_episode(config(population='presence'),9,'stats')
    s=fit_target_statistics([e])['tasks']['presence']
    assert s['count']==8
    assert s['class_distribution']==[.5,.5]
    e2=generate_episode(config(namespace='development_calibration'),9,'stats')
    with pytest.raises(ValueError,match='training'):
        fit_target_statistics([e2])


def test_uniform_gap_law_and_zero_gap_consumed():
    from famjet.data._processes import draw_gaps
    class ControlledRNG:
        def choice(self,values,n,p):
            assert tuple(values)==(0,1,2,4,16)
            assert tuple(p)==(.05,.55,.25,.10,.05)
            assert n==5
            return np.array([0,1,2,4,16])
    np.testing.assert_array_equal(draw_gaps(ControlledRNG(),5,'standard'),[0,1,2,4,16])


def test_latest_ties_presence_zero_sign_and_invalid_windows_hand_calculated():
    from famjet.data.synthetic import queries_for_history
    from famjet.eval.oracle import exact_targets
    from famjet.types import EventBatch,QueryBatch
    events=EventBatch(('fixture',),torch.arange(4)[None],torch.tensor([[0.,1.,2.,2.]],dtype=torch.float64),
                      torch.tensor([[2]*4],dtype=torch.uint64),torch.eye(16)[[2]*4][None],
                      torch.tensor([[[2.]*8,[6.]*8,[10.]*8,[14.]*8]],dtype=torch.float64),torch.tensor([4]),
                      torch.ones(1,4,dtype=torch.bool),torch.ones(1,4,8,dtype=torch.bool),'generator_reference_1')
    c=config(population='latest')
    q,_=queries_for_history(events,c,1,'fixture')
    assert exact_targets(events,q).target[0].tolist()==[[14.]*8]*8
    # Last equal-time event wins; recent mean12 minus older6 has positive sign.
    hand=replace(q,tasks=(('change_sign',)*8,),age_start=torch.zeros(1,8,dtype=torch.float64),age_end=torch.ones(1,8,dtype=torch.float64))
    assert exact_targets(events,hand).target[0].tolist()==[[1.]*8]*8
    events.values[:]=3
    assert exact_targets(events,hand).target[0].tolist()==[[0.]*8]*8
    invalid=replace(hand,age_start=torch.ones(1,8,dtype=torch.float64)*3,age_end=torch.ones(1,8,dtype=torch.float64)*4)
    r=exact_targets(events,invalid)
    assert not r.supported.any()
    assert torch.isnan(r.target).all()
    # Zero-width valid query contracts explicitly have no observed mean.
    r=exact_targets(events,replace(hand,age_end=torch.zeros_like(hand.age_end)))
    assert not r.supported.any()


def test_categorical_revisions_and_iid_binding_exact_seeded_labels():
    from famjet.data._processes import categorical_values
    # Pin the first 20 draws independently from the label oracle. A seeded
    # reference PCG64 trace fixes p1/8 revisions and iid per-event binding.
    index=np.zeros(20,dtype=np.int64)
    revision=categorical_values(index,1,19,True).argmax(-1).tolist()
    iid=categorical_values(index,1,19,False).argmax(-1).tolist()
    assert revision==[4,4,4,4,4,1,1,1,1,1,1,1,1,1,16,11,11,11,11,11]
    assert iid==[29,21,16,14,13,10,30,14,28,16,7,5,1,9,20,24,25,24,30,9]


def test_query_sampler_uses_oracle_exact_age_membership():
    from famjet.data.synthetic import _supported
    from famjet.types import EventBatch
    # Exact represented age 1-float(.1) is below float(.9). Rounded subtraction
    # equals .9 and would incorrectly reject this supported half-open interval.
    e=EventBatch(('h',),torch.tensor([[0]]),torch.tensor([[.1]],dtype=torch.float64),
                 torch.tensor([[2]],dtype=torch.uint64),torch.eye(16)[[2]][None],
                 torch.ones(1,1,8,dtype=torch.float64),torch.tensor([1]),torch.ones(1,1,dtype=torch.bool),
                 torch.ones(1,1,8,dtype=torch.bool),'generator_reference_1')
    assert _supported(e,2,1.,0.,.9,False)


def test_presence_short_history_is_explicit_failure():
    from famjet.data.synthetic import generate_episode
    c=config(population='presence')
    e=generate_episode(replace(c,data=replace(c.data,length=3)),3,'short')
    assert e.metadata['status']=='insufficient_active_keys'
    assert e.metadata['diagnostics']['active_key_shortfall']==9


def test_recorded_process_and_query_laws_exact():
    from famjet.data.synthetic import generate_episode
    e=generate_episode(config(),42,'law')
    p=e.metadata['population_parameters']
    assert p['gaps']==[0,1,2,4,16]
    assert p['gap_probabilities']==[.05,.55,.25,.10,.05]
    assert p['pilot_lengths']==[128,512,2048]
    assert p['regime_weights']==[.25]*4
    assert p['delays']==[0,.125,1,10]
    assert p['numeric_law']=={
        'initial_level_sd':1.,'piecewise_reset_probability':1/32,'noise_sd':.1,
        'trend_slope_sd':.01,'trend_reset_probability':1/128,
        'phase_min':0.,'phase_max':2*np.pi,'amplitude_min':.5,'amplitude_max':1.5,
        'period_min':16.,'period_max':256.,'impulse_probability':1/64,'impulse_sd':2.,
        'excursion_probability':1/64,'excursion_sd':2.,'reversal_min':1,'reversal_max':16}
    assert p['query_law']=={'width_floor':1.,'span_divisor':128.,'max_width_fraction':.5}
    assert p['categorical_law']=={'classes':32,'revision_probability':1/8}


def test_query_windows_sample_declared_ranges_without_values(monkeypatch):
    import famjet.data.synthetic as synthetic
    from famjet.types import EventBatch
    c=config(max_query_attempts=1)
    e=EventBatch(('window',),torch.arange(3)[None],torch.tensor([[0.,128.,256.]],dtype=torch.float64),
                 torch.tensor([[2,2,2]],dtype=torch.uint64),torch.eye(16)[[2]*3][None],
                 torch.ones(1,3,8,dtype=torch.float64),torch.tensor([3]),torch.ones(1,3,dtype=torch.bool),
                 torch.ones(1,3,8,dtype=torch.bool),'generator_reference_1')
    class RangeProbe:
        def __init__(self): self.calls=[]
        def permutation(self,x): return np.asarray(x)
        def choice(self,x): return 2
        def uniform(self,low,high):
            self.calls.append((low,high))
            return (low+high)/2
    probe=RangeProbe()
    monkeypatch.setattr(synthetic,'_rng',lambda *args:probe)
    q,d=synthetic.queries_for_history(e,c,1,'window')
    assert d['attempts']==8
    # Width log-uniform [2,128], width=sqrt(256)=16. Placement is independent
    # and uniform [0,240] for mean, [0,224] for adjacent contrast.
    assert probe.calls[:4]==pytest.approx([(np.log(2),np.log(128)),(0,240),
                                         (np.log(2),np.log(128)),(0,224)])
    assert q.age_start[0,:2].tolist()==pytest.approx([120.,112.])
    assert (q.age_end-q.age_start)[0].tolist()==pytest.approx([16.]*8)


def test_saved_dense_feature_golden_vectors():
    from famjet.data.synthetic import key_features,FEATURE_VERSION
    saved=json.loads(Path('configs/key_features_golden.json').read_text())
    assert saved['feature_version']==FEATURE_VERSION
    assert len(saved['vectors'])>=3
    for vector in saved['vectors']:
        got=key_features(vector['key_id'],vector['feature_seed'],vector['key_dim'])
        assert got.view(np.uint32).tolist()==vector['float32_bits']


def test_constant_impulse_random_and_full_history_numeric_fixtures():
    from famjet.data.synthetic import generate_episode
    constant=generate_episode(config(population='constant'),7,'values')
    assert (constant.events.values==1).all()
    impulse=generate_episode(config(population='impulse'),7,'values')
    assert torch.count_nonzero(impulse.events.values).item()==8
    assert impulse.events.values[0,64].tolist()==[1.]*8
    random=generate_episode(config(population='random'),7,'values')
    assert not torch.equal(random.events.values[:,:,0],random.events.values[:,:,1])
    full=generate_episode(config(population='full_history'),7,'values')
    for q,key in enumerate(full.queries.key_ids[0].tolist()):
        matching=[i for i,k in enumerate(full.events.key_ids[0].tolist()) if k==key]
        want=full.events.values[0,matching].mean(0)
        torch.testing.assert_close(full.labels[0,q],want,rtol=0,atol=0)


def test_secondary_latest_labels_from_last_raw_observation():
    from famjet.data.synthetic import generate_episode
    for population in ['latest','corrected_categorical','random_binding']:
        c=config(population=population)
        if population!='latest':
            c=replace(c,data=replace(c.data,value_dim=32))
        e=generate_episode(c,31,'last')
        for q,key in enumerate(e.queries.key_ids[0].tolist()):
            last=max(i for i,k in enumerate(e.events.key_ids[0].tolist()) if k==key)
            if population=='latest':
                assert e.labels[0,q].tolist()==e.events.values[0,last].tolist()
            else:
                assert e.labels[0,q].item()==e.events.values[0,last].argmax().item()
