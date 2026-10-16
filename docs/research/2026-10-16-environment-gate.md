# Executed local environment gate — 16 October 2026

Task 1/WP00 environment subset, implemented on `main`; controller review remains separate. This record supersedes the preliminary snapshot only for executed observations. No model experiment or scientific result was produced.

## Tested environment and provenance

The existing native `/opt/homebrew/bin/python3.13` is CPython 3.13.5 arm64, Clang 17.0.0 build, built 11 June 2025. Native dependency resolution succeeded for torch 2.14.1, NumPy 2.5.4, SciPy 1.18.1, pytest 9.1.1 and PyYAML 6.0.3. PATH Python 3.14.6 was used for dependency-free tests only; its wheel support was not tested. No interpreter was installed or upgraded.

[requirements.lock](../../requirements.lock) contains generated hashes for 18 actual native/universal wheels, totaling 165,537,733 bytes. It targets CPython 3.13 macOS 14+ arm64, with MarkupSafe/PyYAML wheels compatible from macOS 11. It is not a cross-platform lock. The [native wheel manifest](2026-10-16-native-wheels.json) lists filenames, byte sizes, SHA256 hashes, source indexes and resolver/build versions. [hardware.json](../../artifacts/environment/hardware.json) includes Python build, full `pip freeze`, torch build configuration, dependency versions and all documented MPS flags (unset flags remain null). Runtime pip is 25.1.1; resolver pip-tools is 7.6.2 with build 1.6.1, setuptools 84.0.0 and wheel 0.48.0.

A default `piptools compile --generate-hashes` attempt was stopped after its task-owned temporary cache reached 9.4 GiB while collecting other-platform wheel hashes. Only `/private/tmp/famjet-pip-cache`, created for this task, was removed. No user/shared cache was altered. The corrected native wheelhouse is ~158 MiB. An unsupported `--no-generate-hashes` option attempt and a read-only default pip-tools cache error were corrected by omitting the option and using a task-owned `--cache-dir`. The generated lock contains actual hashes, not fabricated versions or placeholder digests.

Reproduction commands, using an already installed native Python 3.13:

```sh
python3.13 -m venv /private/tmp/famjet-resolver
/private/tmp/famjet-resolver/bin/python -m pip install --cache-dir /private/tmp/famjet-pip-cache pip-tools==7.6.2
/private/tmp/famjet-resolver/bin/python -m piptools compile --allow-unsafe --resolver=backtracking pyproject.toml --output-file /private/tmp/famjet-resolved.txt --pip-args='--only-binary=:all: --no-cache-dir'
/private/tmp/famjet-resolver/bin/python -m pip download --only-binary=:all: --no-cache-dir --dest /private/tmp/famjet-native-wheels -r /private/tmp/famjet-resolved.txt
/private/tmp/famjet-resolver/bin/python -m piptools compile --cache-dir /private/tmp/famjet-piptools-cache --generate-hashes --allow-unsafe --strip-extras --no-index --find-links /private/tmp/famjet-native-wheels --no-emit-find-links --no-emit-index-url pyproject.toml --output-file requirements.lock --pip-args='--only-binary=:all:'
python3.13 -m venv .venv
.venv/bin/python -m pip install --no-index --find-links /private/tmp/famjet-native-wheels --require-hashes -r requirements.lock
```

The first two resolution commands select current versions, so a later regeneration may legitimately select different pins and must be reviewed. To reproduce this exact environment later, install the committed lock. Both `.venv` and a second clean `/private/tmp/famjet-clean-env` installed this lock with `--require-hashes`, then imported NumPy/SciPy/torch/pytest/YAML; CPU FP64 `[1,2].sum()==3` passed. Both `pip check` runs reported `No broken requirements found.` The clean install used the native wheelhouse offline, not a repeated public-index fetch. Temporary environments/wheels are not committed.

## Red/green and operation evidence

Before package implementation or pytest installation:

```sh
python3 -m unittest discover -s tests -p test_doctor.py -v
```

Initial result: 1 assertion failure and 2 import errors, explicitly identifying missing `famjet`; 3 dependency-requiring tests skipped because torch was not installed. After stdlib discovery implementation, discovery tests passed. Subsequent regression tests were observed failing before their fixes: zero-exit thermal errors, battery identifier redaction, resource-policy interface, disabled allocator protection, unsafe rate/MLP workspaces, CPU-to-MPS RNG mutation and missing core dependency metadata. The first unsafe-workspace test mistakenly executed oversized fixtures, was interrupted after 6.65 seconds, then changed to block fixture allocations before repeating the red/green guard test. Final tests remain lightweight and use tiny shapes.

The first installed pytest run had **2 failed / 8 passed**: `test_cpu_matrix_checks_forward_gradients_and_restore` and `test_mps_unavailable_keeps_cpu_path`, both caused by normalization conditioning. The [initial matrix](../../artifacts/environment/op_support.initial.json) retains all failed cells: 3 CPU FP32 normalization cells and 3 MPS FP32 cells failed; all other cells passed. A global state linspace made within-channel variances about 5.04e-6 (V8) and 3.18e-7 (V64), creating cancellation near zero. Max reported CPU absolute error was 2.1173e-5, MPS 8.7550e-6 at the larger shape. Ordinary normalization now varies values across the normalized axis with variance ~0.05; CPU FP32 error in the root-cause fixture was below 7e-8. Tolerances remain rtol 1e-5 / atol 1e-6. This is a fixture-conditioning correction, not a claim that near-constant inputs satisfy those tolerances.

Final verification:

```sh
.venv/bin/python -m pytest tests/test_doctor.py -v
.venv/bin/python -m famjet.doctor --out artifacts/environment
.venv/bin/python -m pytest
.venv/bin/python -m pip check
```

The final full suite reported **13 passed in 2.56s**; doctor returned zero and `pip check` was clean. The targeted suite before the final missing-dependency regression reported 12 passed plus 2 subtests. Native hardware checks ran outside the restricted sandbox; sandbox discovery correctly marked denied sysctl fields unavailable, and MPS can be hidden there.

[The final matrix](../../artifacts/environment/op_support.json) has **72/72 CPU FP64/FP32** and **36/36 MPS FP32** cells passing. Twelve families cover exp/arithmetic/reductions, matmul, einsum, activations, layer/L2 normalization, indexing/gather/masks, two-hidden-layer width128 MLP forward/backward, bounded differentiable log rates, nonreentrant checkpoint backward, short grouped convolution backward, tensor serialization/reload, and Python/NumPy/CPU/MPS RNG replay. Shapes are tiny B1/H1/J4/K16/V8/L8, smoke B1/H1/J4/K16/V8/L128, and an initial larger fixture B1/H1/J8/K32/V64/L2048. These are support fixtures, not retained-state training or implemented scientific model shapes at scale.

Each executed cell has one warmup, synchronized device boundaries for MPS, actual elapsed wall time, finite output/gradient checks and FP64 comparison. Unavailable MPS has reason/null timing and leaves the CPU path intact. Timings include fixture construction, transfers and serialization/backward as applicable; numerical comparisons occur outside the timer. There is no scientific timing benchmark, p50/p95, training forecast, writer/reader timing or fully asynchronous hot-loop claim.

## Resources and numerical limits

Final discovery at 17:29:58 UTC: Apple M3 Max, 30 GPU cores, 14 physical CPU cores, 38,654,705,664 bytes RAM (36 GiB), macOS 26.7.1/build 25G241. MPS built/available and synchronization/current/driver/recommended-memory/RNG APIs exist. Post-probe available disk was 45,211,768 KiB (~43.1 GiB; volume 95% used), swap 17,434.69 MiB used of 18,432 MiB, pressure tool 73% free, AC power. `pmset` recorded no thermal/performance warning level or CPU power status; this is not a measured temperature, sustained-power or thermal-stability result.

Process-lifetime peak RSS was 312,688,640 bytes after CPU probes and 466,354,176 bytes after MPS probes. Maximum sampled MPS tensor allocation was 1,574,400 bytes, sampled driver allocation 11,485,184 bytes, recommendation 30,150,672,384 bytes. Metal samples are observed with outputs live; they are not exact allocator peaks. RSS and driver allocations share unified memory and are not summed as independent pools.

The additional smoke allocation policy uses fresh free+speculative pages (3,206,053,888 bytes at the final observation), bounded further by Metal recommendation minus driver allocation if available, caps the derived envelope at 256 MiB, then leaves 25% reserve: **201,326,592 bytes (192 MiB)**. Micro/effective batch stays 1, CPU threads 4, caches and scientific-asset disk budgets zero. Full training envelope remains null: no model activations/optimizer/checkpoint peaks or sustained pressure/throughput were calibrated. The policy must be rediscovered before later runs. The two configured smoke optimizer steps have not been trained; they are an explicit future trainer budget. Numerical support floor 1e-8 is smoke-only; confirmation calibration remains null.

General MPS fallback and fast math were set to `0` before torch import. High/low allocator ratios remained unset, retaining framework defaults; the doctor refuses zero/negative values. Passing MPS cells certify bounded API/numerical/gradient support only. Built-in CPU fallback registrations can exist even with general fallback disabled; full kernel residency was not profiled. Near-constant normalization and bitwise training resume remain unestablished.

## Official documentation and source access

Installed-major/minor official [PyTorch 2.14 MPS API](https://docs.pytorch.org/docs/2.14/mps.html), [MPS environment documentation](https://docs.pytorch.org/docs/2.14/mps_environment_variables.html), [NumPy 2.5 documentation](https://numpy.org/doc/2.5/) and [PyYAML documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) were accessed. The MPS API page lists synchronization, memory and RNG APIs, also checked against the actual installation. The MPS environment page's table was incompletely exposed by browser extraction; the separate [source-verification record](2026-10-16-source-verification.md) preserves official source-main guidance, explicitly not equivalence with the installed wheel. Installed-version [SciPy 1.18.1 docs](https://docs.scipy.org/doc/scipy-1.18.1/) and [pytest 9.1 docs](https://docs.pytest.org/en/9.1.x/) browser retrieval failed; URLs are recorded without claiming their content was read.

Scientific source verification is metadata/source inspection only. UCI CC BY4.0 metadata and actual archive/schema checks are distinct; HiPPO is pinned MIT source with reproduction pending; GDN2 has noncommercial source restrictions; Time-Local repository reuse permission remains unresolved. No dataset/model downloads, source vendoring, paid/remote compute, system changes, worktree, push or model experiment occurred. These limits do not block the verified CPU environment subset; they constrain later asset, numerical and accelerated claims.
