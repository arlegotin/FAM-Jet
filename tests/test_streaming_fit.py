"""Bounded repeatable fits must retain the original moments and trajectory."""
from dataclasses import replace
import pytest
import torch
from famjet.types import Episode
from test_task_model import model
from jet_fixtures import events,queries,kernel_case


@pytest.mark.parametrize('family',['jet','bank'])
def test_streamed_fit_and_training_trajectory_equal_materialized(family,kernel_case):
    dtype,device,_=kernel_case
    a=model(family,dtype=dtype,device=device);b=model(family,dtype=dtype,device=device);b.load_state_dict(a.state_dict())
    e=events(dtype,device);q=queries(e,[[8,12],[7,14]])
    ep=Episode(e,q,torch.arange(8,device=device,dtype=dtype).reshape(2,2,2),torch.ones(2,2,device=device,dtype=torch.bool),{'split':'training'})
    eps=[ep,replace(ep,labels=ep.labels*.4)]
    a.fit_statistics(eps);b.fit_statistics(lambda:iter(eps))
    assert a.fit_provenance==b.fit_provenance and a.target_statistics==b.target_statistics
    assert a.kernel.t_ref==b.kernel.t_ref
    oa=torch.optim.AdamW(a.parameters(),lr=.001);ob=torch.optim.AdamW(b.parameters(),lr=.001)
    for sample in eps:
        for m,o in ((a,oa),(b,ob)):
            o.zero_grad();p=m(sample.events,sample.queries,encode_mode='terminal').prediction
            (p-sample.labels).square().mean().backward();o.step()
        for key,value in a.state_dict().items():assert torch.equal(value,b.state_dict()[key])
    for key,state in oa.state_dict()['state'].items():
        for name,value in state.items():assert torch.equal(value,ob.state_dict()['state'][key][name])


def test_stream_change_rejected_transactionally():
    from famjet.eval.isolation import model_identity
    a=model();e=events();q=queries(e,[[8],[7]])
    ep=Episode(e,q,torch.ones(2,1,2,dtype=torch.float64),torch.ones(2,1,dtype=torch.bool),{'split':'training'})
    a.fit_statistics([ep]);before=model_identity(a);calls=0
    def changing():
        nonlocal calls
        calls+=1
        return iter([replace(ep,events=replace(e,timestamps=e.timestamps*100),labels=ep.labels if calls==1 else ep.labels*2)])
    with pytest.raises(ValueError,match='repeat|changed'):a.fit_statistics(changing)
    assert model_identity(a)==before
