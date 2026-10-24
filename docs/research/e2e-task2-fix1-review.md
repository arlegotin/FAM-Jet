# E2 fixround 1 — independent SPEC + QUALITY rereview

24 October 2026. Scope: supplied fix diff `2d567442a22c7adac6e414341e0b302a866cdf3e` → `5fb02e180eda011a8a947f5288cfbf9875e01ee9`, complete appended report, changed source/tests and retained regression evidence. Reviewed only the original findings and consequences of these changes. **Verdict: all four original findings ADDRESSED within the E2 source boundary; no new blocking source defect identified. HOLD for Root acceptance and separately admitted execution. Scientific qualification remains unentered.**

## SPEC

**Important 1 — ADDRESSED.** `famjet_poc/inference.py:290` now calls the public production interval for each dataset, and `:300` evaluates both genuinely shifted raw history inputs. Comparison checks D, V, df, endpoints, status and shifted coverage; failed equivalence prevents gate acceptance. Separate deterministic preflight controls at `:98` exercise ±.05 and −2× sign/scale behavior before counts, with an input digest and revalidation at `:507`. `tests/test_poc_inference.py:241` corrupts a shifted production result; `:255` checks reconstructed inputs for every law; `:351` verifies corrupted sign/scale controls block counts. The old independent calibration formula and tautological translation check are removed. The campaign retains three production interval calls per valid dataset; preflight controls are separate.

**Important 2 — ADDRESSED for allocation and the documented E4 handoff.** `famjet_poc/inference.py:179` requires the exact scientific manifest fields and current source digest. Confirmation/replication admit only attempt1/128 or attempt2/256; nuisance remains attempt0/16 with null calibration digest. Exact 12-cell inventories remain mandatory. `tests/test_poc_inference.py:282` accepts both allocations and the revision replication panel, and rejects mismatched attempts, allocations, source, missing IDs and malformed digest.

The actual calibration-byte binding is an **E4 obligation, not a property established by this validator**: `:192` checks digest syntax, not the referenced evidence. The test deliberately uses `'a'*64`. As explicitly documented in the appended report and `:170`, E4 must validate accepted calibration evidence, hash its actual bytes, compare its attempt/per-cell/source to both frozen panels and enforce the prospective revision admission. A syntactically valid E2 manifest cannot authorize protection. This integration obligation must remain in E4 acceptance tests; actual accepted evidence does not yet exist.

**Important 3 — ADDRESSED.** `famjet_poc/inference.py:458` checks time after stored batch progress, including the final batch; `:460` checks before completion; `:473` records finalization-entry time and downgrades a late complete status. Start/deadline/source admission commitments are persisted. At `:517`, validation checks finite ordered timing and its commitment; complete evidence additionally requires the externally supplied matching deadline and end strictly before it. `tests/test_poc_inference.py:309` preserves the final batch while recording incomplete and rejects a forged complete overrun. Parent process accounting and final receipt-write/finalization reserve remain necessary, as in the original resource contract.

**Minor metadata finding — ADDRESSED.** `famjet_poc/inference.py:500` verifies schema, engine and exact ordered strata; `tests/test_poc_inference.py:326` mutates persisted evidence consistently and verifies rejection.

## QUALITY and limits

The fixes reuse production behavior, keep bounded batches and retained failures, and introduce focused regression checks. Recorded final evidence reports **22 PASS**, successful compilation and Torch-free import. Five nonzero fixround logs retain the intermediate failures; earlier raw logs are untouched by this review. Root's separate byte audit owns the 12 invocation receipts and old/E1 preservation proof. The new REDs capture the actual regressions; no earlier reviewer invocation metadata was reconstructed.

No tests, imports, actual probe, calibration, models, protected access, external reads or Git operations were executed during this rereview. Only this review file was written. Population applicability, actual resource feasibility, all32 empirical guards and scientific qualification remain unverified. **HOLD.**

**SPEC YES; QUALITY APPROVED for E2 source.** The E4 actual calibration digest/attempt verification handoff remains binding; this source verdict does not establish scientific qualification or release execution.
