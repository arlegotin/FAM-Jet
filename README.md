# FAM-Jet

FAM-Jet explores a simple idea: compress a stream once, then answer different time-window questions from the saved memory. We compare ordinary exponential summaries with summaries that also retain a first temporal moment, measuring both answer quality and the memory and computation they use.

The core generators, memory families, bounded snapshot reads, training/checkpointing and failure-complete scoring are implemented. Tasks1–17 are accepted; Task18 is running actual CPU development comparisons at128/512/2048 events.

The latest comparison learned the decay rates while keeping the writers fixed. After8192 updates, both neural models still had much larger error than a simple bucket summary on the same96 development histories:

| Method | Normalized loss | Persistent state |
| --- | ---: | ---: |
| Shared-count temporal buckets |0.1365|9247B|
| Reservoir sample |0.2815|9297B|
| Ordinary exponential bank |0.3871|9345B|
| Jet |0.3926|9345B|

**There is no demonstrated practical Jet advantage.** Both models still improve with training, and both pass a separate reader test where the saved information is known to be sufficient. That leaves optimization, reader capacity and temporal compression as unresolved explanations for the benchmark gap. These are exploratory CPU64 results with one initialization and a reused training corpus; protected evaluation remains closed.

The [current results](docs/research/task18-cpu64-learning8192-summary.json), [simple controls](docs/research/task18-cpu64-simple9345-summary.json) and [development inventory](docs/research/task18-development-inventory.json) preserve curves, failures, costs and earlier comparisons. Earlier FP32 results used different scales and state budgets and remain separate. Recorded execution timers can exclude host sleep; the [clock audit](docs/research/task18-cpu64-clock-accounting.json) distinguishes them from elapsed clock time.

The [technical specification](docs/superpowers/specs/2026-10-16-famjet-design.md) defines the experiment; [progress and executed evidence](PROGRESS.md) distinguish completed checks from future work.

From the repository root, use an existing native CPython 3.13 interpreter:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m pytest
.venv/bin/python -m famjet.doctor --out artifacts/environment
```

The lock contains exact hashes for CPython 3.13 macOS 14+ arm64 wheels and universal wheels, verified on Python 3.13.5. It is not a cross-platform lock. Other interpreters/platforms need a separately resolved lock. The current project environment uses torch 2.14.1, NumPy 2.5.4, SciPy 1.18.1, pytest 9.1.1 and PyYAML 6.0.3. See [wheel and resolver provenance](docs/research/2026-10-16-native-wheels.json) and the [executed gate record](docs/research/2026-10-16-environment-gate.md) for clean-install checks and regeneration commands.

Preparation and a short pipeline check are executable now:

```sh
.venv/bin/python -m famjet.prepare --config configs/data.yaml
.venv/bin/python -m famjet.prepare --config configs/beijing.yaml
.venv/bin/python -m famjet.run --config configs/smoke.yaml
```

The [polynomial comparator](docs/baseline_adaptations.md) also has an explicit two-step CPU smoke configuration: `.venv/bin/python -m famjet.run --config configs/polynomial-smoke.yaml`. Its single/multiscale Legendre banks use event impulses, expose all signed coefficients to generic readers, and count their declared transition cache. Timescales are fixed; scientific tuning remains ahead.

The finite log-rate HiPPO Zoo comparator has its own [CPU smoke configuration](configs/multiscale-smoke.yaml): `.venv/bin/python -m famjet.run --config configs/multiscale-smoke.yaml`. It retains all eight signed temporal/scale coefficients and supports scale-basis queries. Its [numerical scope](docs/amendments/2026-10-16-multiscale-numerics.md) explicitly excludes a measured slow-scale FP32 long-stream frontier; CPU64 verifies that same finite system. Scientific comparator selection must respect that inventory.

The native GDN2/KDA/gated-delta family has an explicit [CPU smoke configuration](configs/delta-smoke.yaml): `.venv/bin/python -m famjet.run --config configs/delta-smoke.yaml`. It counts the complete q/k/v convolution cache, distinguishes raw and guarded erase policies, and preserves read-only deferred queries. The [adaptation and source-license boundary](docs/baseline_adaptations.md#task15-native-delta-family--17-october-2026) are explicit; small learning controls do not establish scientific convergence.

The smoke command above explicitly uses CPU and two optimizer steps. It prints a new run directory containing resolved configuration, run status, predictions, timing, draw records and full checkpoints. To resume, pass `--resume PATH/TO/checkpoint.pt` with the same config; use a new `--run-dir` if you specify one. `doctor`, `prepare` and `run` all support `--help` without starting work.

The synthetic command verifies the saved exploratory inventories (or creates them if absent). Beijing preparation requires the pinned official archive at `data/raw/beijing-uci501.zip`; a missing archive produces an explicit unavailable status and exit 2, preserving any matching sealed manifest. Once the archive arrives, preparation can replace an availability record or reconstruct missing local arrays against the sealed inventory. It builds all-station chronological histories, fits normalization only on training, and seals raw/normalized labels locally. Raw archives and bulk arrays are ignored. Ordinary iteration refuses protected test access; preparation does not train or evaluate a model. See the [Beijing preparation record](docs/research/2026-10-16-beijing-preparation.md) for source attribution, counts and access limits.

Discovery also works without installing dependencies:

```sh
python3 -m famjet.doctor --discover-only --out artifacts/environment
python3 -m unittest discover -s tests -p test_doctor.py -v
```

Discovery records each unavailable command with its reason and UTC time. A restricted sandbox may hide sysctl or MPS; the committed actual-hardware report was run with read-only native hardware access. Serial numbers, hardware UUIDs and battery identifiers are excluded.

The full doctor checks CPU FP64/FP32 and available MPS FP32 against the CPU FP64 oracle, with general MPS fallback and fast math disabled before torch import. Missing MPS does not fail a correct CPU gate and carries no invented timings. Successful API checks do not prove every kernel resides on the GPU; built-in CPU fallback registrations and native profiling require separate scrutiny before accelerated claims. Allocator protective limits remain enabled.

The [smoke configuration](configs/smoke.yaml) runs a non-scientific pipeline check with batch1 and the existing192MiB additional-allocation ceiling. CPU exact resume and a tiny warm-process native MPS resume comparison pass. A fresh-process MPS attempt exceeded that ceiling and was stopped; this configuration stays on CPU. These checks establish neither a full training envelope nor model quality. Confirmation fields remain blocking nulls. Initial near-constant normalization failures are [preserved](artifacts/environment/op_support.initial.json); the ordinary bounded fixture passes without widening tolerances. Details and numerical limits are in the executed gate record.

[Progress](PROGRESS.md), [decisions](DECISIONS.md), [audit](AUDIT.md), [supplied evidence](docs/research/2026-10-13-source-record.md) and [read-only source verification](docs/research/2026-10-16-source-verification.md) distinguish planning, source inspection and executed local evidence. Work remains on `main`.


Memory adapters share the Snapshot protocol. Atomic snapshot files retain one previous valid copy and bind the writer/rate identity. Full training checkpoints additionally record model and optimizer state, Python/NumPy/torch RNG, sampler position, completed steps and source/config/data identities. Interrupted accumulation restarts from the previous complete optimizer step.

The state ledger counts retained tensors and metadata separately from static parameters, serialized size and physical memory. Isolated reads reconstruct approved model weights and consume only a snapshot and public queries. This controls accidental history leakage; it is not an operating-system security boundary. The specification and progress record document comparator APIs, numerical limits and the remaining evaluation gates.
