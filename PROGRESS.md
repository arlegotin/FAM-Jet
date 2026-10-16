# Progress

**Updated:** 16 October 2026. **Branch:** `main`. **Current scope:** Task 1 accepted; Task 2 versioned contracts implemented and verified, pending controller review.

The [specification](docs/superpowers/specs/2026-10-16-famjet-design.md) and [implementation plan](docs/superpowers/plans/2026-10-16-famjet.md) remain the research contract. The executed WP00 subset now includes dependency-free hardware discovery, a real native wheel hash lock, a project-local environment, lightweight regression tests, CPU/MPS operation and gradient probes, full smoke configuration, and source/dependency provenance. This does not accept later work packages or establish model correctness/performance.

## Executed evidence

- Native CPython 3.13.5 arm64; torch 2.14.1 / NumPy 2.5.4 / SciPy 1.18.1 / pytest 9.1.1 / PyYAML 6.0.3. Both `.venv` and a clean temporary environment installed the same hash lock; core imports/CPU FP64 arithmetic and `pip check` passed.
- Final full test suite: **13 passed**. Final doctor: **72/72 CPU cells** (FP64/FP32) and **36/36 MPS FP32 cells** passed at rtol 1e-5 / atol 1e-6, across tiny, smoke and initial scientific fixtures. MPS is built and available; full native kernel residency is unprofiled.
- [Hardware](artifacts/environment/hardware.json), [operation matrix](artifacts/environment/op_support.json), [initial failed matrix](artifacts/environment/op_support.initial.json), [asset manifest](artifacts/environment/assets.json), [native wheels](docs/research/2026-10-16-native-wheels.json), and [gate record](docs/research/2026-10-16-environment-gate.md) preserve executed evidence. [Source verification](docs/research/2026-10-16-source-verification.md) records metadata/licenses/pins, without downloaded scientific assets or reproduced source results.
- Current machine: M3 Max, 30 GPU cores, 36 GiB unified RAM. Post-probe disk available 45,211,768 KiB (~43.1 GiB); swap used 17,434.69 MiB; pressure tool reports 73% free. AC power; no thermal/performance warning level recorded, not a temperature reading. See timestamped artifacts for transient values.

## Accepted subset and limits

The verified CPU environment and ordinary bounded operation support are ready for controller review. The smoke policy uses batch 1 / four CPU threads, caps a freshly derived envelope at 256 MiB and leaves 25% reserve, producing a 192 MiB additional-allocation ceiling. Full training allocation, sustained throughput/power/thermal behavior, model memory peaks and pilot timing remain uncalibrated. Existing swap use precludes treating installed RAM or Metal recommendation as free training memory.

The initial normalization fixture had almost constant channel values and violated FP32 tolerances on both devices. That report is retained; the ordinary well-spread fixture passes with unchanged tolerances. Near-constant normalization remains an explicit numerical caveat. MPS success supports these API/gradient fixtures, not accelerated scientific claims or bitwise training resume.

No datasets, model weights, generator/model implementation, checkpoints, training runs, protected outputs or measured model results exist. Later task execution checkboxes remain untouched.

## Next gate

Controller review of Task 2, then Task 3 training statistics and target contracts. Before pilot/training or scientific asset ingestion, enforce the remaining numerical, full-training resource, disk-budget, asset/schema/license and baseline gates. Confirmation scientific fields remain null until the pilot freeze.

## Task 2 contract gate — 16 October 2026

Implemented schema-version-1 event/query/episode/snapshot/feature/read/prediction records and the MemoryMethod adapter protocol. Host-side event/query/rate validation rejects nonfinite masked values, malformed padding/observation masks, invalid rates, out-of-order time, integer subtraction overflow, and shared normalization of independently observed channels. Full uint64 public key IDs remain lossless. Validation results are separate from recurrence tensors; no numerical recurrence is implemented.

Strict typed resolved configurations reject unknown/duplicate fields and invalid bounds. Smoke retains all existing fields and pilot-dependent nulls; confirmation/replication require explicit frozen scientific fields and a training envelope. Canonical finite UTF-8 JSON, namespaced SHA-256 seeds, atomic JSON writes, resolved-config saving and separate source/diff, data, parameter, lock and environment identities are implemented.

Red: 53 contract tests failed on the missing named modules. Final full suite: **70 passed, 1 skipped, 2 subtests passed**, using `.venv/bin/python -m pytest -v`. A resolved-JSON numeric parsing failure and a provenance input-aliasing regression were reproduced and corrected. `requirements.lock` and `configs/smoke.yaml` are unchanged. Implementer self-review is complete; independent controller acceptance remains pending. Task 2 does not establish generator, model, serialization/resume, scientific artifact inventories, protected-manifest acceptance or any later numerical/scientific gate.

## Task 3 independent-oracle gate — 16 October 2026

Implemented independent NumPy FP64 impulse sums, raw observed-event arithmetic labels for mean/contrast/latest/change-sign/presence/interval-support and both V32 categorical-fact arms, and versioned training-only target statistics. Half-open age intervals, adjacent recent-minus-older contrast, stable latest ties, full uint64 IDs, exact integer tick comparisons, per-coordinate observation masks and absent support are covered. Unsupported arithmetic labels are NaN internally and null in finite JSON metadata. Binary presence/support labels remain valid even when factual support is false.

Initial targeted red: nine missing-module failures; checker red: one missing-module failure; absent-presence regression red: factual support incorrectly true. Final targeted suite: **13 passed**. Final full `.venv/bin/python -m pytest -v`: **83 passed, 1 skipped, 2 subtests passed**. The existing sandbox MPS RNG test remains skipped. Standalone `.venv/bin/python validation/numerical_checks.py` passes and stores freshly executed native macOS arm64 / Python 3.13.5 / NumPy 2.5.4 FP64 evidence in `artifacts/numerical_checks.json`: recurrent/direct norm errors below 8e-16, normalized log-rate derivative error 2.88e-11, Hermite minimum -0.13502619 near rate 25.5623. No tolerance widening, FP32-model validation, production recurrence, generator or training is claimed; controller review remains pending.

Task 3 round-1 review fix: reproduced accepted mixed float64-query/int64-event tick cancellation (incorrect mean8 versus12 at 2**60). Exact represented-value subtraction now preserves mixed-domain ages with rational arithmetic; full-int timestamps keep integer subtraction. Focused regression/helpers red: 6 failures. Covering oracle/algebra green: **19 passed**; final full suite: **89 passed, 1 skipped, 2 subtests passed**. No numerical tolerances or factual-support contracts changed.

## Task 4 jet-kernel gate — 16 October 2026

Implemented exact old-Z jet updates, bounded chunked terminal sums, structured/raw contractions, safe complete-decay limits, and independently stepped invertible Laguerre coordinates. The focused fixed-writer JetMemory adapter owns timestamp/identity/status snapshots, measures continued first gaps against saved time, advances copies for queries, rejects historical reads, revalidates raw inputs, and counts all logical snapshot tensors plus hash/schema metadata. Core writes support heads; the raw adapter explicitly supports one head and shared vector observations. Independent normalization is rejected rather than silently sharing a denominator. No reader, generator, trainer, serialization, protected result or model performance claim is included.

TDD initial red: **21 failed, 4 passed, 5 sandbox MPS skips**, with missing named jet modules. Regression tests subsequently reproduced fractional snapshot-time rounding in padded integer queries, MPS device-alias handling, epsilon underflow, and an unflagged overflowing read denominator. Wrong-sign and new-Z source mutations each fail both CPU old-Z fixtures. Independent CPU FP64 autograd/direct and central checks cover rates, gates, keys and values; CPU/MPS FP32 gradients and empty-read backward pass at the unchanged ordinary tolerances.

Native MPS testing exposed a silent combined MPS-to-CPU-FP64 conversion error for a tiny rate and normalized-derivative cancellation under 1000x time scaling. Sequential transfer/promotion and centering the derivative numerator fix the preserved failures without widening tolerances. Final full native command with fallback/fast math disabled: **145 passed, 2 subtests passed**, zero skips, exit 0. Compileall and whitespace checks pass. [Executed bounded error envelope](artifacts/jet_checks.json): 42 independent direct-sum comparisons, max absolute errors CPU FP64 4.44e-16, CPU FP32 3.05e-7, native MPS FP32 5.37e-7. Full inputs, versions and original tolerances are retained. These bounded fixtures establish no long-stream stability or throughput claim; controller acceptance remains pending.
