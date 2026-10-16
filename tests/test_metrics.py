"""Failure-complete losses: prior substitution must never remove a query."""
from copy import deepcopy
from dataclasses import replace
import json
import math
import numpy as np
import pytest
import torch
from famjet.types import PredictionBatch


def case(task='mean', prediction=(4.,), target=(2.,)):
    from famjet.provenance import canonical_hash
    stats={'schema_version':2,'split':'training','target_semantics':'observed_event_targets_v2',
           'tasks':{task:{'status':'ok','mean':[6.],'scale':2.,'pooled_variance':4.,
                          'constant_coordinates':[False],'class_distribution':[.75,.25]}}}
    context={'version':2,'output_convention':'categorical_logits' if task=='random_binding' else 'binary_probability' if task=='presence' else 'numeric','present':[[True]],'tasks':[[task]],'target_valid':[[True]],
             'numeric_supported':[[True]],'prediction_valid':[[True]],'quarantined':[[False]],
             'quarantine_trigger':None,'method':'candidate','replicate':0,'regime':'r',
             'target_semantics':'observed_event_targets_v2','manifest_hash':'a'*64,
             'statistics_hash':canonical_hash(stats)}
    batch=PredictionBatch(('h',),torch.tensor([[0]]),torch.tensor([[prediction]],dtype=torch.float64),
          torch.tensor([[target]],dtype=torch.float64),torch.ones(1,1,dtype=torch.bool),
          torch.zeros(1,1,dtype=torch.bool),torch.zeros(1,1,dtype=torch.bool),{'scoring_v2':context})
    policy={'version':2,'primary_tasks':[task], 'support_calibration':None,
            'expected_inventory':[{'history_id':'h','replicate':0,'regime':'r','tasks':{task:[0]}}],
            'task_weights':{task:1.},'regime_weights':{'r':1.}}
    return batch,stats,policy


def test_numeric_scale_fallback_and_abstention_do_not_drop_denominator():
    from famjet.eval.metrics import score_predictions
    b,s,p=case()
    r=score_predictions(b,s,p)[0]
    assert r['normalized_error']==1 and r['native_mae']==2
    b.prediction[:]=float('nan'); b.abstained[:]=True
    r=score_predictions(b,s,p)[0]
    assert r['normalized_error']==4 and r['fallback'] and r['eligible']
    assert r['prediction']==[6.] and r['raw_prediction']==[None]
    assert r['abstained'] and not r['accepted']
    assert r['support_calibration_status']=='unavailable'
    json.dumps(r,allow_nan=False)


def test_binary_absence_validity_uses_effective_prediction_not_feature_support():
    from famjet.eval.metrics import score_predictions
    b,s,p=case('presence',(.2,),(0.,))
    b.supported[:]=False; b.metadata['scoring_v2']['numeric_supported']=[[False]]
    r=score_predictions(b,s,p)[0]
    assert not r['fallback'] and r['eligible']
    assert r['loss']==pytest.approx(-math.log(.8))
    b.failure[:]=True
    r=score_predictions(b,s,p)[0]
    assert r['prediction']==[.75,.25] and r['loss']==pytest.approx(-math.log(.75))


def test_categorical_full_prior_ties_and_explicit_infinite_loss():
    from famjet.eval.metrics import score_predictions, aggregate_scores
    b,s,p=case('random_binding',tuple([float('nan')]*32),(3.,))
    s['tasks']['random_binding']['class_distribution']=[.5,.5]+[0.]*30
    from famjet.provenance import canonical_hash
    b.metadata['scoring_v2']['statistics_hash']=canonical_hash(s)
    r=score_predictions(b,s,p)[0]
    assert r['predicted_class']==0 and r['prediction']==s['tasks']['random_binding']['class_distribution']
    assert r['loss'] is None and r['infinite_loss'] and r['eligible']
    a=aggregate_scores([r]); assert a['status']=='infinite_loss' and a['infinite_loss_count']==1
    json.dumps(a,allow_nan=False)


def test_change_sign_fallback_keeps_numeric_mean_and_constant_task_blocks():
    from famjet.eval.metrics import score_predictions,aggregate_scores
    from famjet.provenance import canonical_hash
    b,s,p=case('change_sign',(float('nan'),),(-1.,))
    s['tasks']['change_sign']['mean']=[-.25]
    b.metadata['scoring_v2']['statistics_hash']=canonical_hash(s)
    r=score_predictions(b,s,p)[0]
    assert r['prediction']==[-.25] and r['sign_accuracy']==1 and r['native_mae']==.75
    s['tasks']['change_sign'].update(scale=None,pooled_variance=0.,constant_coordinates=[True])
    b.metadata['scoring_v2']['statistics_hash']=canonical_hash(s)
    with pytest.raises(ValueError,match='scale'): score_predictions(b,s,p)
    p['primary_tasks']=[]
    r=score_predictions(b,s,p)[0]
    assert r['constant_absolute_error']==[.75] and aggregate_scores([r])['status']=='undefined_loss'


def test_legacy_and_missing_primary_labels_are_contract_errors():
    from famjet.eval.metrics import score_predictions
    b,s,p=case()
    with pytest.raises(ValueError,match='scoring_v2'): score_predictions(replace(b,metadata={}),s,p)
    b.metadata['scoring_v2']['target_valid']=[[False]]
    with pytest.raises(ValueError,match='primary target'): score_predictions(b,s,p)


def test_equal_task_history_regime_weight_and_complete_pair_inventory():
    from famjet.eval.metrics import score_predictions,history_effects,aggregate_scores,history_effects_inventory
    b,s,p=case(); s['tasks']['contrast']=deepcopy(s['tasks']['mean'])
    from famjet.provenance import canonical_hash
    p.update(primary_tasks=['mean','contrast'],task_weights={'mean':.5,'contrast':.5},regime_weights={'r':.5,'s':.5},
             expected_inventory=[{'history_id':h,'replicate':0,'regime':reg,'tasks':{'mean':[0,1],'contrast':[2]}} for h,reg in [('a','r'),('b','r'),('c','s')]])
    rows=[]
    for h,reg in [('a','r'),('b','r'),('c','s')]:
        for method in ['baseline','candidate']:
            for q,t in [(0,'mean'),(1,'mean'),(2,'contrast')]:
                bb,_,_=case(t,(2. if method=='candidate' else (4. if t=='mean' else 8.),),(2.,))
                bb=replace(bb,history_ids=(h,),query_ids=torch.tensor([[q]]))
                bb.metadata['scoring_v2'].update(method=method,regime=reg,statistics_hash=canonical_hash(s))
                rows.extend(score_predictions(bb,s,p))
    np.testing.assert_equal(history_effects(rows,('baseline','candidate')),[[5.],[5.],[5.]])
    np.testing.assert_equal(history_effects(rows,('candidate','baseline')),[[-5.],[-5.],[-5.]])
    inv=history_effects_inventory(rows,('baseline','candidate'))
    assert inv['history_weights']==[.25,.25,.5]
    a=aggregate_scores([r for r in rows if r['method']=='baseline'])
    assert a['loss']==5 and a['native_by_task']['mean']['rmse']==2 and a['native_by_task']['contrast']['rmse']==6
    with pytest.raises(ValueError,match='inventory'): history_effects(rows[:-1],('baseline','candidate'))
    with pytest.raises(ValueError,match='inventory'): history_effects(rows+[rows[0]],('baseline','candidate'))


def test_extreme_finite_logits_have_finite_cross_entropy():
    from famjet.eval.metrics import score_predictions
    b,s,p=case('presence',(-1000.,),(1.,))
    b.metadata['scoring_v2']['output_convention']='binary_logit'
    assert score_predictions(b,s,p)[0]['loss']==1000.
    b,s,p=case('random_binding',tuple([0.,-1000.]+[0.]*30),(1.,))
    from famjet.provenance import canonical_hash
    s['tasks']['random_binding']['class_distribution']=[1/32]*32
    b.metadata['scoring_v2']['statistics_hash']=canonical_hash(s)
    assert score_predictions(b,s,p)[0]['loss']==pytest.approx(1000+np.log(31))


def test_nonfinite_native_error_and_missing_cells_cannot_disappear():
    from famjet.eval.metrics import score_predictions,aggregate_scores,history_effects
    b,s,p=case(prediction=(1e308,),target=(-1e308,))
    r=score_predictions(b,s,p)[0]
    assert r['native_mse_infinite'] and r['infinite_loss']
    assert aggregate_scores([r])['status']=='infinite_loss'
    with pytest.raises(ValueError,match='inventory'): aggregate_scores([])


def test_finite_abstention_is_diagnostic_only_and_bad_probabilities_fallback():
    from famjet.eval.metrics import score_predictions
    b,s,p=case(); b.abstained[:]=True
    r=score_predictions(b,s,p)[0]
    assert r['loss']==1 and not r['fallback'] and not r['accepted']
    b,s,p=case('presence',(1.5,),(1.,))
    r=score_predictions(b,s,p)[0]
    assert r['fallback'] and r['loss']==pytest.approx(-np.log(.25))


def test_categorical_calibration_uses_scored_probability_not_support_head():
    from famjet.eval.metrics import score_predictions,aggregate_scores
    b,s,p=case('presence',(.2,),(0.,))
    report=aggregate_scores(score_predictions(b,s,p))
    assert report['categorical_by_task']['presence']['brier']==pytest.approx(.08)
    assert report['categorical_by_task']['presence']['ece']==pytest.approx(.2)
    assert report['categorical_by_task']['presence']['accuracy']==1.


def test_scoring_contract_rejects_ambiguous_masks_and_output_convention():
    from famjet.eval.metrics import score_predictions
    b,s,p=case(); b.metadata['scoring_v2']['present']=[['false']]
    with pytest.raises(ValueError,match='boolean'): score_predictions(b,s,p)
    b,s,p=case(); b.metadata['scoring_v2']['output_convention']='guess'
    with pytest.raises(ValueError,match='convention'): score_predictions(b,s,p)


def test_identical_method_effects_and_reversed_labels_are_exact_zero():
    from famjet.eval.metrics import score_predictions,history_effects
    b,s,p=case(); row=score_predictions(b,s,p)[0]
    rows=[{**row,'method':'a'},{**row,'method':'b'}]
    np.testing.assert_array_equal(history_effects(rows,('a','b')),[[0.]])
    np.testing.assert_array_equal(history_effects(rows,('b','a')),[[0.]])


def test_missing_numeric_prior_is_config_failure_even_for_usable_output():
    from famjet.eval.metrics import score_predictions
    from famjet.provenance import canonical_hash
    b,s,p=case(); s['tasks']['mean']['mean']=None
    b.metadata['scoring_v2']['statistics_hash']=canonical_hash(s)
    with pytest.raises(ValueError,match='prior'): score_predictions(b,s,p)


def overflow_case(prediction, target, scale):
    """Use explicit representable training scales and matching dimensions."""
    from famjet.provenance import canonical_hash
    b,s,p=case(prediction=prediction,target=target)
    s['tasks']['mean'].update(mean=[0.]*len(target),scale=scale,pooled_variance=scale*scale,
                            constant_coordinates=[False]*len(target))
    b.metadata['scoring_v2']['statistics_hash']=canonical_hash(s)
    return b,s,p


def test_normalized_error_stays_finite_when_native_square_overflows():
    from fractions import Fraction
    from famjet.eval.metrics import score_predictions,aggregate_scores
    b,s,p=overflow_case((1e155,),(0.,),1e150)
    with np.errstate(all='raise'):
        r=score_predictions(b,s,p)[0]
        result=aggregate_scores([r])
    truth=float((Fraction(1e155)/Fraction(1e150))**2)
    assert r['loss']==pytest.approx(truth,rel=3e-16) and r['loss_status']=='ok'
    assert r['native_mse'] is None and r['native_mse_infinite']
    assert not r['infinite_loss'] and not r['fallback']
    assert result['status']=='ok' and result['infinite_loss_count']==0
    assert result['native_by_task']['mean']['mse_status']=='unavailable_nonrepresentable_row_metric'
    json.dumps(result,allow_nan=False)


@pytest.mark.parametrize('prediction,target,scale',[
    ((1.5e154,0.),(0.,0.),1.),  # individual square overflows, coordinate mean does not
    ((1e154,1e154),(0.,0.),1.),  # finite squares, their sum overflows
    ((1e308,1e308),(0.,0.),1e154),  # native MAE sum overflows; normalized MSE is finite
    ((1e308,0.),(-1e308,0.),1e154),  # individual absolute error overflows, MAE is finite
])
def test_coordinate_means_follow_rational_truth_even_with_overflowing_intermediates(prediction,target,scale):
    from fractions import Fraction
    from famjet.eval.metrics import score_predictions
    b,s,p=overflow_case(prediction,target,scale)
    errors=[Fraction(x)-Fraction(y) for x,y in zip(prediction,target)]
    truths={'native_mse':sum(x*x for x in errors)/len(errors),
            'native_mae':sum(abs(x) for x in errors)/len(errors),
            'loss':sum((x/Fraction(scale))**2 for x in errors)/len(errors)}
    with np.errstate(all='raise'): r=score_predictions(b,s,p)[0]
    for field,truth in truths.items():
        try: expected=float(truth)
        except OverflowError: expected=float('inf')
        flag='infinite_loss' if field=='loss' else field+'_infinite'
        if math.isfinite(expected):
            assert r[field]==pytest.approx(expected,rel=3e-16) and not r[flag]
        else:
            assert r[field] is None and r[flag]
    json.dumps(r,allow_nan=False)


@pytest.mark.parametrize('query_count,replicate_count',[(2,1),(1,2),(2,2)])
def test_finite_query_replicate_and_native_means_cannot_overflow(query_count,replicate_count):
    from fractions import Fraction
    from famjet.eval.metrics import score_predictions,aggregate_scores,history_effects
    b,s,p=overflow_case((1e154,),(0.,),1.)
    p.update(task_weights={'mean':.5,'contrast':.5},regime_weights={'r':.5,'s':.5},
             primary_tasks=['mean','contrast'],expected_inventory=[
                 {'history_id':h,'replicate':rep,'regime':reg,'tasks':{'mean':list(range(query_count)),'contrast':list(range(query_count))}}
                 for h,reg in [('a','r'),('b','r'),('c','s')] for rep in range(replicate_count)])
    s['tasks']['contrast']=deepcopy(s['tasks']['mean'])
    from famjet.provenance import canonical_hash
    rows=[]
    with np.errstate(all='raise'):
        for cell in p['expected_inventory']:
            for task in cell['tasks']:
                for q in range(query_count):
                    for method,value in [('baseline',1e154),('candidate',0.)]:
                        bb=deepcopy(b)
                        bb=replace(bb,history_ids=(cell['history_id'],),query_ids=torch.tensor([[q]]),prediction=torch.tensor([[[value]]],dtype=torch.float64))
                        bb.metadata['scoring_v2'].update(method=method,replicate=cell['replicate'],regime=cell['regime'],tasks=[[task]],statistics_hash=canonical_hash(s))
                        rows.extend(score_predictions(bb,s,p))
        aggregate=aggregate_scores([r for r in rows if r['method']=='baseline'])
        effect=history_effects(rows,('baseline','candidate'))
    truth=float(Fraction(1e154)**2)
    assert aggregate['status']=='ok' and aggregate['loss']==truth and aggregate['infinite_loss_count']==0
    assert aggregate['selective_risk']==truth
    for native in aggregate['native_by_task'].values():
        assert native['rmse']==1e154 and native['mae']==1e154
    np.testing.assert_array_equal(effect,np.full((3,replicate_count),truth))


def test_genuinely_unrepresentable_normalized_loss_remains_infinite():
    from famjet.eval.metrics import score_predictions,aggregate_scores
    b,s,p=overflow_case((1e155,),(0.,),1.)
    with np.errstate(all='raise'):
        r=score_predictions(b,s,p)[0]; aggregate=aggregate_scores([r])
    assert r['loss'] is None and r['infinite_loss'] and r['loss_status']=='infinite_loss'
    assert aggregate['status']=='infinite_loss' and aggregate['infinite_loss_count']==1
    assert aggregate['native_by_task']['mean']['mse_status']=='unavailable_nonrepresentable_row_metric'
    json.dumps(aggregate,allow_nan=False)
