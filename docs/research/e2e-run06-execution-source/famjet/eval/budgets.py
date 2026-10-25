"""Packed capacity versus live backing storage, static weights and wire size.

Storage bytes are distinct tensor backing allocations, not allocator/driver RSS.
Logical fields count each retained value; shared views share one physical storage.
Autograd can retain arbitrarily large history beyond these allocations: report
that separately and refuse a bounded inference claim until explicitly detached.
"""
import numpy as np
import torch
from famjet.eval.state_io import state_bytes, validate_snapshot, retained_tensor_chain

_COMMON_METADATA = {'history_hash', 'time_unit_hash', 'last_event_id',
                    'first_observed_time', 'last_observed_time', 'has_observation'}


def _inventory(tensors):
    fields = {}; storages = {}; graph = False; complete = True
    retained = []; tensor_ids = {}

    def inspect(tensor):
        nonlocal graph, complete
        if id(tensor) in tensor_ids:
            return tensor_ids[id(tensor)]
        tid = len(tensor_ids)
        tensor_ids[id(tensor)] = tid
        storage = tensor.untyped_storage()
        # External NumPy/mmap owners can exceed the exposed tensor storage.
        # Torch cannot enumerate their opaque deleters; fail closed for budgets.
        owned = storage.resizable()
        complete &= owned
        # _cdata identifies even zero-sized allocations; data_ptr can collide at 0.
        key = (str(tensor.device), storage._cdata)
        if key not in storages:
            storages[key] = (len(storages), storage.nbytes())
        sid, allocated = storages[key]
        has_gradient = (tensor.is_leaf or tensor.retains_grad) and tensor.grad is not None
        retained_graph = tensor.grad_fn is not None or has_gradient
        graph |= retained_graph
        retained.append(dict(dtype=str(tensor.dtype).removeprefix('torch.'), shape=list(tensor.shape),
                            logical_bytes=tensor.numel()*tensor.element_size(), storage_id=sid,
                            storage_bytes=allocated, storage_offset=tensor.storage_offset(),
                            stride=list(tensor.stride()), contiguous=tensor.is_contiguous(),
                            device=str(tensor.device), grad_fn=tensor.grad_fn is not None,
                            attached_gradient=has_gradient, requires_grad=tensor.requires_grad,
                            backing_storage_complete=owned))
        return tid

    for name, tensor in tensors.items():
        ids = [inspect(t) for t in retained_tensor_chain(tensor)]
        fields[name] = dict(retained[ids[0]], retained_tensor_ids=ids)
    return dict(fields=fields, logical_bytes=sum(v['logical_bytes'] for v in fields.values()),
                retained_storage_bytes=sum(n for _, n in storages.values()), graph_retention=graph,
                graph_storage_bytes=None if graph else 0, backing_storage_complete=complete,
                retained_tensors=retained)


def state_ledger(snapshot) -> dict:
    validate_snapshot(snapshot)
    inventory = _inventory({**{'payload.'+k: v for k, v in snapshot.payload.items()},
                            **{k: getattr(snapshot, k) for k in ('last_time', 'valid', 'event_offset')}})
    metadata = {k: v['logical_bytes'] for k, v in inventory['fields'].items()
                if not k.startswith('payload.') or k.removeprefix('payload.') in _COMMON_METADATA}
    metadata.update(parameter_hash=32, schema_version=8)
    inventory.update(metadata=metadata, metadata_bytes=sum(metadata.values()),
                     payload_bytes=inventory['logical_bytes']-(sum(metadata.values())-40),
                     logical_bytes=inventory['logical_bytes']+40, serialized_bytes=len(state_bytes(snapshot)),
                     alias_policy='logical fields counted individually; distinct full backing allocations counted once',
                     graph_policy='training graph retention is unbounded/unmeasured; inference requires detach')
    return inventory


def require_inference_state(snapshot):
    if state_ledger(snapshot)['graph_retention']:
        raise ValueError('snapshot retains an autograd graph; detach at explicit inference boundary')


def _contains_dynamic(value, seen=None):
    if seen is None:
        seen = set()
    if isinstance(value, (torch.Tensor, np.ndarray)):
        return True
    if id(value) in seen:
        return False
    seen.add(id(value))
    if isinstance(value, dict):
        return any(_contains_dynamic(k, seen) or _contains_dynamic(v, seen) for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_dynamic(v, seen) for v in value)
    # Unknown objects (loaders, open files, closures) are not static schema.
    return value is not None and type(value) not in (str, int, float, bool)


def model_ledger(model: torch.nn.Module) -> dict:
    """Count registered static weights/buffers; reject unregistered tensor caches.

    Arbitrary scalar attributes cannot be proven history-independent by counting;
    the isolation registry additionally checks the entire constructor schema.
    """
    if not isinstance(model, torch.nn.Module):
        raise TypeError('model_ledger requires nn.Module')
    from famjet.models.task_model import TaskModel
    if type(model) is TaskModel:
        model.validate_metadata()
    for module in model.modules():
        for name, value in vars(module).items():
            if name in {'_parameters', '_buffers', '_modules'}:
                continue
            if _contains_dynamic(value):
                raise ValueError(f'unregistered/hidden model attribute: {name}')
    parameters = dict(model.named_parameters())  # repeated tied Parameter objects count once
    buffers = dict(model.named_buffers())
    ledger = _inventory({**{'parameter.'+k: v for k, v in parameters.items()},
                         **{'buffer.'+k: v for k, v in buffers.items()}})
    ledger.update(parameter_bytes=sum(p.numel()*p.element_size() for p in parameters.values()),
                  buffer_bytes=sum(p.numel()*p.element_size() for p in buffers.values()))
    return ledger


def budget_report(method, snapshot, *, limit_bytes: int) -> dict:
    from famjet.eval.isolation import export_method
    if type(limit_bytes) is not int or limit_bytes < 0:
        raise ValueError('limit_bytes must be a nonnegative integer')
    spec = export_method(method)
    state = state_ledger(snapshot)
    if snapshot.parameter_hash != method._parameter_hash():
        raise ValueError('snapshot parameter hash mismatch')
    method.persistent_nbytes(snapshot)  # method-specific layout/identity validation
    bounded = not (spec['kind'] == 'packed' and spec['schema']['policy'] == 'exact')
    within = state['logical_bytes'] <= limit_bytes and state['retained_storage_bytes']+40 <= limit_bytes
    static = model_ledger(method) if isinstance(method, torch.nn.Module) else dict(logical_bytes=0, retained_storage_bytes=0)
    accountable = state['backing_storage_complete'] and static.get('backing_storage_complete', True)
    graph = state['graph_retention'] or static.get('graph_retention', False)
    return dict(state=state, static=static, bounded=bounded, within_limit=within,
                eligible=bounded and within and not graph and accountable, limit_bytes=limit_bytes,
                end_to_end_logical_bytes=state['logical_bytes']+static['logical_bytes'])
