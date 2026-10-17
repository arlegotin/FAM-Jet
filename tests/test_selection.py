"""Development selection cannot consume protected outcomes or hide weak controls."""
import importlib.util
from copy import deepcopy
import pytest


def api():
    assert importlib.util.find_spec('famjet.analysis.development') is not None, 'development selection is absent'
    from famjet.analysis import development
    return development


def trial(name='a', loss=1., cost=10.):
    return dict(config_hash=name, family='bank', split='development_fit', loss=loss,
                total_cost_seconds=cost, status='completed', convergence='accepted',
                positive_control='passed', numerical_gate='passed', padding_parameters=0,
                allocated_parameters=20, objective_active_parameters=18,
                reader_input_width=12, claim_scope='fixed_writer_primary')


def policy():
    return dict(claim_scope='fixed_writer_primary', max_total_cost_seconds=100.,
                max_active_parameters=100, tie_tolerance=0.)


def test_protected_scores_cannot_enter_selection():
    d=api(); protected=trial('protected',-100.)
    protected['split']='confirmation'
    with pytest.raises(ValueError,match='protected|development'):
        d.select_family([trial(),protected],policy())
    forbidden=trial(); forbidden['test_loss']=-100
    with pytest.raises(ValueError,match='protected|unknown'):
        d.select_family([forbidden],policy())


@pytest.mark.parametrize('field,value',[('convergence','underfit'),('positive_control','failed'),('numerical_gate','unvalidated'),('status','failed')])
def test_undertrained_or_control_failed_baseline_is_not_accepted(field,value):
    d=api(); r=trial(); r[field]=value
    with pytest.raises(ValueError): d.validate_baseline_acceptance(r,'fixed_writer_primary')
    assert d.select_family([r,trial('credible',2.)],policy())['selected']['config_hash']=='credible'


def test_ties_use_cost_then_hash():
    d=api()
    assert d.select_family([trial('b',1.,5.),trial('a',1.,5.),trial('cheap',1.,9.)],policy())['selected']['config_hash']=='a'


def test_actual_reader_width_and_no_padding():
    d=api(); a=trial(); b=trial('b'); b['reader_input_width']=13
    assert not d.reader_match(a,b)
    b=deepcopy(a); b['padding_parameters']=1
    with pytest.raises(ValueError,match='padding'): d.validate_baseline_acceptance(b,'fixed_writer_primary')


def test_query_multiplicity_does_not_change_validation_weighting():
    d=api()
    rows=[dict(history_id='h1',task='mean',regime='a',loss=1.),dict(history_id='h1',task='contrast',regime='a',loss=9.),dict(history_id='h2',task='mean',regime='a',loss=3.),dict(history_id='h2',task='contrast',regime='a',loss=7.)]
    assert d.validation_loss(rows,{'a':1.},{'mean':.5,'contrast':.5})==5.
    rows.extend([dict(rows[0])]*10)
    assert d.validation_loss(rows,{'a':1.},{'mean':.5,'contrast':.5})==5.


def test_development_policy_rejects_protected_execution_and_unmeasured_learning(tmp_path):
    from dataclasses import replace
    from pathlib import Path
    from famjet.config import load_config
    d=api(); c=load_config(Path('configs/smoke.yaml'))
    assert hasattr(d,'resolve_policy'), 'strict development execution policy absent'
    with pytest.raises(ValueError): d.resolve_policy(replace(c,phase='pilot'))
    with pytest.raises(ValueError): d.resolve_policy(replace(c,phase='development'))


def test_clean_generic_reader_has_real_equal_cost_and_support_is_inactive():
    from dataclasses import replace
    from pathlib import Path
    from famjet.config import load_config
    from famjet.train import make_model
    d=api(); c=load_config(Path('configs/smoke.yaml'))
    c=replace(c,resources=replace(c.resources,device='cpu'),model=replace(c.model,reader=replace(c.model.reader,kind='generic_contracted',width=64)))
    jet=make_model(c); bank=make_model(replace(c,model=replace(c.model,method='bank',J=8)))
    assert hasattr(d,'parameter_accounting'), 'objective-active accounting absent'
    j,b=d.parameter_accounting(jet),d.parameter_accounting(bank)
    assert j==b
    assert j['allocated_parameters']-j['objective_active_parameters']==385
    assert j['padding_parameters']==0


def dev_config():
    from dataclasses import replace
    from pathlib import Path
    from famjet.config import load_config,DevelopmentConfig
    c=load_config(Path('configs/smoke.yaml'))
    return replace(c,phase='development',model=replace(c.model,reader=replace(c.model.reader,kind='generic_contracted',width=64)),resources=replace(c.resources,device='cpu',cpu_threads=1),development=DevelopmentConfig('calibration',(128,),12345,1,1,(0,1,2)))


def test_cell_draws_are_independent_but_paired_across_methods():
    from dataclasses import replace
    d=api(); c=dev_config(); bank=replace(c,model=replace(c.model,method='bank',J=8))
    ids=[]
    for n in (128,512,2048):
        cc=replace(c,data=replace(c.data,length=n),development=replace(c.development,lengths=(128,512,2048)))
        for regime in d.REGIMES:
            _,identity=d.draw_config(cc,0,length=n,regime=regime)
            ids.append(identity)
    assert len(set(ids))==12
    assert d.draw_config(c,0)[1]==d.draw_config(bank,0)[1]


def test_development_resume_preserves_trajectory_and_raw_optimizer_checks(tmp_path):
    import torch
    from famjet.train import train_model
    from famjet.checkpoint import load_checkpoint,_validate
    from famjet.provenance import canonical_hash
    c=dev_config()
    whole=load_checkpoint(train_model(c,tmp_path/'whole'),{})
    first=train_model(c,tmp_path/'first',stop_at=1)
    resumed=load_checkpoint(train_model(c,tmp_path/'resumed',resume=first),{})
    assert whole['consumed_episode_ids']==resumed['consumed_episode_ids']
    for k in whole['model_state']: assert torch.equal(whole['model_state'][k],resumed['model_state'][k])
    bad=deepcopy(resumed); bad['optimizer']['param_groups'][0]['lr']*=2
    with pytest.raises(ValueError,match='optimizer'): _validate(bad)
    bad=deepcopy(resumed); bad['model']['schema']['reader']['budget']['width']=2**30
    bad['model_hash']=canonical_hash(bad['model'])
    with pytest.raises(ValueError,match='reader|configuration'): _validate(bad)


def test_simple_controls_use_actual_packed_budget():
    d=api(); methods=d.simple_memories(dev_config(),4705)
    assert {'recent','latest_lru','reservoir','hybrid','buckets','exact_unbounded_fp64'}==set(methods)
    for name,m in methods.items():
        if name=='exact_unbounded_fp64': continue
        state=m.init_state(1,device='cpu',dtype='float32')
        assert m.persistent_nbytes(state)<=4705


def test_development_command_produces_real_paired_scoring_curve(tmp_path):
    d=api(); record=d.run_development(dev_config(),tmp_path/'development')
    assert record['status']=='completed'
    assert record['last_evaluation']['step']==2
    assert record['last_evaluation']['loss']>=0
    assert record['last_evaluation']['parameters']['objective_active_parameters']>0
    assert (tmp_path/'development/manifest.json').is_file()


def test_data_identity_closes_over_pooled_population():
    from dataclasses import replace
    from famjet.train import identities
    from famjet.provenance import canonical_hash
    d=api(); c=dev_config()
    pooled=replace(c,development=replace(c.development,lengths=(128,512,2048)))
    one,_=identities(c,d.resolve_policy(c)); many,data=identities(pooled,d.resolve_policy(pooled))
    assert one['data_hash']!=many['data_hash']
    assert data['length_weights']=={'128':1/3,'512':1/3,'2048':1/3}
    assert len(data['regime_weights'])==4
    assert data['cell_identity_namespace']=='task18-{fit|train}-N{length}-{regime}-{ordinal:012d}'


def test_calibration_shape_survives_json_without_losing_exact_binding(tmp_path):
    import json
    from dataclasses import replace
    from famjet.eval.isolation import source_identity
    from famjet.provenance import canonical_hash
    d=api(); c=dev_config(); path=tmp_path/'calibration.json'
    evidence={'status':'passed','source_hash':source_identity(),'shapes':[d.execution_shape(c)],'net_allocation_limit_bytes':201326592}
    path.write_text(json.dumps(evidence))
    # Real evidence uses JSON arrays; typed RunConfig uses tuples.
    evidence=json.loads(path.read_text())
    learning=replace(c,development=replace(c.development,mode='learning',calibration_path=str(path),calibration_hash=canonical_hash(evidence)))
    assert d.resolve_policy(learning)['scientific_status']=='exploratory_development'
    altered=replace(learning,model=replace(learning.model,rates=replace(learning.model.rates,bounds=(.002,1.))))
    with pytest.raises(ValueError,match='applicable'): d.resolve_policy(altered)


def test_pooled_timing_counts_actual_consumed_events(tmp_path):
    import json
    from dataclasses import replace
    from famjet.train import train_model
    c=dev_config();c=replace(c,training=replace(c.training,effective_batch=3),development=replace(c.development,lengths=(128,512,2048)))
    train_model(c,tmp_path/'pooled',stop_at=1)
    row=json.loads((tmp_path/'pooled/timing.jsonl').read_text().splitlines()[0])
    assert row['events']==2688
    assert row['queries']==24
    assert row['shape']['lengths']==[128,512,2048]


def test_primary_activity_excludes_only_guaranteed_task_and_exact_fixed_rate_zeros():
    import torch
    from dataclasses import replace
    from famjet.train import make_model
    c=dev_config();raw=api().parameter_accounting(make_model(c))
    assert raw['objective_active_parameters']==10632
    assert raw['objective_activity_status']=='upper_bound'
    full=make_model(replace(c,model=replace(c.model,reader=replace(c.model.reader,kind='generic_full',rank=5))))
    count=api().parameter_accounting(full)
    assert count['allocated_parameters']==11014 and count['objective_active_parameters']==10924
    structured=make_model(replace(c,model=replace(c.model,reader=replace(c.model.reader,kind='structured'))))
    columns=[18,38,58,78]
    structured.reader.feature_mean[columns]=torch.log(structured.kernel.rates.flatten())
    exact=api().parameter_accounting(structured)
    assert exact['objective_active_parameters']==10888
    structured.reader.feature_mean[18]+=1e-6  # Tiny nonzero constant is active.
    assert api().parameter_accounting(structured)['objective_active_parameters']==10952
