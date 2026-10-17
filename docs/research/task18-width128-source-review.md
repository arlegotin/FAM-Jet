# Task18 width128 source review — 2026-10-17

**Spec-compliance: approved. Code quality: approved. No blocking findings in this delta.** Approval covers only the declared CPU64 width128 profile infrastructure; it does not accept numerical/resource execution, authorize a scientific 2048-step pair, or complete Task18.

Reviewed BASE `861da502228d5cf0e2e587643e84af8262062b6a` through HEAD `321b01b4059469375c11f63b021800465b85defa`, reported package `3a54cb7201bd8a0a888dcfa4ee09c9de581fcbab720882815a243f4c389f7bf8`. I read the supplied diff once and the source report, then inspected only the relevant predicate/applicability context, extended tests and existing logs. No suites, models or numerical campaigns were rerun; no source/index/Git mutation occurred.

## Policy and scope

`famjet/analysis/development.py:162` changes only the accepted width tuple: `(64,128)` when the existing learned-profile branch applies and precision is float64, otherwise `(64,)`. The preceding checks at lines 122–158 still require CPU, raw learned-rate fixed-writer Jet/Bank, exact J4/Bank8, generic unranked two-layer reader, bounds `[1/5224,1]`, finite6144 raw cache, configured32768, LR.001/weight_decay0, microbatch1/effective3, 768 fit histories, 96 development histories and the existing fixed profile settings. Width256/arbitrary widths, FP32width128, fixed-rate width128, structured/factorized/ranked alternatives and different state sizes are not admitted by the new predicate.

`execution_shape` at `famjet/analysis/development.py:99` retains the full model and data descriptions, data seed, precision/device and cache applicability fields. The unchanged measured-evidence check at line 172 therefore distinguishes width64 from width128. `tests/test_learned_rate_development.py:69` exercises the public development entry with width64 evidence and a width128 request, installing a model-allocation tripwire; it expects the applicability rejection first. Source/checkpoint/dtype lifecycle code is unchanged by this delta.

This is a calibration permission change. The separate learning path continues to require matching measured evidence; the accompanying amendment explicitly limits the new allocation to profile work and retains independent numerical and resource gates before any broader decision.

## Tests and accounting

`tests/test_learned_rate_development.py:44` tests both families' exact width128 permission and relevant exclusions, actual instantiated parameter counts/bytes, MACs and objective-active upper-bound semantics. Arithmetic is consistent with the existing input97/two-layer/output8/support1 reader: **30,217 reader parameters**, **29,952 MAC/query**, model **30,221/30,225 parameters** or **241,768/241,800 B** for Jet/Bank. The inactive support head and five inactive task-input columns leave reported objective-active upper bounds **29,452/29,456**, not guaranteed realized active counts. No padding or new architecture was introduced.

The trajectory test at line 101 adds float64/width128 while preserving both earlier width64 precision cases. It runs actual fresh, raw-cached, interrupted and resumed training for both families, compares complete model-state and AdamW trees plus consumed order, and requires every learned logit to change. It also checks float64 model/moments, float32 AdamW step counters, timing precision, and malformed wire/moment rejection; rate/reader wire rejection uses a reconstruction tripwire. The bounded fixture's synthetic calibration evidence is explicitly distinguished from production profile authorization.

The round-trip test at line 164 now covers width128 alongside64. It verifies seeded FP32 initialization promoted to64, presented inputs, fit equivalence, export/reconstruction predictions, float64 loss/gradients, actual **9345 B** state and ledger bytes. The larger reader changes parameter storage, not the Jet/Bank state basis or state-byte budget.

Existing logs substantiate the report:

- `artifacts/task18-evidence/width128-policy-red.txt`: **2 expected failures, 1 pass**, 16 deselected, 2.40s. Both failures are the new Jet/Bank acceptance tests at the original width64 guard.
- `artifacts/task18-evidence/width128-policy-green.txt`: **19 passed**, 11.05s.
- `artifacts/task18-evidence/width128-native-cover.txt`: **230 passed**, 37.80s, with no reported skips/failures. The source report records native fallback/fast-math disabled and the covering command.

These are appropriate source-level checks for this narrow change. They do not substitute for the pending represented-rate/reader `1e-12` numerical checks or the actual cold768-fit/96-development/two-update resource profiles. Strict new-source raw preparation remains dependent on both source and numerical approval. Previous width64 scientific evidence and the new width128 source review remain distinct.
