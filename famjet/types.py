"""Version-1 public contracts; layouts use B histories, N events and Q queries.

Constructors do not validate tensors or perform device synchronization. Call the
host-side validators in ``famjet.data.schema`` before dispatching to a kernel.
Tensor ownership/copying belongs to the adapter, not these lightweight records.
"""
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from torch import Tensor

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class EventValidation:
    gaps: Tensor  # CPU float64 [B,N], first event/padding zero
    write_mask: Tensor  # bool [B,N], present and at least one observed channel
    schema_version: int = SCHEMA_VERSION


@dataclass
class EventBatch:
    history_ids: tuple[str, ...]
    event_ids: Tensor  # int64 [B,N], unique per history, stable tie order
    timestamps: Tensor  # CPU float64 or int64 ticks [B,N]
    key_ids: Tensor  # int64 or uint64 [B,N]
    key_features: Tensor  # floating nonnegative [B,N,K]
    values: Tensor  # floating finite [B,N,V], even when unobserved
    lengths: Tensor  # int64 [B]
    present: Tensor  # bool [B,N], prefix padding mask
    observed: Tensor  # bool [B,N,V], false on padding
    time_unit: str
    normalization: Literal['shared', 'independent'] = 'shared'
    auxiliary: dict[str, Tensor] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION
    validation: EventValidation | None = field(default=None, init=False, repr=False, compare=False)


@dataclass(frozen=True)
class QueryBatch:
    history_ids: tuple[str, ...]
    query_ids: Tensor  # int64 [B,Q], unique per history
    T: Tensor  # CPU float64 or int64 ticks [B,Q]
    key_ids: Tensor  # int64 or uint64 [B,Q]
    key_features: Tensor  # floating nonnegative [B,Q,K]
    tasks: tuple[tuple[str, ...], ...]  # [B,Q], task registry owned by target builder
    age_start: Tensor  # CPU float64 [B,Q], half-open age interval
    age_end: Tensor  # CPU float64 [B,Q]
    present: Tensor  # bool [B,Q]
    lengths: Tensor  # int64 [B]
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True)
class Episode:
    events: EventBatch
    queries: QueryBatch
    labels: Tensor  # [B,Q,V] numeric or [B,Q] categorical
    supported: Tensor  # bool [B,Q]
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True)
class Snapshot:
    payload: dict[str, Tensor]  # all method-owned state and caches
    last_time: Tensor  # CPU float64/int64 [B]; placeholder 0 when invalid
    valid: Tensor  # bool [B], whether a last stream time exists
    parameter_hash: str  # writer/rate parameter content identity
    event_offset: Tensor  # int64 [B], consumed events (excludes padding)
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True)
class FeatureBatch:
    values: Tensor  # [B,Q,F]
    supported: Tensor  # bool [B,Q]
    diagnostics: dict[str, Tensor] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True)
class ReadResult:
    prediction: Tensor | None  # [B,Q,V] numeric, or None for categorical
    logits: Tensor | None  # [B,Q,C] categorical, or None for numeric
    support: Tensor  # [B,Q] numeric support output
    failure: Tensor  # bool [B,Q], never discarded by fallback
    diagnostics: dict[str, Tensor] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True)
class PredictionBatch:
    history_ids: tuple[str, ...]
    query_ids: Tensor
    prediction: Tensor  # final prediction including training-mean fallback
    target: Tensor
    supported: Tensor
    failure: Tensor
    abstained: Tensor
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


@runtime_checkable
class MemoryMethod(Protocol):
    """Public adapter protocol; numerical kernels are torch.nn.Modules."""
    def init_state(self, batch_size: int, *, device: str, dtype: str) -> Snapshot: ...
    def encode(self, events: EventBatch, state: Snapshot | None = None,
               *, mode: str = 'stream') -> Snapshot: ...
    def advance_copy(self, state: Snapshot, query_time: float) -> Snapshot: ...
    def read(self, state: Snapshot, queries: QueryBatch) -> ReadResult: ...
    def persistent_nbytes(self, state: Snapshot) -> int: ...
    def parameter_nbytes(self) -> int: ...
