# E3 source review — 24 October 2026

**SPEC: NO**  
**QUALITY: NEEDS FIXES**

Reviewed the adopted E3 brief, including the eligibility, normalized-row storage and chunk-128 amendments; the implementer report; and the supplied package for BASE `3de99bd598e6a18b064aeff980e14a460572183e` through HEAD `764e3d305f29c8a04ed88bf509a2761e1834e8d1`. All six new implementation modules and six test files were reviewed from the diff. Focused integration reads covered existing snapshot deserialization, packed-state validation, E1 model/fit interfaces and core scoring policy behavior. No Git commands, test runs, benchmarks, protected-data access or source changes were performed. This review file is the only authored artifact.

## Critical

None identified.

## Important — acceptance blockers

### I1. Existing cache reuse does not bind the requested population specification

**Locations:** `famjet_poc/study.py:655–663` (`_cache_for`), `study.py:666–702` (probe caller); `famjet_poc/cache.py:153–175` (manifest loading).

`_cache_for` derives the expected cache-manifest digest from the existing file itself and checks only the ordered history IDs against the requested inventory. It never compares each entry's `spec_sha256` with the requested specification. The history-ID format excludes the seed, shape and attempt ceiling. Consequently, invoking `probe_feasibility` in an existing output directory with a valid new manifest that changes a seed can reuse the old episodes, fit them, and write a successful probe carrying the new manifest hash. Internal cache hashes remain valid: they authenticate the old data rather than establish that it is the requested data.

Compare the complete requested ordered `(history_id, canonical_hash(spec))` inventory before reuse, and validate resumed cache ceilings. Bind an existing probe directory to its original manifest or reject incompatible reuse. Add a tiny regression using the same IDs with a different seed/specification; it must reject reuse, not silently certify the old population.

### I2. Resume rejects the diagnostic policies required for partial eligibility

**Locations:** `famjet_poc/study.py:289–294`, `study.py:342–365` (`score_results`); `study.py:720–757`, especially `study.py:733` (`_audit_terminal_entries`).

Scoring intentionally gives ineligible diagnostic rows a separate policy with no primary tasks. Persistence retains those rows and their correct policy hashes. Resume then requires **every** restored row to have the main primary-policy hash. A completed candidate or control containing even one correctly retained unsupported label therefore fails resume with `resumed score row method/policy mismatch`. This contradicts the adopted partial-eligibility and resumable-pipeline contracts.

Validate the primary policy on primary rows and the expected diagnostic policy/inventory on diagnostic rows, while checking the complete full-query inventory. The existing resume test uses only fully eligible rows and does not cover this case. Add a persist/reload/resume regression with both primary and ineligible diagnostic rows.

### I3. Worker input allocation limits and method-specific schemas are not enforced before reconstruction

**Locations:** `famjet_poc/wire.py:230–264`, particularly `wire.py:233` and `wire.py:255`; `wire.py:267–300`; `famjet_poc/worker.py:23`, `worker.py:69–84`, `worker.py:96–101`.

`encode_request` applies `_preflight_arrays` only to statics. It serializes snapshots and queries without applying the caller's `max_array_bytes`. The child then decodes with hard-coded 32 MB array/64 MB frame limits instead of the admitted caller limits. Thus an ordinary packed exact snapshot/query can exceed a smaller caller array ceiling and still execute successfully whenever its result arrays fit that ceiling. For example, the existing 128-event, eight-query K12/V1 shape already has 1,024-byte values and 768-byte query features; a 256-byte caller array ceiling is not enforced on either input. This is a source-derived counterexample, not an executed test.

Separately, the decoder validates only the outer snapshot dictionary and generic tensor byte sizes. It does not precheck the registered payload-key allowlist, method-specific shapes/dtypes or snapshot digest. `_read` allocates every payload tensor through `snapshot_from_record` before checking the snapshot hash; existing method validators reject extra payload fields and invalid layouts only later, during `read`. An extra numeric history/label payload therefore reaches reconstruction before rejection, contrary to the strict boundary contract. The existing generic deserializer explicitly defers method-specific validation (`famjet/eval/state_io.py:84–125`); packed validation occurs in `famjet/memory/exact_store.py:304–337`.

Apply the admitted limits to the entire outgoing request and carry/enforce the same finite limits in the child. Preflight registered snapshot/query schemas, tensor layouts and snapshot hashes before tensor/model reconstruction. Add regressions for a valid request over a smaller caller array limit, an extra snapshot payload field and an otherwise byte-valid wrong tensor layout, with assertions that reconstruction has not occurred.

### I4. Resume renews the same finite wall-time allocation

**Locations:** `famjet_poc/study.py:208–218` (`_admit`), `study.py:758–771` (`run_development`).

Every call to `run_development` starts a new monotonic clock, including resume. The existing journal requires the allocation to remain identical, but no consumed elapsed time is carried into `_admit`. Repeated resumptions can each spend the full `max_wall_seconds` under the same allocation ID; the resulting admission record reports only the most recent invocation. This makes the finite phase allocation renewable without an explicit new allocation.

Persist and charge cumulative consumed wall time across attempts and resume, including validation/reopen work, or require a separately authorized extension/allocation with an explicit relationship to the previous one. Check remaining admission before starting the next fit/batch. Add a fake-clock interrupted/resumed regression proving that previously spent time reduces the remaining allowance.

### I5. Candidate tie-breaking uses JSON wire size instead of active static bytes

**Locations:** `famjet_poc/study.py:368–376` (`select_candidate`), `study.py:535–551` (evaluation cost ledger), `study.py:859–862` (candidate ledger).

The value passed as selection `static_bytes` is `len(canonical_json(statics))`. The active numeric parameter count is separately recorded as `numeric_parameter_bytes` but is not used by selection. Serialized statics include base64 expansion, field names and decimal spellings of hyperparameters. Two same-width candidates with equal active storage can have different wire sizes solely because, for example, `0.01` and `1e-10` have different JSON lengths. Within the adopted loss tolerance, that chooses by formatting before configuration hash, rather than by active static bytes and then hash.

Use the declared complete active-static storage ledger for the selection key and keep serialized request/static bytes as a separate transport measurement. Add a tie regression where active storage is equal but wire lengths differ; the configuration hash must resolve that tie.

## Minor

### M1. The lower training-cache LRU ceiling is accepted but ignored

**Locations:** `famjet_poc/cache.py:89–100`, `cache.py:247–255`.

`attach_training_cache` accepts any positive `limits['lru_bytes']` up to the cache ceiling, but attaches the original cache unchanged. `CacheManifest.put` continues using `cache.lru_bytes`, so a caller requesting a smaller training allowance can exceed it. Enforce the admitted limit, or reject unequal limits if the shared cache must have one fixed ceiling. The current study caller passes equal values, so this affects the public API rather than the default study path.

### M2. Prefix cost records omit the fit and its preparation/serialization work

**Locations:** `famjet_poc/study.py:891–922`; compare candidate accounting at `study.py:834–873`.

Candidate entries record total fit wall time, row persistence, and standalone/amortized views. Prefix entries call `_fit_one` without an encompassing timer and store only `_evaluate` costs. The fit artifact's internal fit duration cannot recover metadata preparation, save/load and validation time. The four diagnostic fits therefore lack the same explicit complete cost attribution. Record those intervals and allocate shared costs for prefix entries too; retain phase-level totals as a separate measurement.

## Requirements satisfied in the inspected source

- The manifest declares the 12 cells, balanced 768/192 inventories, 18 candidates per family and 40 expected production fits. Prefix refits rebuild their own metadata, target statistics and reader/scalers.
- The new files leave historical core, Stage A, lock, B88, E1 and E2 files unchanged in the supplied diff. E1 and E3 source identities remain separately scoped; adding a later module does not automatically enter either explicit source set.
- Training memoization is a subclass boundary; `_fit_one` saves/loads back to the exact E1 base class before development. The worker imports neither cache nor study, rejects training subclasses at export, and reconstructs a reader without its fit-corpus artifact.
- Normal streaming uses at most 128 events per call in `mode='stream'`. Numerical chunk failures trigger singleton replay from the preceding checkpoint, and the earliest failure is recorded. The source tests compare Jet, Bank and fixed controls with singleton streaming, including missing/simultaneous writes; one-event latency has a separate timer.
- Scoring retains full and label-only eligible inventories; core fallback scoring keeps valid failed predictions in loss. Missing primary-task support blocks the panel. Policy storage is normalized losslessly, with core aggregation after restoration.
- Fixed controls use FP64 construction and shape-specific state budgets. Latest LRU is capped at public K. Laguerre state is independently stepped before conversion and reader comparison.
- Worker source/identity checks, process timeout cleanup, an accidental-I/O audit guard and input/static immutability checks are present. These do not cure the preallocation defects above or establish an adversarial sandbox.

## Evidence and cannot-verify obligations

The supplied `full-e3-source-freeze.json/.log` records all six E3 test files, exit 0, **33 passed**, pytest 6.31 s and wrapper 6.604 s, with numerical thread environment values set to 1. The supplied final compile record reports exit 0. These are existing implementer evidence, not independently rerun results. The tests do not establish the cases identified above. In particular, full development/resume execution and the complete benchmark loop are not covered by the reported helper-level timing tests.

No actual production fit study, protected evaluation, production feasibility probe or full timing allocation was available for this review. Runtime, disk-volume feasibility, cache effectiveness, solver workspace, actual candidate outcomes and complete 40-fit/46-panel costs remain unverified. The small stream diagnostic is evidence for the adopted batching mechanism only.

The timing output correctly labels its memory observation as a sum of process **lifetime peaks** at an ACK handshake. It is not simultaneous current whole-process-tree RSS, physical concurrency or inference workspace. `_admit` samples the parent's lifetime peak only. Before a resource-admitted production run, Root still needs the separately specified live whole-tree monitor/accounting; the current proxy cannot establish that obligation.

Historical outcome preservation is supported by the supplied changed-file scope, not an independent Git/history audit. E1/E3 scoped source hashes do not freeze all transitive runtime dependencies; the later full executable freeze remains required. Qualifying these new source classes would not repair or reclassify historical scientific failures.

**Disposition:** fix the Important findings and perform a scoped rereview before E3 source acceptance. Source acceptance, once earned, remains separate from Root's explicit allocation and the eventual feasibility/scientific results.
