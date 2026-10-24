# E3 source implementation brief — 24 October 2026

Build source and focused tests; no36-fit allocation, protected evaluation or benchmark is implied. E1 reader source `f787…d8475` and its four files remain immutable. Preserve old53core,15StageA, lock and B88 commitments. E3 has its own explicit file-content digest; adding later inference/report modules must not invalidate E1 models.

## Files and entry points

Add `famjet_poc/{cache,wire,worker,comparators,study,timing}.py`; corresponding focused tests may group cache/study and wire/worker. No package-initializer changes.

```python
# cache.py
prepare_episode_cache(specs, inventory, root, limits) -> CacheManifest
episode_factory(cache, history_ids) -> Callable[[], Iterator[Episode]]
CachedTrainingModel(RidgeMemoryModel)  # training-only subclass
attach_training_cache(model, cache, limits) -> CachedTrainingModel
# wire.py / worker.py
export_statics(model) -> dict
encode_request(statics, pairs, expected_ids, limits) -> bytes
isolated_read_batch(statics, pairs, policy) -> list[ReadResult]
worker_main() -> int  # python -m famjet_poc.worker, framed stdin/stdout
# comparators.py
build_controls(shape, budget, training_statistics, seed) -> dict
laguerre_control(model, events, queries) -> dict
# study.py / timing.py
study_manifest(config) -> dict
probe_feasibility(manifest, out, allocation) -> dict
run_development(manifest, out, allocation) -> dict
score_results(episodes, results, statistics, policy, method) -> list[dict]
benchmark(methods, workloads, policy, out, allocation) -> dict
```

Allocation is a strict finite resource/phase record, not a boolean override. Source tests use separate tiny unit-test populations. Implement executable callables now; Root allocates actual runs later.

## Common data, caching and actual fit APIs

Freeze12cells: lengths128/512/2048×four regimes, Q8. Training64histories/cell=768; development16/cell=192. Construct singleton-length/singleton-regime `PopulationSpec`s with distinct declared history IDs and namespaces. Round-robin training order makes prefixes192/384/768 balanced16/32/64 per cell. Every candidate consumes identical raw examples. Freeze root seeds and IDs before generation; retain sampling failures without replacement or cherry-picking.

Cache real `Episode` tensors plus exact metadata in strict JSON/numeric arrays, no pickle. `episode_factory` returns a fresh iterator and freshly reconstructed episodes, preserving E1 digests/order. No synthetic Episodes substituted for features. Bound disk and LRU separately; initial configurable ceilings1GiB disk/64MiB LRU, subject to measured admission. One episode at a time remains sufficient.

Actual E1 flow is:

```python
factory = episode_factory(cache, ids)
meta = fit_training_metadata(factory)
model = build_model(shape, reader_spec, meta['t_ref'], meta['target_statistics'])
model = attach_training_cache(model, cache, limits)
fit_manifest = make_fit_manifest(model, meta)
fit = fit_reader(model, factory, fit_manifest, chunk_rows=1024)
ref = save_model(model, output_json)
inference_model = load_model(ref.path, ref.sha256)
```

E1 performs metadata replay and two feature passes. Its training-only subclass overrides `encode(mode='terminal')` and `_raw_features` with content-verified memoization; every miss calls exact base writer/feature methods. Keys bind complete data/state/query, E1/E3 source, writer hash, full ReaderSpec, shape, t_ref, time metadata and feature version. Width/ridge aliases require an explicit numerical-independence proof from the pinned base methods and exact fixed-control equality; otherwise use separate keys. Verify cache hits against base calculations on fixed cheap controls. Return owned copies. Never reuse standardized features across fits. Stream-mode encode bypasses cache; changed subset t_ref/writer invalidates keys. After every fit, save/load and require `type(model) is RidgeMemoryModel` before development, reading, worker or timing. No inference feature cache.

Fit artifacts retain unchanged E1 mathematics digests; the STUDY record additionally commits cache/subclass E3 source, config and cache manifest. Test cached/uncached fits and stale-key rejection; never alter E1 provenance to pretend cache code was part of E1. Charge all cache construction/tuning, generation, encoding, feature preparation and I/O; amortized and standalone views allocate shared costs explicitly.

Run18fixed candidates/family: q{8,16}×ridge{1e−10,1e−6,1e−2}×alpha_max{.5,1,2}, alpha_min1/5224, eps1e−6/floor1e−12. Select qualified finite candidates by lowest development loss, ties within1e−12 by active static bytes then config hash. Freeze policy before results. Fit selected configurations again on192/384 prefixes using each prefix's own metadata/scalers/fallback statistics; these four additional fits are diagnostic curves, not reselection. Record every candidate/failure and total40expected fits.

## Controls, encoding and scoring

Use FP64 `PackedHistoryMemory(None,V,'exact',key_dim=K)`, bounded `'recent'`/`'latest_lru'`, `ReservoirMemory` and `TemporalBucketsMemory`. Deterministically select largest positive capacity fitting total persistent9345B(K16/V8) or1665B(K12/V1), including metadata; freeze reservoir seed, shared bucket normalization and all constructor parameters. No supervised fitting exists for arithmetic controls: attach common training priors honestly. Record exact unbounded reference separately, unused budget, complete static bytes and observed maximum state bytes; verify occupancy does not conceal dynamic excess.

Equivalent-coordinate control independently streams `laguerre_step`, then `from_laguerre` recovers Z/H for the same frozen reader; compare predictions/state at original FP64 tolerances. Merely transforming a terminal Jet snapshot is insufficient. Account equivalent metadata and conversion work.

Generate snapshots by real incremental one-event `.encode` calls; retain quarantine triggers. Worker receives no labels. Parent combines returned `ReadResult` with labels in `PredictionBatch` using existing scoring_v2 fields and `score_predictions`/`aggregate_scores`. Freeze common policy, manifest/statistics IDs and expected query inventory. Every valid label receives ordinary or training-prior fallback loss. Unsupported labels remain explicit ineligible rows; infrastructure failures remain incomplete runs rather than fabricated successful predictions. Differential tests compare `score_episode` on tiny cases.

## Worker contract and source separation

One fresh interpreter/request batch, at most64histories, one numerical thread set before imports. Frame carries schema, E1/E3 hashes, reader-statics hash, expected writer hash, request/response IDs, typed static arrays and snapshot/query records only. Reject subclasses and extra history/cache attributes before exporting; never silently discard them. No histories, fit-corpus inventory, labels, cache objects, data filenames or callable/pickle payloads. Strict field allowlists, array shapes/dtypes, byte ceilings and hashes precede allocation; use public numeric `tensor_record`/snapshot serialization. Base model reconstructs from approved statics; simple methods use their registered constructor schemas. Parent first validates saved E1 artifacts with `load_model`.

Check history/query IDs, source identities, writer-versus-reader identities, snapshot hash, time units and deferred-query rules. Validate finite statics; preserve nonfinite prediction evidence as numeric tensor bytes. Verify inputs/statics unchanged after reads. Install disk/network/process audit guard after trusted imports/source checks; no worker imports cache/study modules. This is an audited accidental-leak boundary, not an OS-adversary sandbox. Parent keeps expected inventory, timeout/process cleanup, atomic journal and every failed attempt.

## Timings, tests and risks

Timing uses base methods and actual one-event ingestion, never cached terminal sums. Policy:3warmups,12separated blocks, independently randomized paired order, Q{1,8,64}; separately measure cold subprocess startup, warm in-process query batch, serialization/IPC and complete preprocessing+ingest+Qread/output. Report p50/p95 and block-level uncertainty, not independent inner-repeat confidence. Sample simultaneous parent+child RSS; separate absolute/incremental RSS from logical state, static parameters, inference workspace and serialized bytes. Unknown workspace remains unknown. Compute break-even only with positive denominator and satisfied accuracy requirement.

Required tests: replay/hash/namespace/subset isolation; cache-versus-direct fit equivalence; tampered/unknown wire fields and oversized allocations; worker input immutability and forbidden I/O; batch64/65; fallback/quarantine/incomplete inventory; capacity boundaries; independent Laguerre stream; deterministic selection/failure ledger; fake-clock timing boundaries and invalid break-even. Probe measures one declared small fit plus worker batch before any larger allocation. Principal risks are cache identity, actual E1 repeated hashing/row-loop cost, cold-worker overhead and precise scoring-context parity; source acceptance alone establishes no study feasibility or scientific result.

## Execution and reporting contract

E1 source acceptance docs/research/e2e-task1-source-acceptance.md, actual8case qualification docs/research/e2e-qualification-01-report.md; all passed. E2 famjet_poc/inference.py source accepted; actual calibration running separately, so no writes until Root releases. Preserve E1 four files and inference.py/tests, 53 old core/15StageA/lock/B88. Root will record BASE after release. Read actual public APIs, do not guess signatures. Existing key files famjet_poc/models.py/contracts.py/data.py, famjet/eval/metrics.py, famjet/memory/exact_store.py/buckets.py, existing snapshot wire helpers.

Use subagent-driven implementation: no subagents, no own reviewer. Work current main as explicitly authorized, no worktree/branch/push. No actual study, substantial run or protected access: only focused tiny unit-test populations. Thread env1 before numerical imports. Do not modify requirements.lock, pyproject or historical code. Implement new files and matching tests; reports/evidence under docs/research/e2e-task3-* plus report mirror in SDD e2e-task-3-report.md.

TDD required for important behavior; capture every invocation via raw log and structured argv/exit/elapsed/hash bytes. Keep failed logs. Focused iterations; complete entered E3 test files once before commit, no old suite reruns. Source/tests commit then report/evidence commit. Self-review source. Report complete implementation, exact commands/results/RED-GREEN, owned changed paths, source/config/interfaces, limits, concerns. Chat under15lines status/commits/tests/report path. On NEEDS_CONTEXT ask Root not user. No fake stubs or silent defaults. Root owns independently allocating science and final review.

Runtime APIs must expose allocation/admission records so pipeline can use one command with --resume; expose selected model references and row/statistics/cost manifests with exact inventories. Keep E4 pipeline caller in mind, but avoid implementing E4 protection. Source architecture has already been adopted; raise genuine incompatibilities early.

## Root ruling on label eligibility
Primary numeric targets require observed support, per original specification. Preserve every full-inventory query. Use a separately content-bound label-only eligible numeric inventory with core primary_tasks mean/contrast for scoring/aggregation; retain unsupported labels as explicit ineligible diagnostic rows under their own policy/status. Common eligibility is identical across methods and cannot inspect predictions. Every valid target gets ordinary or fallback loss. Hash full and eligible inventories and report per-history/task counts. Any history lacking either primary task blocks that panel/trial without replacement or redraw. Test partial eligibility, missing-task failure, and valid failed-prediction retention. Core source remains unchanged.
