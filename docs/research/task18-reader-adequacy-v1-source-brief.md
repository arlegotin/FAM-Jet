# Reader adequacy v1: first source-only component

DESIGN ONLY; all choices proposed for Root adoption. Implement only after independent builder check and dated methodological adoption. This brief specifies the first component; it grants no training or allocation release. The companion design fixes the scientific protocol.

## Placement and exact files

Add `validation/reader_adequacy_v1/{__init__.py,contract.py,reader.py,fixtures.py,README.md}` and `tests/test_reader_adequacy_v1.py`. No new CLI, trainer, process monitor or production registration in this component. No changes to `famjet/`, existing configs, A/B authority/launchers, lock or historical evidence. Later bounded stages add transport/training orchestration only after this component's acceptance; do not clone the old monolithic trainer or relax its closed configuration predicates.

`contract.py` provides immutable schema-v1 `ReaderSpec(family,access,width)` accepting exactly jet/bank × C128/C558/F256; canonical feature-order metadata, analytic parameter/MAC ledger and strict static metadata validation. Reject unknown fields, ranks, learned writers, non-FP64 tensors, nonprimary tasks, unsupported dimensions and inconsistent frozen source/data identities. Document exact full-state axes and contracted order from companion design.

`reader.py` provides `PrimaryReader(spec)` with two biased SiLU hidden layers and eight-output head; buffers feature_mean[D], feature_scale[D], target_mean[2,8], target_scale[2,1]. Counts must equal the companion table, excluding buffers. Methods:

* `fit_feature_statistics(training_rows)` accepts replayable explicitly training-tagged inputs, deterministic ordered reductions and no development rows; zero SD→1, reject nonfinite features. Never refit during read/train updates.
* `features(kernel,snapshot,queries,spec)->FeatureBatch` uses validated existing kernel advancement and contractions, returns D inputs/support/failure. Preserve mask-aware query positions. Compute support outside the learned vector from existing finite contracted normalization and floor. No payload mutation or per-history retained attributes.
* `read(kernel,snapshot,queries)->ReadResult` applies frozen normalization/MLP/inverse target transform; deterministic support float0/1, no logits or learned confidence. Include `numeric_supported`, `prediction_valid`, `failure`; invalid/padded rows cannot become valid through zero-fill.
* `export_static()->dict` and `from_static(dict)` use explicit numeric tensor records, never pickle; strict schema reconstructs exactly and validates statistics/kernel hashes. Export includes weights/buffers/spec/source identities, no snapshot/history. Snapshot serialization stays existing `state_io`.

The adapter is deliberately outside `TaskModel`, whose exact registered-reader checks and97/1177-input schemas remain intact. Use existing numerical memory APIs, `validate_queries`, `FeatureBatch`, `ReadResult`, target-statistics provenance and central metrics; do not duplicate kernel arithmetic except in independent fixtures. Primary compact fields remove five impossible task columns and unused support head. All architectural weights are active candidates, with no dummy padding.

## Fixed pins and read policy

Read base `f75bfdbd795b174f2c132dd77a6edbc26ed88d5c`; Root reports subsequent custody-only HEAD `51d47249708c715e693ee78116992e07a575c513`, all code unchanged. Completed panel source remains `9d44b4acf6eeeda3857485aab4e5328dcd747844`. Preserve famjet53 hash `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`, lock SHA `2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1`, and historical material-manifest SHA `d0669ad0c20a1dc810f0eb6a79b4e9b81f71496cc76a2430e3e91fe833ec49d8`. Verify exact listed bytes, not merely commit ancestry.

Resolve kernel rates/settings from first family entries of panel04's retained `preparation/plan.json` candidate static/rates refs, verifying their declared SHA and writer hash. Select by family, never ridge score; all family kernels must agree bytewise. Target statistics/t_ref come from `validation/kernel_stage_a/frozen-training-metadata.json` (SHA `9ca422cc04f35de1a94bf65a579f37be5122a382cb635c47e7d39d49fa92509c`), common target hash in companion. Original768 fit is `iter_fit_panel` with fixed-raw config data_seed20261017018; confirm target hash/t_ref before feature fitting. Dev uses existing panel entries/seeds/hashes and FP64 promotion semantics, not fresh aliases. No original files are rewritten or resigned.

Learned features exclude every identity/hash/metadata field. Raw/query values use current `move_episode` FP64 conversion, preserving CPU timestamps and bool/integer masks. Mask semantics, unsupported features, underflow and complete-decay follow existing kernels. Invalid numeric output retains failure and is scored by central v2 fallback. Export/reconstruction must not expose calibration claims. Unknown or absent primary target blocks a run rather than deleting its query.

## Tests and independently calculable fixture

Source acceptance requires focused schema/ledger/feature-order/static round-trip tests and source-tree manifest checks; no experiment or fitting. Numerical acceptance separately executes independent feature/output/gradient checks, all16 key selectors, query permutation/delay/absence, signed values, padding/shared missingness, snapshot hash stability, shifted timestamps and1000× unit conversion (rates÷1000,t_ref×1000). Compare terminal chunk32 to streaming on one generated history per12 cells at atol=rtol1e−12; compose existing memory evidence instead of repeating old suites. Gamma control uses L0=Z,L1=Z−2H and recovers H=(L0−L1)/2 before unchanged features/reader. Verify structured diagnostic ratios/derivatives independently; do not train an extra structured arm.

Fixture: four histories, all16 keys, independent eight-vectors at timestamps0 and2, T=2; values from CPU FP64 Uniform[−1,1], seed2026102401, ordered history/time/key/value. All values observed, unit gates, stable event IDs by time/key. Ask each key mean windows[0,1),[2,3) and contrast[0,2),[0,1.5), 256 rows total; oracle yields recent/old vectors and recent-minus-old contrasts. Use seed-local torch Generator, not process RNG side effects. Bank's first/last poles invert the two age coefficients; Jet Z/H at its final pole also recover both vectors. Verify explicit two-by-two reconstruction against event oracle at1e−12. This proves fixture information sufficiency, not model fit.

Separate tiny-fit allocation: all six readers, independently reset seed2026102402, fixture-only feature/target statistics, AdamW LR.003/betas(.9,.999)/eps1e−8/wd0/clip1, batch64 cyclic, at most4096 updates each. Require normalized training MSE≤1e−4 separately per task and key, finite nonzero input/output-layer gradients, and changed predictions when selecting unequal-valued keys. No retry/sweep; failure blocks development. Fixture preprocessing/checkpoints never enter development fitting.

## Sequencing

Root adopts → source implementation/focused tests/independent review → separately bounded numerical and tiny-fit acceptance → measured feasibility → source-bound development allocation. Later orchestration must enforce clean-worker inference, exact-resume identities, fresh draws, failure-complete scoring and ceilings already specified. No old A/native/calibration run is part of these gates. Source acceptance alone does not mean training, adequacy, convergence or Task18 completion.
