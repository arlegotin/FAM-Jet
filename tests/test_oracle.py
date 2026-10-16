import numpy as np
import pytest
import torch
from famjet.types import EventBatch, QueryBatch, Episode


def fixture(tasks=('mean',), starts=None, ends=None, values=None):
    values = values or [[2., 7.], [6., 7.], [10., 7.], [14., 7.]]
    n, q = len(values), len(tasks)
    e = EventBatch(('h',), torch.arange(n)[None], torch.tensor([[0., 1., 2., 2.]], dtype=torch.float64), torch.tensor([[2**64-1]*n], dtype=torch.uint64), torch.ones(1,n,1), torch.tensor([values], dtype=torch.float64), torch.tensor([n]), torch.ones(1,n,dtype=torch.bool), torch.ones(1,n,2,dtype=torch.bool), 'ticks')
    x = QueryBatch(('h',), torch.arange(q)[None], torch.full((1,q),2.,dtype=torch.float64), torch.tensor([[2**64-1]*q],dtype=torch.uint64), torch.ones(1,q,1), (tasks,), torch.tensor([starts or [0.]*q],dtype=torch.float64), torch.tensor([ends or [1.]*q],dtype=torch.float64), torch.ones(1,q,dtype=torch.bool),torch.tensor([q]))
    return e,x


def test_half_open_targets():
    from famjet.eval.oracle import exact_targets
    e,q = fixture(('mean','contrast','mean'), [0.,0.,3.], [1.,1.,4.])
    r = exact_targets(e,q)
    np.testing.assert_allclose(r.target[0,:2], [[12.,7.],[6.,0.]])
    assert r.supported.tolist() == [[True,True,False]]
    assert torch.isnan(r.target[0,2]).all()
    assert r.metadata['targets'][0][2] is None


def test_secondary_labels_and_unknown():
    from famjet.eval.oracle import exact_targets
    e,q = fixture(('latest','change_sign','presence','interval_support'))
    # Presence/support are scalar tasks, so query separately.
    r = exact_targets(e,fixture(('latest','change_sign'))[1])
    np.testing.assert_equal(r.target.numpy(), [[[14.,7.],[1.,0.]]])
    for name in ('presence','interval_support'):
        assert exact_targets(e,fixture((name,))[1]).target.item() == 1
    with pytest.raises(ValueError,match='task'):
        exact_targets(e,fixture(('invented',))[1])


def test_missing_coordinates_and_future():
    from famjet.eval.oracle import exact_targets
    e,q=fixture()
    e.normalization='independent'
    e.observed[0,2:,1]=False
    assert not exact_targets(e,q).supported.item()
    q.T[0,0]=-1
    assert not exact_targets(e,q).supported.item()


def test_categorical_latest_and_absence():
    from famjet.eval.oracle import exact_targets
    e,q=fixture(('corrected_categorical','random_binding'))
    e.values=torch.eye(32,dtype=torch.float64)[torch.tensor([[0,1,2,3]])]
    e.observed=torch.ones_like(e.values,dtype=torch.bool)
    r=exact_targets(e,q)
    assert r.target.tolist()==[[3.,3.]]
    e.values[0,3,0]=1
    with pytest.raises(ValueError,match='one-hot'):
        exact_targets(e,q)


def test_target_statistics_train_only():
    from famjet.eval.metrics import fit_target_statistics
    e,q=fixture(('mean','mean'))
    labels=torch.tensor([[[2.,7.],[6.,7.]]],dtype=torch.float64)
    ep=Episode(e,q,labels,torch.ones(1,2,dtype=torch.bool),{'split':'training'})
    s=fit_target_statistics([ep])['tasks']['mean']
    assert s['mean']==[4.,7.]
    assert s['coordinate_variance']==[4.,0.]
    assert s['pooled_variance']==2.
    assert s['scale']==pytest.approx(np.sqrt(2))
    assert s['constant_coordinates']==[False,True]
    with pytest.raises(ValueError,match='training'):
        fit_target_statistics([Episode(e,q,labels,ep.supported,{'split':'development'})])


def test_statistics_class_priors_and_unsupported():
    from famjet.eval.metrics import fit_target_statistics
    e,q=fixture(('random_binding',)*3)
    ep=Episode(e,q,torch.tensor([[2.,2.,4.]]),torch.tensor([[True,True,False]]),{'split':'training'})
    s=fit_target_statistics([ep])['tasks']['random_binding']
    assert len(s['class_distribution'])==32
    assert s['class_distribution'][2]==1
    assert s['count']==2


def test_no_write_presence_and_empty_windows():
    from famjet.eval.oracle import exact_targets
    e,q=fixture(('presence',))
    e.observed[:]=False
    assert exact_targets(e,q).target.item()==0
    assert not exact_targets(e,fixture(('latest',))[1]).supported.item()
    assert exact_targets(e,fixture(('interval_support',))[1]).target.item()==0


def test_integer_tick_precision():
    from famjet.eval.oracle import exact_targets
    e,q=fixture()
    e.timestamps=torch.tensor([[2**60,2**60+1,2**60+2,2**60+2]])
    from dataclasses import replace
    q=replace(q,T=torch.tensor([[2**60+2]]))
    assert exact_targets(e,q).target[0,0,0].item()==12.


def test_absent_presence_is_valid_even_without_factual_support():
    from famjet.eval.oracle import exact_targets
    from famjet.eval.metrics import fit_target_statistics
    e,q=fixture(('presence',))
    e.observed[:]=False
    r=exact_targets(e,q)
    assert r.target.item()==0
    assert not r.supported.item()
    assert not r.abstained.item()
    assert r.metadata['target_valid']==[[True]]
    ep=Episode(e,q,r.target,r.supported,{'split':'training'})
    s=fit_target_statistics([ep])['tasks']['presence']
    assert s['count']==1
    assert s['class_distribution']==[1.,0.]
    assert s['scale'] is None
    assert s['constant_coordinates']==[True]


def test_mixed_float_query_integer_ticks_preserve_half_open_boundaries():
    from dataclasses import replace
    from famjet.eval.oracle import exact_targets
    e,q=fixture()
    e.timestamps=torch.tensor([[2**60-2,2**60-1,2**60,2**60]],dtype=torch.int64)
    q=replace(q,T=torch.tensor([[2**60]],dtype=torch.float64))
    r=exact_targets(e,q)
    assert r.target.tolist()==[[[12.,7.]]]
    assert r.metadata['observed_counts'][0][0][0]==[2,2]


@pytest.mark.parametrize('newer,older,expected', [
    (float(2**60),2**60-1,1),
    (2**60-1,float(2**60),-1),
    (2**60,2**60-1,1),
    (0.5,0,0.5),
    (0,0.5,-0.5),
])
def test_exact_time_difference(newer,older,expected):
    from famjet.eval.oracle import exact_time_difference
    assert exact_time_difference(newer,older)==expected
