"""Invertible Laguerre coordinates, stepped independently of jet_step."""
from torch import Tensor
from famjet.memory.jet import JetState, _validate_step, _coefficients, _write, _state_shape, _require


def to_laguerre(state: JetState) -> tuple[Tensor, Tensor]:
    _state_shape(state)
    return state.z.clone(), state.z - 2*state.h


def from_laguerre(l0: Tensor, l1: Tensor) -> JetState:
    state = JetState(l0, (l0-l1)/2)
    _state_shape(state)
    _require(l0.device == l1.device and l0.dtype == l1.dtype and l0.shape == l1.shape,
             'Laguerre coordinates must have equal shape/device/dtype')
    return state


def laguerre_step(l0: Tensor, l1: Tensor, key: Tensor, value: Tensor, gate: Tensor,
                  delta: Tensor, rates: Tensor, event_present: Tensor) -> tuple[Tensor, Tensor]:
    """L0'=a L0+X, L1'=a L1-2ad L0+X using OLD L0.

    Input validation and exponential weights are shared, but this recurrence
    never calls jet_step or converts to Z/H for stepping.
    """
    import torch
    _validate_step(JetState(l0, l1), key, value, gate, delta, rates, event_present)
    gaps = torch.where(event_present.to(delta.device), delta, torch.zeros_like(delta))
    a, ad = _coefficients(rates, gaps)
    a, ad = a[..., None, None], ad[..., None, None]
    impulse = _write(key, value, gate, event_present)
    return a*l0 + impulse, a*l1 - 2*ad*l0 + impulse
