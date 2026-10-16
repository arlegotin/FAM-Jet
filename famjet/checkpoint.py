"""Checksummed atomic optimizer-boundary checkpoints, separate from snapshots."""
import hashlib
import io
from pathlib import Path
import random
import numpy as np
import torch
from famjet.artifacts import atomic_bytes
from famjet.provenance import canonical_hash

RunContext = dict
_MAGIC = b'FAMJET-CHECKPOINT-1\n'
_FIELDS = {'schema_version','config','execution_policy','config_hash','policy_hash',
           'source_hash','source','data_hash','data_identity','lock_hash','model',
           'model_hash','writer_hash','model_state','optimizer','scheduler','scaler',
           'optimizer_active_parameters','rng','sampler','completed_step','accumulation_position','consumed_episode_ids',
           'restarted_accumulation'}


def capture_rng(device):
    state = np.random.get_state()
    return {'python': random.getstate(), 'numpy': (state[0],state[1].tolist(),state[2],state[3],state[4]),
            'torch_cpu': torch.get_rng_state(),
            'torch_mps': torch.mps.get_rng_state().cpu() if device == 'mps' else None}


def restore_rng(rng, device):
    random.setstate(rng['python'])
    state=rng['numpy']
    np.random.set_state((state[0],np.asarray(state[1],dtype=np.uint32),state[2],state[3],state[4]))
    torch.set_rng_state(rng['torch_cpu'])
    if device == 'mps':
        if rng['torch_mps'] is None: raise ValueError('missing MPS RNG state')
        torch.mps.set_rng_state(rng['torch_mps'])


def _validate(context):
    from famjet.config import RunConfig, _parse
    from famjet.eval.isolation import _reconstruct
    if type(context) is not dict or set(context) != _FIELDS or context['schema_version'] != 1:
        raise ValueError('checkpoint schema/cache mismatch')
    config=_parse(context['config'],RunConfig,'checkpoint.config')
    for field,value in [('config_hash',context['config']),('policy_hash',context['execution_policy']),
                        ('data_hash',context['data_identity']),('model_hash',context['model'])]:
        if context[field] != canonical_hash(value): raise ValueError(f'checkpoint {field} mismatch')
    for field in ['source_hash','lock_hash','model_hash','writer_hash']:
        if type(context[field]) is not str or len(context[field]) != 64:
            raise ValueError(f'invalid checkpoint {field}')
        try: int(context[field],16)
        except ValueError as exc: raise ValueError(f'invalid checkpoint {field}') from exc
    step,acc=context['completed_step'],context['accumulation_position']
    if type(step) is not int or not 0 <= step <= config.training.optimizer_steps or type(acc) is not int or not 0 <= acc < config.training.effective_batch:
        raise ValueError('invalid checkpoint step/accumulation')
    ids=context['consumed_episode_ids']
    if ids != [f'train-{i:012d}' for i in range(step*config.training.effective_batch)]:
        raise ValueError('checkpoint consumed sampler sequence mismatch')
    sampler=context['sampler']
    if set(sampler) != {'namespace','seed','position'} or sampler['namespace'] != 'shared_training_draws_v1' or sampler['seed'] != config.seed or sampler['position'] != len(ids)+acc:
        raise ValueError('checkpoint sampler mismatch')
    if context['scheduler'] != {'kind':'constant','last_step':step} or context['scaler'] is not None:
        raise ValueError('checkpoint scheduler/scaler mismatch')
    rng=context['rng']
    if type(rng) is not dict or set(rng) != {'python','numpy','torch_cpu','torch_mps'}:
        raise ValueError('checkpoint RNG schema mismatch')
    # Validate generator states without changing the caller's random trajectory.
    previous=capture_rng(config.resources.device)
    try: restore_rng(rng,config.resources.device)
    finally: restore_rng(previous,config.resources.device)
    model=_reconstruct(context['model'])
    expected=model.state_dict()
    if set(expected) != set(context['model_state']): raise ValueError('checkpoint parameter schema mismatch')
    for name,value in context['model_state'].items():
        if not isinstance(value,torch.Tensor) or value.dtype != expected[name].dtype or not torch.equal(value,expected[name]):
            raise ValueError('checkpoint parameter mismatch')
    # Writer identity is native-device-specific for learned represented rates.
    model=model.to(config.resources.device)
    if model._parameter_hash() != context['writer_hash']:
        raise ValueError('checkpoint writer/rate mismatch')
    optimizer=torch.optim.AdamW(model.parameters(),lr=config.training.learning_rate,weight_decay=config.training.weight_decay)
    original=optimizer.state_dict()['param_groups']
    groups=context['optimizer'].get('param_groups')
    if groups != original: raise ValueError('checkpoint optimizer hyperparameter/group mismatch')
    optimizer.load_state_dict(context['optimizer'])
    names=[n for n,p in model.named_parameters() if p in optimizer.state]
    if names != context['optimizer_active_parameters']:
        raise ValueError('checkpoint incomplete optimizer state')
    for parameter,state in optimizer.state.items():
        for key in ['exp_avg','exp_avg_sq']:
            value=state.get(key)
            if not isinstance(value,torch.Tensor) or value.shape != parameter.shape or value.dtype != parameter.dtype:
                raise ValueError('checkpoint optimizer moment shape/dtype mismatch')
        if not {'step','exp_avg','exp_avg_sq'} <= set(state) or int(state['step']) != step:
            raise ValueError('checkpoint optimizer step/state mismatch')
        if not all(torch.isfinite(v).all() for v in state.values() if isinstance(v,torch.Tensor)):
            raise ValueError('checkpoint nonfinite optimizer state')
    if step and not optimizer.state: raise ValueError('checkpoint missing optimizer state')


def save_checkpoint(path: Path, context: dict) -> None:
    """Model/optimizer/RNG always describe a complete step, never partial grads.

    A nonzero accumulation position is diagnostic only; load restarts the entire
    next step from these boundary tensors/RNG and the committed sampler prefix.
    """
    _validate(context)
    buffer=io.BytesIO()
    torch.save(context,buffer)
    payload=buffer.getvalue()
    path=Path(path)
    if path.exists():
        load_checkpoint(path,{})  # Preserve only a previously valid file.
        atomic_bytes(path.with_suffix(path.suffix+'.previous'),path.read_bytes())
    atomic_bytes(path,_MAGIC+hashlib.sha256(payload).hexdigest().encode()+b'\n'+payload)


def load_checkpoint(path: Path, expected: dict) -> dict:
    raw=Path(path).read_bytes()
    try:
        magic,digest,payload=raw.split(b'\n',2)
        if magic+b'\n' != _MAGIC or hashlib.sha256(payload).hexdigest().encode() != digest:
            raise ValueError('checkpoint checksum mismatch')
        context=torch.load(io.BytesIO(payload),map_location='cpu',weights_only=True)
    except (ValueError,EOFError,RuntimeError) as exc:
        raise ValueError('corrupt checkpoint/checksum') from exc
    _validate(context)
    for field,value in expected.items():
        if field not in _FIELDS or context[field] != value:
            raise ValueError(f'checkpoint {field} mismatch')
    context['restarted_accumulation']=context['accumulation_position'] > 0
    context['sampler']['position']=len(context['consumed_episode_ids'])
    context['accumulation_position']=0
    return context
