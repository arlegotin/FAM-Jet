Task18 kernel Stage A preflight
===============================

This directory is an external, prospective diagnostic implementation. Importing
it performs no scientific work. The checked-in seal has null authority and must
refuse execution. Source acceptance, this implementation, actual Stage A, and
whole Task18 remain separate decisions.

`descriptors.py` defines the exact 32 rows and 128 named slots, including four
nonapplicable O slots per candidate. The six candidates therefore have 768
recorded slots and at most **744 applicable reads**, within the original 768 cap.
`fixture-descriptors.json` serializes definitions, not snapshots or results.
History/query identities are fixed SHA256-derived opaque schema identifiers.
No generator, search, target, learned checkpoint or scientific fixture runs at
import, during observation, or in the focused tests.

`reference.py` depends only on the standard library. It derives exponential-prior
Gram/window entries, canonical diagonal-scaled ridge solves, event sums, delays,
guards and three-way comparisons independently at 80/160 Decimal digits. The
endpoint antiderivatives intentionally share no production integral branches.
Partial pivoting uses largest absolute column value and lowest current row ties;
event/channel sums sort by decreasing absolute magnitude with stable ties.
Finite values remain mandatory when decisions agree. No precision repair occurs.

`authority.py` observes hashes without constructing models and refuses incomplete,
extra, changed, dirty, stale or mismatched launch authority before backend import.
The seal binds runtime/Decimal implementation, accepted source/package/lock,
unchanged kernels, adopted mathematics, corrected manifest, helpers, frozen
training metadata, actual rates/static exports, implementation review, resource
boundary, fresh disk/power/host observations, output and a root release tied to
the exact payload hash. Its hash layers are: source/input files -> observed
inventory -> seal payload -> root release. The seal never includes its own hash.
The later root must regenerate observations at the final clean HEAD; an earlier
prospective observation is not permission to bypass exact identity checks.

`driver.py` visits the fixed candidate/group/row order. Source-only failures remain
FAILED and permit remaining original slots; reader failures stop a candidate;
reference/common/engine/resource failures stop everything. It retains unexecuted
inventory and actual started operation counts, including failures. Keyboard
cancellation propagates to the process-group owner. No retry/replacement exists.

`production.py` constructs at most one canonical snapshot per row/family after
authority, then transforms saved copies. It reconstructs sealed factors without
an eigendecomposition. U transports rates, units and the identical dimensionless
arrays. Its training metadata is explicitly DERIVED unit transport; original
accepted records remain parent evidence, not a fictitious refit in new units.
R uses the declared Jet coordinate round trip or binary64 Bank reload. Poison
bits remain a nonfinite sentinel. Saved inputs and resumed ownership are checked
without an extra prediction. `reader_worker.py` accepts only the existing closed
snapshot/query/static request and delegates the existing isolation boundary. Its
profile records actual coefficient/window/clone/reconstruction/read entries;
flushed per-call counter files survive a kill. Scientific reference events never
enter that worker. An engine failure is a whole-stage failure, never fallback.

`monitor.py` owns a fresh process group, kills/reaps it on timeout, cancellation or
resource failure, measures sampled absolute/process-tree RSS separately from
per-worker post-import incremental RSS, and charges outputs including temporary
overlap. It uses native `ps`; sandbox-only execution may deny that observation.
Focused sleeper tests use an explicitly controlled sampler and establish no
native numerical memory forecast. Root separately verified read-only native ps
availability through approved escalation. A monitoring-capable execution context
is still necessary for the actual allocation. Sampling is every .02 seconds;
reported RSS is sampled resident memory, not allocator peak or a proof that no
between-sample spike occurred. Timings are descriptive heterogeneous call/group
boundaries, with no extra timing reads, warmup, stable-p95 or throughput claim.

Only the exact declared `/bin/ps -axo pid=,ppid=,rss=,comm=,args=` process,
matching its PID, executable, arguments and expected parent, is an observer
helper. Every other worker requires its post-import baseline; an unresolved
descendant blocks completion. Observer RSS remains in absolute totals and is
charged with baseline zero. Conservative outer/inner observer peaks are added
to the worker incremental peak, including late declarations after a short
observer exits. No generic non-Python or basename exemption exists.

Pending setup and exact invocation
----------------------------------

No setup command or scientific command is released now. Actual represented rates
and six factor exports are null because none were constructed here. A separate
root allocation must first invoke the existing fixed constructors at the actual
represented caller-order rates and `KernelReadModel` exactly once per candidate,
export via existing `export_method`, and record every cost. There is no new
trainer or generic setup framework in this directory. Root owns the concrete
setup command and review. A failed factor may instead produce exactly
`{candidate:[family,rho.hex()],status:"FAILED",factor_diagnostics:{...}}`; it
remains failed and that candidate receives no reads. No alternate factorization.

The setup ledger must contain `actual_factor_constructions:6`, `actual_reads:0`,
`allocation_start_monotonic`, `source_full_git`, `package_hash`, exact sealed
`static_exports` and `represented_rate_records` path/hash maps, absolute
`output_directory`, `output_peak_bytes` and `incremental_worker_peak_bytes`.
Retain absolute/process-tree readings, baselines, failed setup work, times and
serialization/copy counts in that same ledger. Files, logs and temporary overlap
in the preparation directory remain charged to the 64MiB total. Static exports
are exact existing closed method records; rates are JSON lists of binary64 hex
strings, four for Jet and eight for Bank, in caller order. Do not regenerate a
second grid. Setup files should remain outside the clean source checkout.

Setup and the later driver share the **same original monotonic start and absolute
start+600s deadline**. Root's verification gap consumes that allowance. The
resource boundary has exactly the five constant fields checked in authority.py
plus `allocation_start_monotonic`, `allocation_start_utc_epoch`,
`deadline_monotonic`, `setup_ledger:{path,sha256}`. A fresh launch snapshot has
`utc_epoch`, `free_disk_bytes`, `power_observation`, and matching `host_identity`.
The implementation review has `{path,sha256,approved:true}`. A release has
`{approved:true,scope:"Stage A scientific execution",payload_sha256,ruling_path,
ruling_sha256}`. All must be real, current and independently reviewed. No null
may be bypassed by calling the internal control-loop test seam.

After that separate release, the prospective invocation from repository root is:

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
.venv/bin/python -m validation.kernel_stage_a --seal /ABS/ROOT-SEALED-stage-a.json
```

The output directory must be absent at launch. Outputs include `monitor.json`,
`stage-a.json` (when the worker can finish), outer stdout/stderr, baseline events,
canonical/input snapshot files, compact static ledgers, per-read flushed traces,
and P/A/B slot records. A kill can leave partial files; those remain failed,
charged evidence. The setup directory remains charged alongside this directory.
No Stage B, fitting, training, common panel, corpus, bootstrap or protected access
is provided by this command.

Focused verification:

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_kernel_stage_a_preflight.py
```
