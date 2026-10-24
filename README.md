# FAM-Jet

FAM-Jet explores a simple idea: compress a stream once, then answer different time-window questions from the saved memory. We compare ordinary exponential summaries with summaries that also retain a first temporal moment, measuring both answer quality and the memory and computation they use.

The core generators, memory families, bounded snapshot reads, training/checkpointing and failure-complete scoring are implemented. Tasks 1–17 are accepted; Task18 is assessing CPU development comparisons at 128, 512 and 2048 events.

The latest completed experiment used fixed mathematical readers on 96 development histories, with eight questions per history. All six declared configurations finished: 192 saved states, 576 reader requests and 4608 scored predictions, with no fallback or quarantine. The best configuration in each family was:

| Memory | Normalized loss | Persistent state |
| --- | ---: | ---: |
| Ordinary exponential bank, 8 decays | 0.1918 | 9345 B |
| Jet, 4 decays plus first moments | 0.2804 | 9345 B |

Lower loss is better. The bank led at all three history lengths. **There is no demonstrated practical Jet advantage.** These are selected, exposed development results for one fixed-reader family; they do not establish an information-capacity limit or protected generalization. The [full result and all six configurations](docs/research/task18-kernel-stage-b-panel04-report.md) retain those limits and the raw evidence.

The complete CPU64 experiment ran on the Mac in 10.63 minutes, with about 396 MiB of additional sampled worker memory under a 640 MiB limit. The process monitor and post-return validation passed. No cache purge, unrelated process termination or hardware upgrade was needed. The guarded process overhead is included, so these timings are not optimized deployment latency.

An earlier trained comparison used structured readers. Both models passed their trained numerical checks after 8192 updates, but simple summaries still had much lower error on that same development population:

| Method | Normalized loss | Persistent state |
| --- | ---: | ---: |
| Shared-count temporal buckets | 0.1365 | 9247 B |
| Reservoir sample | 0.2815 | 9297 B |
| Ordinary exponential bank | 0.3888 | 9345 B |
| Jet | 0.3945 | 9345 B |

In that trained comparison, Jet's development loss flattened near the end; Bank improved modestly. Frozen training losses remained high too (Jet 0.4183, Bank 0.4687). Optimization, the reader and temporal compression remain unresolved explanations. Those exploratory CPU64 results used one initialization and a reused training corpus; they are not a convergence or statistical claim. The new fixed reader changes the decoder class and does not establish that the older models converged. Protected evaluation remains closed.

The [completed pair](docs/research/task18-epsilon1em6-learning-results.md) retains all curves, length/regime results, numerical checks and costs. An earlier structured Jet run failed a strict trained gradient check; the [failed result](docs/research/task18-structured-stopped8192-report.md) remains failed. The new pair uses a different numerical smoothing setting and does not repair that historical result. Earlier learned-rate and fixed-basis comparisons remain in the [development inventory](docs/research/task18-development-inventory.json); the learned-rate Bank's observed loss of 0.3871 also remains below the current pair.

The fixed mathematical reader completed its [full numerical diagnostic](docs/research/task18-kernel-stage-a06-report.md): all720 finite reader comparisons and24 fallback-policy checks passed. All696 ordinary source-state comparisons passed too. One extreme signed-cancellation fixture failed across the six configurations and four transforms, so global numerical validation remains **FAILED**. The [independent audit](docs/research/task18-kernel-stage-a06-mathematical-audit.md) preserves that limitation. The completed development experiment describes the ordinary saved states; it does not repair those extreme failures.

The memory hold cleared on21October when a fresh check passed the unchanged admission rule. The diagnostic's sampled worker process-tree peak was about471MiB; no hardware upgrade, process termination or system-setting change was needed. Earlier refused admissions and failed runs remain in the record. The full test ran within its shared time and execution/output limits. Protected evaluation remains closed.

The first [empty launch check](docs/research/task18-kernel-stage-b-binding01-report.md) failed before the PyTorch baseline. Later attempts exposed FP32/FP64 input wiring and a reader-launcher path check. The [input correction](docs/research/task18-kernel-stage-b-input-dtype-source-report.md) and [reader-launcher correction](docs/research/task18-kernel-stage-b-reader-launcher-source-report.md) passed independent review and 67 focused covering tests before fresh qualification and the completed experiment. All failed attempts remain archived; no historical failure was reclassified as success.

Task18 now needs a bounded generic-contracted versus full-state reader-adequacy comparison, with comparable parameter/compute budgets and explicit fitting and convergence criteria. The kernel result is an achievable reference from these states, not an optimal decoder. Broader comparator learning curves, learned writers, resource frontiers, calibrated inference and real transfer remain open.

The [reader qualification check](docs/research/task18-reader-adequacy-v1-checks-run02-report.md) completed numerical validation and six tiny training runs. All six missed the fixed accuracy threshold on a fixture whose answers are provably recoverable from both memories. Larger training is blocked while the reader/optimization issue is investigated. This67-second diagnostic used about382MiB additional sampled process memory; RAM was sufficient. Its training errors are not a new Jet/Bank benchmark.

The [simple controls](docs/research/task18-cpu64-simple9345-summary.json) and [evidence map](docs/research/task18-epsilon1em6-learning-promotion.md) preserve exact provenance. Earlier FP32 results used different scales and state budgets and remain separate. The [clock audit](docs/research/task18-cpu64-clock-accounting.json) distinguishes execution timers from elapsed time during host sleep.

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
