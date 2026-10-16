# FAM-Jet

Query-conditioned exponential-moment memory research: compress a stream once, then answer different temporal questions from the retained state. The primary question is whether exact first temporal moments improve retrieval under measured state and system costs; the recurrence itself is established repeated-pole memory.

Tasks 1–9 are accepted: environment/contracts, independent CPU FP64 oracles, jet and exponential-bank kernels, deterministic synthetic populations, observed-event Beijing preparation, packed references, and restartable bounded summaries. Task 10 adds retained-state ledgers, controlled isolated inference and checksummed atomic snapshots; review round1 fixes are verified and pending re-review. Arithmetic, preparation and bounded storage controls work; no trained-model accuracy comparison exists yet. The [technical specification](docs/superpowers/specs/2026-10-16-famjet-design.md) and [25-task implementation plan](docs/superpowers/plans/2026-10-16-famjet.md) define the remaining reader, baseline, training and fair-comparison gates.

From the repository root, use an existing native CPython 3.13 interpreter:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m pytest
.venv/bin/python -m famjet.doctor --out artifacts/environment
```

The lock contains exact hashes for CPython 3.13 macOS 14+ arm64 wheels and universal wheels, verified on Python 3.13.5. It is not a cross-platform lock. Other interpreters/platforms need a separately resolved lock. The current project environment uses torch 2.14.1, NumPy 2.5.4, SciPy 1.18.1, pytest 9.1.1 and PyYAML 6.0.3. See [wheel and resolver provenance](docs/research/2026-10-16-native-wheels.json) and the [executed gate record](docs/research/2026-10-16-environment-gate.md) for clean-install checks and regeneration commands.

Preparation commands are executable now:

```sh
.venv/bin/python -m famjet.prepare --config configs/data.yaml
.venv/bin/python -m famjet.prepare --config configs/beijing.yaml
```

The synthetic command verifies the saved exploratory inventories (or creates them if absent). Beijing preparation requires the pinned official archive at `data/raw/beijing-uci501.zip`; a missing archive produces an explicit unavailable status and exit 2, preserving any matching sealed manifest. Once the archive arrives, preparation can replace an availability record or reconstruct missing local arrays against the sealed inventory. It builds all-station chronological histories, fits normalization only on training, and seals raw/normalized labels locally. Raw archives and bulk arrays are ignored. Ordinary iteration refuses protected test access; preparation does not train or evaluate a model. See the [Beijing preparation record](docs/research/2026-10-16-beijing-preparation.md) for source attribution, counts and access limits.

Discovery also works without installing dependencies:

```sh
python3 -m famjet.doctor --discover-only --out artifacts/environment
python3 -m unittest discover -s tests -p test_doctor.py -v
```

Discovery records each unavailable command with its reason and UTC time. A restricted sandbox may hide sysctl or MPS; the committed actual-hardware report was run with read-only native hardware access. Serial numbers, hardware UUIDs and battery identifiers are excluded.

The full doctor checks CPU FP64/FP32 and available MPS FP32 against the CPU FP64 oracle, with general MPS fallback and fast math disabled before torch import. Missing MPS does not fail a correct CPU gate and carries no invented timings. Successful API checks do not prove every kernel resides on the GPU; built-in CPU fallback registrations and native profiling require separate scrutiny before accelerated claims. Allocator protective limits remain enabled.

The [smoke configuration](configs/smoke.yaml) specifies two optimizer steps for a future trainer, batch 1, and a conservative additional-allocation ceiling derived from fresh observations. It does not establish a full training envelope. Confirmation fields remain blocking nulls. Initial near-constant normalization failures are [preserved](artifacts/environment/op_support.initial.json); the ordinary bounded fixture passes without widening tolerances. Details and numerical limits are in the executed gate record.

[Progress](PROGRESS.md), [decisions](DECISIONS.md), [audit](AUDIT.md), [supplied evidence](docs/research/2026-10-13-source-record.md) and [read-only source verification](docs/research/2026-10-16-source-verification.md) distinguish planning, source inspection and executed local evidence. Work remains on `main`.


Task 9 containers are `Reservoir(capacity,value_dim,seed)`, `TemporalBuckets(capacity,value_dim)` and `HybridStore(recent_capacity,reservoir_capacity,value_dim,seed)`. Their matching `ReservoirMemory`, `TemporalBucketsMemory` and `HybridMemory` adapters add `key_dim=...` and implement the shared Snapshot protocol. Import reservoir/hybrid from `famjet.memory.reservoir` and buckets from `famjet.memory.buckets`. Each accepts explicit `value_dtype` and `accumulation_dtype` (`float32` or `float64`, both default `float64`); choose these explicitly for fair budget comparisons. Buckets also declare `normalization='independent'|'shared'` (default independent); initial core comparisons must explicitly choose shared, which validates identical masks and packs one count/mask column. Buckets retain sums in accumulation_dtype after input rounding; reservoir/hybrid retain values in value_dtype and use the configured temporary accumulation precision. IDs and tagged timestamp words remain lossless. All array state and metadata is counted; there is no retained RNG object or hidden history cache.

Reservoir diagnostics expose sampling fraction, uncertainty status and zero-sample windows without claiming confidence bounds. Hybrid means use certainty weights for recent rows and inverse inclusion weights for reservoir-only rows, deduplicated by counted observed-write ordinal; this is a finite-sample biased ratio estimator. Bucket means use temporal overlap fractions and per-coordinate counts, with exact point boundaries. Numeric estimates can be valid while factual support is uncertified; `prediction_valid`, `certified_support`, `partial_overlap` and estimated counts distinguish these cases. A merged latest bucket cannot recover its last value and returns unsupported. No approximation bound, training fallback or model advantage is claimed. `TemporalBucketsMemory.bucket_arrays(snapshot)` returns owned copies of the same summary features available to a future learned reader. Policy choices/tuning use development data only; no tuning was performed here. Extreme cancellation and sum-grouping equivalence to the current raw oracle remain a separately assigned Task 17 numerical gate before tuning.

Snapshot evaluation now uses `famjet.eval.budgets.state_ledger`, `model_ledger` and `budget_report`; `famjet.eval.isolation.isolated_read` accepts a full query batch for the packed methods. Jet/bank kernels use `isolated_features` until Task 11 supplies trained TaskModels. The worker receives only approved static schema/weights, numeric state and queries, checks package source identity, and rejects ordinary disk/process/network access during reads. This controls accidental leakage; it is not an OS security boundary against hostile native code or an administrator.

`save_state(path, snapshot)` / `load_state(path, expected_parameter_hash)` in `famjet.eval.state_io` use checksummed, versioned numeric files. Saves atomically replace the primary and retain a validated `.previous` file; corrupt primaries require explicit recovery. Restored snapshots own independent packed CPU allocations: aliases, strides, autograd graphs and devices are not restored. Stream snapshots are separate from full training checkpoints. Ledgers distinguish logical capacity, full Torch backing storage, static tensors and serialized size; opaque external storage and retained training graphs cannot qualify as measured bounded inference.
