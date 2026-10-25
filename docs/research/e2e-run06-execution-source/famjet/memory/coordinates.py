"""Invertible Laguerre coordinates, stepped independently of jet_step."""
from torch import Tensor
from famjet.memory.jet import JetState, _core_coefficients, _write, _state_shape, _require


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

    Tensor-only core with the same preconditions as jet_step: validate inputs
    before stepping, and prepare delta on the state dtype/device. A false write
    mask suppresses only the impulse; padding separately requires delta=0.
    This recurrence never calls jet_step or converts to Z/H for stepping.
    """
    a, ad = _core_coefficients(rates, delta)
    a, ad = a[..., None, None], ad[..., None, None]
    impulse = _write(key, value, gate, event_present)
    return a*l0 + impulse, a*l1 - 2*ad*l0 + impulse
