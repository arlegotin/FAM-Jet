# E6 coordinate diagnostic source amendment

25 October 2026. **Source work complete; HOLD for fresh independent review.** Source/tests/resource commit: `9b4dc7f8`. Base: `7547deac07b13f8f90aecbb1db3c7279e59f5692`. This implements the [approved prospective design](../superpowers/specs/2026-10-25-coordinate-diagnostic-design.md) and [short plan](../superpowers/plans/2026-10-25-coordinate-diagnostic.md). It does not claim completion of the scientific PoC or authorize migration of the stopped run.

The strict default remains unchanged at `atol=rtol=1e-12`. The explicit diagnostic mode returns a prediction-only disagreement as `FAILED`, while state and all five reader-mask checks remain fatal. The complete audit now follows the control through E3, E4, copied E5 replay, and machine/Markdown reports. The final focused run passed **84 tests in 18.06 seconds** (18.34038179199706 seconds including process startup); compilation and whitespace checks passed.

## Interfaces and unchanged science

`comparators.laguerre_control(model, events, queries, *, diagnostic_mode=False)` retains its three positional arguments and old result fields. The default still raises `ArithmeticError` for the cancellation fixture. With `diagnostic_mode=True`, both Z/H tensors must be finite and pass the original state tolerance, and `finite`, `support`, `failure`, `prediction_valid`, and `numeric_supported` masks must match exactly. Prediction-only failure may return; there is no replacement passing tolerance. Matching ordinary unsupported/fallback reads retain full frozen-prior loss and the full query inventory.

The result adds `coordinate_diagnostics`, keyed by history, and `diagnostic_seconds`. Each diagnostic has schema 2 and policy `fp64_coordinate_diagnostic_v2`, original tolerances, history identity, unchanged numeric-model identity, query IDs/count, value dimension, total/evaluated scalar counts, failed prediction query/scalar counts, strict prediction `PASSED`/`FAILED`, explicit two-state/five-mask checks, separate Z/H absolute/scaled errors, and maximum state/prediction absolute/scaled deltas. The scaled denominator remains `1e-12 + 1e-12 * abs(right)`, preserving the old comparator orientation. A matching fallback with zero finite predictions is recorded with zero evaluated scalars and scored normally; its vacuous finite-read criterion does not imply informative equivalence.

`coordinate_model_sha256(model)` binds shape, reader spec, reference time, writer identity (including rates), target statistics, coefficients and feature/query scalers. It supports the existing unfitted unit comparator as well as fitted deployment readers. It does not change any numeric model value.

`study._evaluate(..., equivalent=True)` explicitly requests diagnostic execution, preserves the per-history record in the existing content-hashed `stream_audits`, and records the model identity and a complete diagnostic summary in costs. Equivalent histories cannot overwrite an earlier audit. The existing isolated worker still reads the recovered snapshot and scores all queries. Per-history coordinate, conversion and diagnostic durations are retained; stream/evaluation costs include diagnostic work and final audit validation. Transfer reference-validation cost includes all three measured comparator components and retains the existing warning that it is not deployable ingestion latency.

`validate_coordinate_audits(costs, rows, *, model_numeric_sha256=None, require_summary=True)` is the shared pure validator. It checks audit hash, exact history/query coverage, duplicate query IDs, model/policy identity, original tolerances, true boolean state/mask checks, nonnegative finite maxima, state-max consistency and original state tolerance, failure-count/status consistency, dimension/scalar closure, and equality of the finite count to the saved raw predictions. It recomputes the summary and rejects missing or altered summaries. Only the E3 producer uses `require_summary=False` while creating that summary. Resume validation checks the same contract for measured Laguerre entries.

Selected real pre-test references use schema 2, explicit `diagnostic_complete` status, and policy/model identities. E4 retains its exact four-history × 120-query inventory, row method/manifest/target-semantic checks, then loads the saved selected K12 Jet and binds the audit identity to its actual numeric contents. A completed diagnostic reference can retain strict read `FAILED`; it is never relabeled simply `passed`. Existing selected model manifest commitments and fit/source/data/cache/guard closures remain intact.

E5's selected-reference adapter resolves the selected model and row paths only in an in-memory copy. It returns the original reference, never rewrites original JSON, and retains the existing temporary-derived-probe validation rule. Development and stress replay validate coordinate costs against saved rows. The three-line `protected.py` addition is necessary because the shared `validate_scored_receipt` is the admission boundary used by both protected synthetic and real releases: without it those releases could ignore missing or forged coordinate audits. All pre-existing count-sidecar, label, score-policy, source, grant, model, resource and row checks still execute before that additional validation. `pipeline.py` was not changed.

Machine JSON adds a `coordinate_diagnostics` section collecting summaries for development, synthetic panels, stress, selected real reference, and both real modes. Markdown renders history/query coverage, strict failed histories/queries/scalars, strict-read status, state/mask status and absolute/scaled maxima for each receipt scope. It explicitly says strict FP64 read equivalence is not established for failed criteria. Current-run coordinate evaluation expenditure is reported separately; full current-run fit/cache/worker/stage costs remain in their existing receipts.

Primary Jet/Bank writers, FP64 state, models, fit/reader design, selection, candidate grid, scientific populations/seeds, inference/calibration, metrics and fallback rules were not changed. There is no higher-precision engine, cache migration, new deadline CLI, hardcoded failed-run runtime path, retuning, or capacity/novelty/agent/all-family superiority claim.

## Source identities and prospective resources

[Compatibility record](e2e-coordinate-source-compatibility.json) retains the entire previous resource policy, historical probe references, old E3 pin and per-module baseline/current byte identities. It is explicitly pending independent review.

- E1 remains `f78761891876540011e577293e31a89c7661ef66adbb522d2cbcd36c331d8475`.
- E2 remains `5cdbae0a61810a0f9d509ed1d462530d708439021f8f9fc81ce04fd12f39bfb4`.
- E3 becomes `c88b38987ba460a77d783bef32cfc46e9fc2246cdb91fbfc9167a28b0b50cb82`; only `comparators.py` and `study.py` changed within E3's explicit source set.
- The transfer evaluator and [prospective resource policy](e2e-development-resource-policy.json) pin that exact E3 identity.
- New allocation policy ID: `e2e-coordinate-diagnostic-development-v2`; prospective K16 stage ceiling **3600 seconds**, RSS **1610612736 bytes**, disk **2147483648 bytes**.

The 3600-second ceiling uses the observed 1728.763838625-second partial stage plus headroom for the previously unmeasured full coordinate audit. The old 2400-second allocation remains closed. Fresh source-matched CLI probes and a new run root are required. The original overall six-hour deadline remains the first witness's UTC start plus 21600 seconds; Root supplies only the remaining time through its external witness. No source change resets that clock or adopts old E3 caches.

Original actual run01 remains **FAILED, stopped before protected access**, elapsed **1728.763838625 seconds**, observed current RSS **848740352 bytes**. Its [independent conditioning diagnosis](e2e-laguerre-actual-diagnostic-report.md) remains prior work, not an all-history bound. This task did not run/resume it, open Beijing test arrays, generate protected populations, fit the actual grid, recalibrate, or conduct an actual benchmark. The original 1245-file/348930903-byte run inventory, diagnostic inputs, and old evidence paths were not edited. Root retains responsibility for its independent byte-inventory check; this report does not substitute a Git diff for verification of ignored run files.

## Verification and retained failures

The new cohesive test file uses a reproducible 128-event public synthetic history with timestamps/query times and ages scaled by 1e-6. No ignored run directory or saved actual-model fixture is required. It checks strict failure, returned failed diagnostic, unchanged model identity, ordinary strict pass, and hard failure after injected state or each of five mask defects. Its E3 tests fit a small public unit reader, execute the actual isolated worker, preserve all eight scored queries, reject corrupt audits, and verify all-eight-query ordinary fallback loss. The E4/E5 fixture uses the actual model serializer and E3 producer to create four 120-query histories, checks copied replay after removing the original directory, and rejects missing/incomplete diagnostics, forged status, missing summary and model mismatch. The report test exposes failed criteria in six representative phase/mode locations. Existing producer-shaped replay tests now use that complete producer fixture; no tamper check was weakened. Existing transfer coverage additionally verifies full comparator diagnostic-cost accounting.

Final covering command:

```sh
.venv/bin/python -m pytest -q tests/test_poc_coordinate_diagnostic.py tests/test_poc_e3_comparators.py tests/test_poc_e3_study.py tests/test_poc_transfer.py tests/test_poc_report_inputs.py tests/test_poc_report.py tests/test_poc_report_scientific.py tests/test_poc_protected.py
```

[Final raw log](e2e-coordinate-source-evidence/green-final-02.log) and [exact invocation receipt](e2e-coordinate-source-evidence/green-final-02.json): exit 0, 84 passed; log 180 bytes, SHA-256 `72d093e748bd77dc9c408069237b062346a6e4651097633f05ba73069aa194b5`. [Final compile receipt](e2e-coordinate-source-evidence/compile-final-02.json) records all six changed modules and three changed test files; exit 0. [Whitespace receipt](e2e-coordinate-source-evidence/diff-check-final.json): exit 0. No full legacy suite or E2 calibration rerun was performed, following the explicit bounded verification scope.

Every retained command has exact argv, exit code, wall duration, raw combined log bytes and SHA-256 in its adjacent JSON. The evidence directory includes the capture runner and a read-only verifier. [Final verification log](e2e-coordinate-source-evidence/verification-final.log) verifies every preceding receipt, current E1/E2/E3 identities, policy/evaluator pin, per-module baseline bytes, and unchanged core/configs/locks/pipeline.

All failed attempts remain visible: `red-01` included an invalid frozen-Episode assignment; `red-02` exposed use of fitted-only wire export on an unfitted comparator fixture. Both fixture mistakes were corrected, not suppressed. `red-03` records the missing diagnostic API/audit validator; `red-04` the old selected-reference status rejection; `red-05` the absent report interface; `red-06` exposes integer `1` masquerading as a true boolean audit check and motivated strict boolean validation; `red-07` exposes omitted diagnostic timing from the transfer cost sum. All seven raw logs and receipts are preserved. Intermediate green results (9, 10, 75, 20 and 84 tests) and both compile attempts are retained rather than overwritten. The initial Git staging/commit command encountered the read-only `.git` sandbox; authorized escalation then staged and committed the reviewed file list successfully, with no partial source mutation from the failed Git command.

## Limits and handoff

This source task establishes the explicit diagnostic contract and focused artifact validation, not successful FP64 coordinate equivalence. Later public, stress, protected or real histories may still fail a mandatory state/mask check. Such failures must stop execution; no test or report allows them through. The observed Decimal case supplies no universal bound. The selected-reference validator checks immutable numeric provenance and consistent recorded diagnostics, not a fresh scientific reevaluation during report replay.

**HOLD:** Root should read this report, verify evidence and unchanged prior run bytes, and dispatch a fresh independent spec/quality review. Root owns any bounded public qualification, the new source-matched full CLI under the remaining original overall clock, old/new selected numeric-artifact comparison, first protected access after freeze, deterministic/copied final replay, and whole-branch final review. No reviewer was spawned by this source owner.

## Fix round 1 — independent model binding and empty-comparison consistency

25 October 2026. Fix base `254424b0f91f7517af503ca04ae9a49f5bc8a00f`; source/tests/resource commit **`19d9f8e4727451fc8d7a8d2beba50d3f181e8194`**. **R1 and R2 addressed; HOLD for scoped independent rereview.** The preceding section is retained as the original implementation record. Its optional-identity validator interface and completeness claim are superseded by this section: independent review found that most consumers verified only internal digest consistency, and the original source gate did not pass.

The review was read in full from `.superpowers/sdd/2026-10-16-famjet/e2e-coordinate-source-review.md`. R1's coherent wrong-model substitution was reproduced at development resume. R2's zero-finite-scalar record with a scaled maximum of 0.5 was also reproduced. Both failed-regression logs are retained. No actual public preflight, full study, protected generation, Beijing array access, or recalibration was executed during this fix.

### R1: required independent checkpoint relationship

`validate_coordinate_audits(costs, rows, *, expected_model, require_summary=True)` now requires an independently supplied `RidgeMemoryModel` Jet object. There is no optional digest argument and no omission path that reduces admission to internal consistency. The validator derives the expected numeric digest itself and requires every history's value dimension to equal that model's value dimension. A `None` model is rejected. Existing counts, masks, original tolerances, maxima, audit-hash and summary checks are retained.

`load_coordinate_model(reference, expected_shape=None, *, resolve=Path)` loads the selected checkpoint through the existing content-verifying model loader, requires Jet family and, where the phase fixes it, the expected shape. Portable callers supply `ArtifactPaths.resolve`; serialized paths and JSON remain untouched. This helper obtains no model identity from costs or diagnostic fields.

Every production admission now supplies the independent model:

| Consumer | Independent authority and additional closure |
| --- | --- |
| E3 equivalent producer | The actual evaluated Jet object; its model bytes are unchanged. |
| E3 development resume | Recompute the Jet winner with existing `select_candidate`, require the journal's selected reference to agree, enforce local allocation path, and load the winner's checkpoint. Selection behavior is unchanged; this is verification of the saved selection. |
| E4 synthetic release sealing | Load the freeze's selected Jet, verify the selected checkpoint-pair commitment, require K16/V8 for the study profile and the cell population shape at the receipt boundary. |
| E4 real release sealing | Load the selected K12/V1 Jet from the independently bound receipt mode; pass it to normalized and native-row receipt validation. |
| E4 real release reading | Resolve the verified frozen mode and its K12/V1 Jet before validating the saved coordinate receipt. |
| Selected real pre-test reference | Retain its existing actual selected-model manifest/numeric check and exact four-by-120 inventory; additionally bind value dimension through the required model object. |
| E5 development replay | Require the journal's selected Jet reference to equal the freeze's shape-specific reference; resolve/load that K16/V8 or K12/V1 checkpoint before audit validation. |
| E5 stress replay | Pass the existing verified freeze into `_verify_stress`, then resolve/load its selected K16/V8 Jet. |
| E5 synthetic release replay | Resolve/load the freeze's selected Jet and require the declared population shape before shared receipt admission. |
| E5 real release replay | Resolve/load each bound mode's K12/V1 Jet and pass it to both normalized and native validation. |

`validate_scored_receipt` has an additional keyword `coordinate_model`; it remains optional for other methods but is mandatory in effect for any Laguerre receipt or row. All original policy/count/label/source/grant/model/resource/row checks still execute. A unit release containing the coordinate control must now freeze selected checkpoint references and their pair commitment too; the existing producer-shaped unit test was updated to provide that authority, rather than weakening the validator. It also now attempts a coherent wrong-model substitution through the actual `seal_release` entry point and requires rejection.

No `pipeline.py` edit was needed: E5 already has the independently verified freeze and can pass it to stress validation. No report metric, scoring formula, model parameter, candidate, seed, fallback, inference setting, or numerical acceptance threshold changed.

### R2: impossible empty-comparison maxima

When `evaluated_scalar_count == 0`, both `max_prediction_absolute_error` and `max_prediction_scaled_error` must be exactly zero. The producer already emits this pair. A forged 0.5 scaled maximum is rejected even after recomputing the audit hash and matching summary. No wider numerical acceptance rule was added.

The all-fallback regression also coherently changes value dimension, total scalar count, summary and raw-prediction lengths; the independently selected model's value dimension rejects it. Matching ordinary fallback itself remains accepted and scored for the full inventory.

### Fix verification and retained attempts

[Fix-round evidence directory](e2e-coordinate-source-evidence/fix-round1/) contains exact argv, exit code, wall duration, raw combined output bytes and SHA-256 for every command. All new files are separate from the original evidence.

- `red-01`: exit 1, reproduced acceptance of scaled maximum 0.5 with zero evaluated scalars.
- `red-02`: exit 1, reproduced development-resume acceptance of a coherent wrong numeric digest. Three shared synthetic/real receipt cases also failed because the independent-model keyword was not yet implemented.
- `green-01`: exit 0, 15 focused tests passed in 13.03 seconds.
- `integration-01`: exit 0, copied K16/K12 development and stress replay passed, including coherent substituted digests with recomputed journal/stress hashes and unchanged frozen checkpoint references, after removal of the original run directory.
- `covering-01`: exit 1, 88 passed and one failure. The existing all-control unit release had not frozen its selected checkpoint references; the new required independent binding rejected it. The fixture now freezes those references and checks a seal-level coherent substitution. The failure and traceback remain in the raw log.
- **`covering-02`: exit 0, 89 passed in 29.42 seconds**, 29.713821750003262 seconds including process startup. Raw log: 180 bytes, SHA-256 `60c11aa55c8bd60f2cc34dd939c9657928a8955ebfe9fc91b7fac8e9ae6d75b2`.
- `compile-final`: exit 0, all five changed production modules and both changed test files compiled; empty output.
- `diff-check`: exit 0, `git diff --check`; empty output.
- `verification-final`: exit 0, source/policy preservation and caller inventory verified; 2563 output bytes, SHA-256 `316bfd1108a02611720dc3169e225538bda11ed2186721bcda6e2255631d610d`.

The exact final covering command is unchanged in scope:

```sh
.venv/bin/python -m pytest -q tests/test_poc_coordinate_diagnostic.py tests/test_poc_e3_comparators.py tests/test_poc_e3_study.py tests/test_poc_transfer.py tests/test_poc_report_inputs.py tests/test_poc_report.py tests/test_poc_report_scientific.py tests/test_poc_protected.py
```

The new tests use actual small public-unit fitted/serialized models, E3 worker-scored rows, and producer-shaped policy/count/audit artifacts. They cover coherent digest substitution at E3 resume, shared synthetic and both real-mode admission, actual synthetic sealing, and portable development/stress replay. The complete development ledger fixture reuses unit-produced row/model evidence across fixture entries; it does not run a scientific 36-candidate grid or claim those fixture losses are scientific results. Real admission coverage tests the shared receipt boundary with each mode's independently loaded model; a full real 56-block release was not manufactured or executed. Existing complete selected-reference portable checks remain in the covering suite.

[Read-only fix verifier](e2e-coordinate-source-evidence/fix-round1/verify_fix.py) checks all **36 original evidence files / 66722 bytes** against the original evidence index, verifies that index against the fix base, and checks every new command receipt. Thus the original 17 invocations, including all seven RED attempts, remain byte-identical. It also records all 13 production audit/shared-receipt call sites with their explicit independent-model arguments. This source inventory complements the runtime regressions; it is not a substitute for them.

### Current identity and remaining gate

Current E3 is **`e25b63ee60f51ed511fc7af5d3f713c9a404301f51178283c0a2066d940e68ba`**. Transfer and resource policy pin it. The compatibility record retains the previous `c88b3898…` source as revision history and retains the original `bbd4772c…` historical policy/probe facts. E1 remains `f78761891876540011e577293e31a89c7661ef66adbb522d2cbcd36c331d8475`; E2 remains `5cdbae0a61810a0f9d509ed1d462530d708439021f8f9fc81ce04fd12f39bfb4`. The verifier confirms core/E1/E2/worker/wire/cache/timing/pipeline/configs/locks unchanged from the fix base.

The prospective 3600-second stage cap, original absolute six-hour deadline ending 03:41:39Z, and Root's remaining-time witness are unchanged. Original run01 remains failed and closed; its 1245-file inventory was not touched. This task did not independently reread those ignored run files; Root retains the byte check. The report's SDD mirror is updated byte-for-byte.

**HOLD for scoped rereview of R1/R2 and their integration.** Root owns public preflight and all actual scientific execution after approval. The patch does not predict whether later mandatory state/mask checks will pass and does not turn strict-read diagnostic failures into equivalence success.

## Runtime fix round 2 — machine policy for the mandatory fresh probe

25 October 2026. Base `eb6d33eac3f3995208c7453fa4eb0e51fbcb7df7`; source/tests/metadata commit **`7af7106e36c1f51c4e3d2547ef08baf33bfa5a24`**. **Narrow fix complete; HOLD for independent review.** R1/R2 had been closed by Root's intervening review. This is a separate runtime integration defect, not a numerical-control amendment.

Root's actual fresh main02 invocation ended with exit 1 after **14.117138125 seconds**, observed current RSS **297648128 bytes**, before the fresh probe, fits or protected access. The traceback in `artifacts/e2e-core-run-02-prep/stderr.log` was read without changing that file. It points to `k16_probe_allocation`: the helper compared `probe_ref_status` to the exact old sentence `historical_pre_worker_fix; requires fresh matching actual CLI probe`. The approved policy now describes the historical pre-coordinate-diagnostic source. The E3 identities matched; the prose comparison was the failing predicate. No guard exhaustion was reported by Root.

Only `pipeline.py::k16_probe_allocation`, `tests/test_poc_pipeline.py`, the resource policy, and compatibility metadata changed. The helper now requires **`policy.get('fresh_probe_required') is True`**. Missing, `None`, `False`, integer `1`, and string values are rejected. `probe_ref_status` remains unchanged descriptive historical provenance and is no longer interpreted as authorization. Arbitrary descriptive prose works when the strict boolean is true and the existing source/manifest checks pass.

The repository resource policy adds exactly one field, `fresh_probe_required: true`; all previous fields remain equal to the base policy, including current E3 identity, phase, allocation identifier, 3600-second development cap, RSS/disk limits, historical references and clock treatment. The helper still returns the same fresh current-manifest probe allocation: phase `probe`, ID `e4-k16-current-source-probe-v1`, 120 seconds, 134217728 disk bytes, 1610612736 RSS bytes. It does not return or adopt the old probe reference. The existing fresh-probe execution and first-attempt deadline code are unchanged.

The new integration test loads the **actual repository study configuration and resource policy** and calls the real `study_manifest`. Before the fix, it confirmed equal E3 pins and then reproduced the same allocation failure. It now verifies the complete unchanged allocation against that manifest. Additional tests exercise arbitrary provenance text with the true flag, continued source-mismatch rejection, and rejection of absent/non-boolean/false flags even when the old provenance sentence is present. The existing historical-receipt test fixture now provides the mandatory boolean. These tests prepare metadata only; no actual probe, scientific fit or protected array access occurs.

[Round-2 raw evidence](e2e-coordinate-source-evidence/fix-round2/) preserves every command's exact argv, exit, wall duration, output byte count and SHA-256:

| Record | Command / result |
| --- | --- |
| `red-01` | `.venv/bin/python -m pytest -q tests/test_poc_pipeline.py -k 'repository_study_metadata or fresh_probe_policy or fresh_probe_requires'`; exit 1; all seven new cases failed as expected, including the actual-metadata integration case. Log 8828 bytes, SHA-256 `2db19e111163e2d2c7a434facb645a2354dd8c588756453cf5a5268dc2068af6`. |
| `green-01` | `.venv/bin/python -m pytest -q tests/test_poc_pipeline.py`; exit 0; **23 passed in 1.47 seconds**, 1.7119133329979377 seconds including startup. Log 99 bytes, SHA-256 `315717575bf8cf62f39c2de0239110d36a9dd3d6cc0aea4e7998c4225c7e28b0`. |
| `compile-final` | `.venv/bin/python -m py_compile famjet_poc/pipeline.py tests/test_poc_pipeline.py`; exit 0; empty output. |
| `diff-check` | `git diff --check`; exit 0; empty output. |
| `verification-final` | Read-only `verify_fix.py`; exit 0; log 512 bytes, SHA-256 `1f41b19f8698bbb16c235605424a3fae16028c03308e9e3a2db50c7eca172bfd`. |

The verifier confirms the 56 indexed files from the original and round-1 evidence are byte-identical, with both old indexes unchanged. It verifies that the resource policy only adds the true flag, that the pipeline AST outside `k16_probe_allocation` is unchanged, and that every other production module, core, configuration and lock is unchanged from this round's base. E1 remains `f78761891876540011e577293e31a89c7661ef66adbb522d2cbcd36c331d8475`; E2 remains `5cdbae0a61810a0f9d509ed1d462530d708439021f8f9fc81ce04fd12f39bfb4`; **E3 remains `e25b63ee60f51ed511fc7af5d3f713c9a404301f51178283c0a2066d940e68ba`**. The full executable identity changes because pipeline code changed; the E3 numerical source does not.

No 84/89/156-test scope or E2 suite was rerun. No public preflight or actual probe was rerun. Root separately reported that its already completed 192-history public qualification passed all state/mask checks in approximately 47 seconds while retaining 16 failed strict prediction histories; that prior result is unchanged and was not reclassified as strict equivalence. This task does not independently certify that runtime evidence.

Original run01's 1245 files, the new failed run02, and the completed public-preflight artifacts remain untouched. Root retains their independent byte-inventory checks; the source verifier does not claim to have rehashed ignored runs. No existing allocation or failure was reset. Root owns a new full run03 after narrow review, with only the time remaining before the original absolute deadline **03:41:39Z**. The report's SDD mirror is updated byte-for-byte. **HOLD for narrow review and Root's subsequent execution.**
