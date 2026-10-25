# E6 R4 report timing inventory correction

25 October 2026. **Implemented; HOLD for independent review.** Base `95c9557edda09eea02f3ff3296edd6f87155ef1c`; source/tests commit **`8e4e567e115a5410cfc9f728bd03eebb0736a906`**. This is a report-only correction. No benchmark, numerical model, study coordinator, protected population, saved fit, or interrupted-run artifact was changed or executed.

Root identified a guaranteed pre-freeze reporting mismatch: the timing producer measures Jet, Bank, exact, recent, latest_lru, reservoir and buckets—seven deployment methods—while the scored release also includes the Gamma/Laguerre numerical control. `_verify_timing` incorrectly required eight timing summaries; `_science_chart_data` then indexed a nonexistent `timing['laguerre']`. The producer-shaped RED run reproduced both failures: `ValueError: paired timing inventory incomplete` and `KeyError: 'laguerre'`.

## Corrected contract

`report_inputs._verify_timing` now derives the deployment roster by removing **only** `laguerre` from the independently expected scored roster. It preserves the three-warmup, twelve-block, Q1/Q8/Q64 policy and source-bound artifact read. It requires exactly the seven actual summaries, all three query-count keys in each summary, and exactly one record for every method/query-count/block combination: 252 records for this study. Missing Bank, any other timed method, a missing row, a duplicated block replacing a record, a wrong query count, or a missing summary query count still blocks report admission. No additional missing method is tolerated.

The returned timing projection keeps the original seven summaries, break-even data, RSS scope and admission intact. It adds `unmeasured_methods.laguerre` with `status: not_measured`, `query_seconds: null`, and reason `coordinate_reference_validation_not_deployment_timing`. Existing `_science_machine` already preserves this timing projection, so the machine report exposes the status without inventing an eighth measurement or substituting Jet latency.

`report._science_chart_data` emits the seven actually deployment-timed methods, preserving their existing accuracy, state, static-storage and Q8 read values. It skips Gamma's deployment-timing entry and adds the corresponding explicit `omitted_methods.laguerre` status/null/reason. It does not mutate development inputs, drop a scored method from the raw report, or replace a coordinate cost with a deployment latency.

The small `_science_markdown` caption change states that the two descriptive method charts contain seven deployment-timed methods, that Gamma/Laguerre is omitted with deployment latency `not_measured` / machine `null`, and that its scored accuracy, state, coordinate diagnostics and reference-validation costs remain in tables and machine JSON. All eight scored methods remain represented in the development data; protected/real scoring tables and the coordinate-diagnostic report path are unchanged. The paired-effect chart inputs are unchanged. `plots.py` was read to verify compatibility with the added chart metadata and was not edited or executed.

No other report functions changed. The only production edits are `_verify_timing`, `_science_chart_data`, and the omission caption in `_science_markdown`. The focused tests are in `tests/test_poc_report_scientific.py`; `tests/test_poc_report.py` was run unchanged.

## Verification

The fixture uses the timing producer's actual fields: `summaries`, string query-count keys, and record `method`, `query_count`, `block`. It persists a hash-bound timing JSON and exercises the real report input resolver. The existing development fixture now supplies seven timings for eight scored methods, verifies deterministic seven-entry chart output, no Gamma latency, explicit null/status, the omission caption, unchanged input data, and retained Gamma loss and reference-validation cost in the machine result. Separate corruptions verify all required non-Gamma coverage remains mandatory. The test suite also retains existing portable-reference and report-replay checks; this task did not construct or execute an actual scientific release.

Exact commands and raw output receipts are in [evidence](e2e-report-timing-fix-evidence/):

| Record | Command and result |
| --- | --- |
| `red-01` | `.venv/bin/python -m pytest -q tests/test_poc_report_scientific.py -k 'producer_candidate_storage or seven_actual_timings or only_gamma'`; exit 1; 2 failed / 5 passed / 14 deselected, 0.96 s pytest time, 1.219367040997895 s process time. Both expected pre-fix failures are retained. |
| `green-01` | `.venv/bin/python -m pytest -q tests/test_poc_report_scientific.py tests/test_poc_report.py`; exit 0; 25 passed in 2.63 s. |
| `green-final` | Same focused command after stronger machine/caption/input-preservation assertions; exit 0; **25 passed in 2.60 s**, 2.86409604200162 s process time. |
| `compile-final` | `.venv/bin/python -m py_compile famjet_poc/report.py famjet_poc/report_inputs.py`; exit 0, empty output. |
| `diff-check` | `git diff --check`; exit 0, empty output. |
| `verification-final` | `.venv/bin/python docs/research/e2e-report-timing-fix-evidence/verify_fix.py`; exit 0, verifies named-function scope and unchanged source identities/modules. |

[Final test log](e2e-report-timing-fix-evidence/green-final.log): **99 bytes**, SHA-256 `47aec6ca5bb9131f9e6d5cd4e410239b2f48ceb34ecfdc1ab047399e0375c9bd`. [RED log](e2e-report-timing-fix-evidence/red-01.log): **5523 bytes**, SHA-256 `b5c55d84fc613b2ffbb430a450829078cee5cb13e91bc206a780a2a75f2254c9`. [Verification log](e2e-report-timing-fix-evidence/verification-final.log): **486 bytes**, SHA-256 `8237ecf0d05d703fd5474884d814c4122e2fe874c43366574e8f4c8865754687`. Every log has adjacent exact argv/exit/elapsed/bytes/hash JSON; the capture runner, read-only verifier and evidence index are retained. No broad 89/155/156-test suite, inference calibration, new timing benchmark, or actual protected/report rendering run was performed.

## Source and run preservation

The read-only verifier confirms:

- E1 remains `f78761891876540011e577293e31a89c7661ef66adbb522d2cbcd36c331d8475`.
- E2 remains `5cdbae0a61810a0f9d509ed1d462530d708439021f8f9fc81ce04fd12f39bfb4`.
- E3 remains **`e25b63ee60f51ed511fc7af5d3f713c9a404301f51178283c0a2066d940e68ba`**.
- ASTs outside the three named report functions are unchanged. All other production modules—including pipeline, timing, plots, worker, wire, cache, models and inference—plus core/configs/locks/resource policy and old coordinate-source evidence are unchanged from this task's base.

Root deliberately interrupted only its verified public run03 process group before freeze/protected access. Its witness reported parent exit **-15**, elapsed **1705.092098292 seconds**, current RSS **866713600 bytes**, with 40 public fits and five simple controls saved and Gamma work in progress. That interruption remains visible; it is not relabeled as success. Original failed runs01/02 also remain failed. This task neither opened nor modified the saved run03 files and did not issue `--resume`; Root retains the independent checkpoint byte/source baseline and run inventory checks.

The original phase 3600-second clock and overall deadline **03:41:39.663497Z** remain unchanged. The full executable identity changes due to reporting code; E3 remains unchanged so this patch does not require new fit computation or source-cache adoption. Whether to resume is Root's decision after independent review and its existing-output witness checks. No report test guarantees completion within the remaining allowance or predicts protected scientific results.

The report is mirrored byte-for-byte at `.superpowers/sdd/2026-10-16-famjet/e2e-report-timing-fix-report.md`. **HOLD for independent review; Root owns any checkpoint resume and all subsequent actual execution.**
