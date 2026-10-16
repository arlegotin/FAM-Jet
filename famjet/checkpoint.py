"""Checksummed atomic optimizer-boundary checkpoints, separate from snapshots."""
import hashlib
import io
import math
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


def _preflight_model(context, config):
    """Bind allocation descriptors to the bounded training constructor schema.

    No model/tensor reconstruction occurs here. The registry still owns full
    wire semantics; this checks only sizes and configuration compatibility.
    """
    from famjet.train import _check_smoke_dimensions
    from famjet.readers.structured import validate_reader_schema
    _check_smoke_dimensions(config)
    m,d=config.model,config.data
    try:
        wire=context['model']; schema=wire['schema']; kernel=schema['kernel']
        reader=schema['reader']; validate_reader_schema(reader)
        count_name='coefficients' if m.method in {'polynomial','multiscale'} else 'anchors'
        count=m.multiscale.order*m.multiscale.scale_order if m.method=='multiscale' else sum(m.polynomial.orders) if m.method=='polynomial' else m.J
        expected_reader={'kind':m.reader.kind,
            'feature_spec':{'family':m.method,count_name:count,'key_dim':m.K,'value_dim':d.value_dim},
            'query_spec':{'key_dim':m.K},'budget':{'width':m.reader.width,'hidden_layers':m.reader.layers}}
        if wire['kind'] != 'task' or m.method not in {'jet','bank','polynomial','multiscale'} or kernel['kind'] != m.method or reader != expected_reader:
            raise ValueError('checkpoint reader/model configuration mismatch')
        if schema['inference_config'] != {'schema_version':1,'writer':m.writer,'rate_mode':'fixed' if m.rates is None else m.rates.mode} or schema['frozen_rates'] is not False:
            raise ValueError('checkpoint training model configuration mismatch')
        ks=kernel['schema']
        if any(type(ks[k]) is not int or ks[k] != value for k,value in [('key_dim',m.K),('value_dim',d.value_dim)]):
            raise ValueError('checkpoint kernel dimensions mismatch')
        if m.method == 'multiscale':
            from famjet.memory.multiscale import validate_system
            from famjet.memory.hippo import validate_allocation
            if set(ks) != {'order','scale_order','epsilon','tau0','declared_gaps','key_dim','value_dim','cache_limit_bytes','t_ref','chunk_size','dtype'}:
                raise ValueError('checkpoint multiscale schema mismatch')
            if (any(ks[k] != getattr(m.multiscale,k) for k in ('order','scale_order','epsilon','tau0'))
                    or type(ks['declared_gaps']) not in (tuple,list)
                    or list(ks['declared_gaps']) != list(m.multiscale.declared_gaps)):
                raise ValueError('checkpoint multiscale allocation mismatch')
            if (ks['dtype'] != m.precision or type(ks['cache_limit_bytes']) is not int
                    or ks['cache_limit_bytes'] != config.resources.cache_limit_bytes
                    or type(ks['chunk_size']) is not int or ks['chunk_size'] != 32 or kernel['weights'] != {}):
                raise ValueError('checkpoint multiscale construction mismatch')
            validate_system(ks['order'],ks['scale_order'],ks['epsilon'],ks['tau0'])
            validate_allocation((ks['order'],)*ks['scale_order'],(ks['tau0'],)*ks['scale_order'],
                                ks['declared_gaps'],ks['cache_limit_bytes'],4)
            return
        if m.method == 'polynomial':
            from famjet.memory.hippo import validate_allocation
            expected = {'orders':list(m.polynomial.orders),'taus':list(m.polynomial.taus),
                        'declared_gaps':list(m.polynomial.declared_gaps)}
            if set(ks) != {'orders','taus','declared_gaps','key_dim','value_dim','cache_limit_bytes','t_ref','chunk_size','dtype'}:
                raise ValueError('checkpoint polynomial schema mismatch')
            if any(type(ks[k]) not in (tuple,list) or list(ks[k]) != v for k,v in expected.items()):
                raise ValueError('checkpoint polynomial allocation mismatch')
            if (ks['dtype'] != m.precision or ks['cache_limit_bytes'] != config.resources.cache_limit_bytes
                    or type(ks['chunk_size']) is not int or ks['chunk_size'] != 32 or kernel['weights'] != {}):
                raise ValueError('checkpoint polynomial construction mismatch')
            validate_allocation(ks['orders'],ks['taus'],ks['declared_gaps'],ks['cache_limit_bytes'],4)
            return
        source=ks['rate_source']
        if m.rates.mode == 'learned':
            expected_source={'count':m.J,'log_min':math.log(m.rates.bounds[0]),'log_max':math.log(m.rates.bounds[1])}
            if type(source) is not dict or type(source.get('count')) is not int or source != expected_source:
                raise ValueError('checkpoint learned rate source mismatch')
            names={'logits','represented_rates'}
        else:
            if source is not None: raise ValueError('checkpoint fixed rate source mismatch')
            names={'rates'}
        weights=kernel['weights']
        if type(weights) is not dict or set(weights) != names:
            raise ValueError('checkpoint rate components mismatch')
        for value in weights.values():
            if (type(value) is not dict or value.get('shape') != [1,m.J]
                    or any(type(x) is not int for x in value['shape']) or value.get('dtype') != m.precision):
                raise ValueError('checkpoint rate component layout mismatch')
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('checkpoint allocation descriptor schema mismatch') from exc


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
    _preflight_model(context,config)
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
    raw=context['optimizer']
    if type(raw) is not dict or set(raw) != {'state','param_groups'}:
        raise ValueError('checkpoint optimizer schema/cache mismatch')
    groups=raw['param_groups']
    if (type(groups) is not list or len(groups) != 1 or type(groups[0]) is not dict
            or type(groups[0].get('params')) is not list
            or any(type(i) is not int for i in groups[0]['params']) or groups != original):
        raise ValueError('checkpoint optimizer hyperparameter/group mismatch')
    # Validate the serialized mapping before load_state_dict can cast moment
    # dtypes or reinterpret IDs. Registration order fixes ID -> parameter/name.
    parameters=dict(zip(original[0]['params'],model.named_parameters()))
    states=raw['state']
    if type(states) is not dict or any(type(i) is not int or i not in parameters for i in states):
        raise ValueError('checkpoint optimizer parameter ID mismatch')
    names=[name for i,(name,_) in parameters.items() if i in states]
    if type(context['optimizer_active_parameters']) is not list or names != context['optimizer_active_parameters']:
        raise ValueError('checkpoint incomplete optimizer state')
    for i,state in states.items():
        parameter=parameters[i][1]
        if type(state) is not dict or set(state) != {'step','exp_avg','exp_avg_sq'}:
            raise ValueError('checkpoint optimizer state/cache schema mismatch')
        for key in ['exp_avg','exp_avg_sq']:
            value=state[key]
            if (not isinstance(value,torch.Tensor) or value.layout != torch.strided
                    or value.shape != parameter.shape or value.dtype != parameter.dtype):
                raise ValueError('checkpoint optimizer moment shape/dtype mismatch')
            if not bool(torch.isfinite(value).all()):
                raise ValueError('checkpoint nonfinite optimizer moment')
        if not bool((state['exp_avg_sq'] >= 0).all()):
            raise ValueError('checkpoint negative optimizer second moment')
        counter=state['step']
        if (not isinstance(counter,torch.Tensor) or counter.layout != torch.strided
                or counter.ndim != 0 or counter.dtype not in {torch.float32,torch.float64}
                or not bool(torch.isfinite(counter)) or counter.item() != step):
            raise ValueError('checkpoint optimizer step mismatch')
    if step and not states: raise ValueError('checkpoint missing optimizer state')
    optimizer.load_state_dict(raw)


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
    for field,value in expected.items():
        if type(context) is not dict or field not in _FIELDS or context.get(field) != value:
            raise ValueError(f'checkpoint {field} mismatch')
    _validate(context)
    context['restarted_accumulation']=context['accumulation_position'] > 0
    context['sampler']['position']=len(context['consumed_episode_ids'])
    context['accumulation_position']=0
    return context
