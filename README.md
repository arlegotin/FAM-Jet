# FAM-Jet

**No overall Jet advantage was demonstrated.** The completed CPU64 fixed-writer study found slightly lower average normalized loss for Jet4 than Bank8 at equal recurrent bytes, but the calibrated confirmation and independent replication intervals both include zero. The prescribed Jet-superiority decision is false in both panels. A simple temporal-buckets control had lower average loss than either fitted memory. The two Beijing transfer modes give mixed, finite-period results; the real-trained Bank is substantially better than Jet on native RMSE.

The [final human report](reports/famjet-poc/final.md), [machine report](reports/famjet-poc/final.json), [charts](reports/famjet-poc/final-charts/primary-effect.svg), [recovery and portable replay proof](docs/research/e2e-report-recovery-actual/index.json), and [original run inventory](docs/research/e2e-run06-execution-record/index.json) give the full result and evidence. The narrow study uses fixed Jet4/Bank8 writers, a qualified coordinate-shared ridge reader, known one-hot keys, observed-event mean/contrast targets, three lengths and four regimes. It does not establish learned-writer, dense-key, generic full-state, all-family or agent-memory superiority.

| Result | Jet4 | Bank8 | Other evidence |
| --- | ---: | ---: | --- |
| Confirmation normalized loss | 0.15649 | 0.19184 | Buckets 0.12862; paired ΔL = Bank − Jet +0.0353537664622, interval [−0.019711263, +0.090418796] |
| Independent replication normalized loss | 0.16638 | 0.20607 | Buckets 0.14074; paired ΔL +0.0396830788643, interval [−0.012747851, +0.092114009] |
| Beijing synthetic-frozen RMSE / MAE (µg/m³) | 130.49 / 99.528 | 1069.5 / 621.09 | Both RMSEs exceed simple baselines near 54–63 |
| Beijing task-adapted RMSE / MAE (µg/m³) | 68.642 / 15.354 | 21.36 / 12.705 | Bank is lower on both metrics |

Confirmation and replication each contain 3,072 histories (256 per each of 12 strata), use separate frozen cohorts, and score all eight entered methods. The Beijing modes share 56 test blocks × 120 queries, with 6,693 eligible and 27 invalid queries. Synthetic inference conditions on the fitted models, preprocessing, training corpus and development selection; it excludes retraining variation. Beijing findings cover the evaluated 2015–17 period; 28-/56-day block ranges are sensitivity checks, not a future-period population guarantee. The report gives per-method ingestion, fit, query, storage and deployment costs, failures and unsupported statuses. Gamma/Laguerre's eighth scored control has `not_measured`/`null` deployment latency.

## Execution and report provenance

Run06 completed the 192-history pilot, both 3,072-history panels, all 36 synthetic cells, 16 real evaluation stages, synthetic and real releases and sealed inference. Its original normal CLI exited **1 at report assembly** because an ordered run-ID comparison rejected the same 288 unique IDs in a different Bank/Jet order. The frozen source, releases, inference, failed report entry and clocks remain unchanged. The explicit `run06-report-order-v1` recovery produced the report separately, with original execution and corrected reporter identities recorded. Root's witnessed recovery passed (68.615 s, peak sampled RSS 1,057,259,520 B); a clean locked-environment replay with the original run, prep and tracked source paths unavailable also passed (70.188 s, peak sampled RSS 1,083,965,440 B). All seven deterministic report files were byte-identical across recovery and replay; only the separate recovery receipt contains volatile metadata. This is **sealed scientific execution plus audited report-only recovery**, not an uninterrupted exit-zero original CLI run.

The original full run and prep remain locally ignored, with [4,813 run files / 2,062,164,087 B plus four prep files / 10,158,074 B](docs/research/e2e-run06-execution-record/index.json). Its 74-file execution source is [archived](docs/research/e2e-run06-execution-source/). The complete local `artifacts/e2e-run06-sealed-bundle.tar.gz` is **285,608,419 B**, SHA-256 `b6de6ba91c234a30bf885f5695b26244358749597bd9f043621f1a44bbd624ae`; [bundle receipt](docs/research/e2e-run06-execution-record/bundle-receipt.json). The bulk bundle and Beijing arrays are ignored and **not in Git**; retrieve them from this local workspace or an explicitly copied, hash-verified bundle. The committed report and proofs retain provenance but do not replace the bulk for report-only replay.

## Install, prepare and replay

Use native **CPython 3.13.5 exactly** on macOS 14+ arm64 from the repository root. The frozen E2 executable identity includes the patch version, and the main wheel lock is platform-specific. Install pinned main dependencies and the editable project; plots use a separate hash-locked Matplotlib environment:

```sh
python3.13 --version  # must print Python 3.13.5
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
python3.13 -m venv .report-venv
.report-venv/bin/python -m pip install --require-hashes -r docs/reporting-requirements.lock
```

Obtain the [official UCI Beijing Multi-Site Air Quality outer ZIP](https://archive.ics.uci.edu/static/public/501/beijing%2Bmulti%2Bsite%2Bair%2Bquality%2Bdata.zip) (Chen, 2017; DOI 10.24432/C5RK5G; CC BY 4.0), place it at `data/raw/beijing-uci501.zip`, and verify the **outer** archive hash. The nested PRSA ZIP alone is not the expected asset. Preparation selects the committed current-v2 manifest and reconstructs missing ignored arrays only when every regenerated inventory hash matches. Do not edit the committed manifest to accommodate a changed local path or timestamp.

```sh
mkdir -p data/raw
curl --fail --location --output data/raw/beijing-uci501.zip 'https://archive.ics.uci.edu/static/public/501/beijing%2Bmulti%2Bsite%2Bair%2Bquality%2Bdata.zip'
printf '%s  %s\n' 'b04da438b2f331ac0ffd45aebdfec0d20d2367feb5f6948c4b1f7ce1191e33c4' 'data/raw/beijing-uci501.zip' | shasum -a 256 -c -
.venv/bin/python -m famjet.prepare --config configs/data.yaml
.venv/bin/python -m famjet.prepare --config configs/beijing.yaml
```

To render the **sealed run06** from the full original run, preparation and archived source under the current guarded reporter, use the fixed v2 report-only migration in a fresh sibling output directory:

```sh
FAMJET_REPORT_PYTHON=.report-venv/bin/python .venv/bin/python scripts/report_run06_recovery_v2.py --run artifacts/e2e-core-run-06 --out artifacts/e2e-run06-replay-new/final.md --archived-source docs/research/e2e-run06-execution-source --compatibility-id run06-report-safety-v2
```

The v2 migration binds the preserved original execution source, the historical v1 reporter and the current guarded reporter through exact file maps. The historical v1 launcher and manifest remain at `scripts/report_run06_recovery.py` and `docs/research/e2e-run06-report-migration.json`; to execute that historical reporter, check out its source commit `4e073f86cfadea7ef2793bf0f1bf91850d8856d7` separately. The recovery verifies the original run, source, model, grant, score, row, cost and clock inventories before rendering. It does not fit, select models, generate histories, create grants or reseal the releases. External prepared Beijing arrays are labeled `verified_inventory_not_rehashed`; replay checks their sealed inventory but does not reopen those array bytes. A fresh full pipeline execution is the separate data-validation step.

For a **fresh execution** of the registered study, the normal CLI is `FAMJET_REPORT_PYTHON=.report-venv/bin/python .venv/bin/python -m famjet_poc run --out artifacts/NEW-RUN`. A new output path reuses the fixed registered seeds and populations; it is a reproduction, **not a new independent confirmation**. The ordinary `report --run RUNROOT --out MARKDOWN` is for runs frozen under the current reporter identity. Do not run or resume the historical run06 pipeline under changed source. An eligible public-stage `run --out RUNROOT --resume` keeps the same source, root and original clocks; failed/begun protected cells are not routine-resumable.

## Historical Task18 archive

The sections below preserve earlier Task18 development evidence and failures. Their historical status statements refer to the checkpoint before the completed narrow run06 study; the new fitted reader does not retroactively change them.

At the earlier Task18 checkpoint, the core generators, memory families, bounded snapshot reads, training/checkpointing and failure-complete scoring were implemented, Tasks 1–17 were accepted, and Task18 was assessing CPU development comparisons at 128, 512 and 2048 events.

That checkpoint's fixed mathematical-reader experiment used 96 development histories, with eight questions per history. All six declared configurations finished: 192 saved states, 576 reader requests and 4608 scored predictions, with no fallback or quarantine. The best configuration in each family was:

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

In that trained comparison, Jet's development loss flattened near the end; Bank improved modestly. Frozen training losses remained high too (Jet 0.4183, Bank 0.4687). Optimization, the reader and temporal compression remain unresolved explanations. Those exploratory CPU64 results used one initialization and a reused training corpus; they are not a convergence or statistical claim. The later ridge reader changes the decoder class and does not establish that the older models converged. Protected evaluation was closed for that experiment.

The [completed pair](docs/research/task18-epsilon1em6-learning-results.md) retains all curves, length/regime results, numerical checks and costs. An earlier structured Jet run failed a strict trained gradient check; the [failed result](docs/research/task18-structured-stopped8192-report.md) remains failed. That pair used a different numerical smoothing setting and did not repair the historical failure. Earlier learned-rate and fixed-basis comparisons remain in the [development inventory](docs/research/task18-development-inventory.json); the learned-rate Bank's observed loss of 0.3871 also remained below that pair.

The fixed mathematical reader completed its [full numerical diagnostic](docs/research/task18-kernel-stage-a06-report.md): all720 finite reader comparisons and24 fallback-policy checks passed. All696 ordinary source-state comparisons passed too. One extreme signed-cancellation fixture failed across the six configurations and four transforms, so global numerical validation remains **FAILED**. The [independent audit](docs/research/task18-kernel-stage-a06-mathematical-audit.md) preserves that limitation. The completed development experiment describes the ordinary saved states; it does not repair those extreme failures.

The memory hold cleared on21October when a fresh check passed the unchanged admission rule. The diagnostic's sampled worker process-tree peak was about471MiB; no hardware upgrade, process termination or system-setting change was needed. Earlier refused admissions and failed runs remain in the record. The full test ran within its shared time and execution/output limits. Protected evaluation was closed at that checkpoint.

The first [empty launch check](docs/research/task18-kernel-stage-b-binding01-report.md) failed before the PyTorch baseline. Later attempts exposed FP32/FP64 input wiring and a reader-launcher path check. The [input correction](docs/research/task18-kernel-stage-b-input-dtype-source-report.md) and [reader-launcher correction](docs/research/task18-kernel-stage-b-reader-launcher-source-report.md) passed independent review and 67 focused covering tests before fresh qualification and the completed experiment. All failed attempts remain archived; no historical failure was reclassified as success.

That historical Task18 work called for a bounded generic-contracted versus full-state reader-adequacy comparison, with comparable parameter/compute budgets and explicit fitting and convergence criteria. The kernel result was an achievable reference from those states, not an optimal decoder. Broader comparator learning curves, learned writers and resource frontiers remain open. The later narrow PoC entered conditional inference and finite-period Beijing transfer only for its adopted fixed-writer scope.

The [reader qualification check](docs/research/task18-reader-adequacy-v1-checks-run02-report.md) completed numerical validation and six tiny training runs. All six missed the fixed accuracy threshold on a fixture whose answers are provably recoverable from both memories. Larger training is blocked while the reader/optimization issue is investigated. This67-second diagnostic used about382MiB additional sampled process memory; RAM was sufficient. Its training errors are not a new Jet/Bank benchmark.

The [simple controls](docs/research/task18-cpu64-simple9345-summary.json) and [evidence map](docs/research/task18-epsilon1em6-learning-promotion.md) preserve exact provenance. Earlier FP32 results used different scales and state budgets and remain separate. The [clock audit](docs/research/task18-cpu64-clock-accounting.json) distinguishes execution timers from elapsed time during host sleep.

The [technical specification](docs/superpowers/specs/2026-10-16-famjet-design.md) defines the experiment; [progress and executed evidence](PROGRESS.md) distinguish completed checks from future work.

Historical core smoke/gate commands, after creating the exact 3.13.5 main environment above:

```sh
FAMJET_REPORT_PYTHON=.report-venv/bin/python .venv/bin/python -m pytest -q --ignore=tests/test_poc_inference.py
.venv/bin/python -m pytest -q tests/test_poc_inference.py
.venv/bin/python -m famjet.doctor --out artifacts/environment
```

The unit suite uses a committed compact public normalization fixture. The two full run06 admission tests are opt-in: with the verified complete ignored run and prep archive present, run `FAMJET_RUN06_INTEGRATION=1 .venv/bin/python -m pytest -q tests/test_poc_report_recovery.py -k 'registered_admission or copied_admission'`. Run inference separately because its process-lifetime 256-MiB RSS check must start without the rest of the suite loaded. The lock contains exact hashes for CPython 3.13 macOS 14+ arm64 wheels and universal wheels, verified on Python 3.13.5. It is not a cross-platform lock. Other interpreters/platforms need a separately resolved lock. The original project environment used torch 2.14.1, NumPy 2.5.4, SciPy 1.18.1, pytest 9.1.1 and PyYAML 6.0.3. See [wheel and resolver provenance](docs/research/2026-10-16-native-wheels.json) and the [executed gate record](docs/research/2026-10-16-environment-gate.md) for clean-install checks and regeneration commands.

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
