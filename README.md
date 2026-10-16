# FAM-Jet

Query-conditioned exponential-moment memory research: compress a stream once, then answer different temporal questions from the retained state. The primary question is whether exact first temporal moments improve retrieval under measured state and system costs; the recurrence itself is established repeated-pole memory.

Tasks 1–7 are accepted: environment/contracts, independent CPU FP64 oracles, jet and exponential-bank memory kernels, deterministic deferred-query synthetic populations, and observed-event Beijing preparation. Task 8 adds packed exact-history, recent-ring and latest/LRU storage references with Snapshot adapters and is pending review. Arithmetic, data preparation and these storage references work; no trained-model accuracy comparison exists yet. The [technical specification](docs/superpowers/specs/2026-10-16-famjet-design.md) and [25-task implementation plan](docs/superpowers/plans/2026-10-16-famjet.md) define the remaining reader, baseline, training and fair-comparison gates.

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
