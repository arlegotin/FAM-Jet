# E6 coordinate diagnostic fix-round 1 scoped re-review

R1 — ADDRESSED. R2 — ADDRESSED.

Overall source-task disposition: **SPEC YES; QUALITY APPROVED.** This supersedes the open R1/R2 disposition in the initial source-task review, subject to the execution/replay limits below.

Reviewed fix base `254424b0f91f7517af503ca04ae9a49f5bc8a00f` through head `11f6af785bfa99e6e9cadbf2b4a6f6afc5c83fdf`, using the supplied fix package, the previously reviewed task brief/design/plan, the original findings, and the appended fix report. Scope was R1, R2, and breakage introduced by this fix.

## Finding verdicts

**R1: independent numeric-model binding — ADDRESSED.**

`famjet_poc/comparators.py:203` now requires `expected_model`; it rejects a missing/non-Jet object, derives the expected numeric digest from that object, and compares the costs digest against it. Per-history identity remains checked, and `:243` binds value dimension to the independent model. The former optional-digest admission path no longer exists. `load_coordinate_model` at `:91` loads a content-verified checkpoint, checks Jet family/expected shape, and supports portable path resolution without taking authority from audit fields.

All affected production admissions supply the independently selected model:

| Boundary | Evidence |
| --- | --- |
| E3 producer | `famjet_poc/study.py:590` passes the actual evaluated model. |
| E3 resume | `famjet_poc/study.py:807` recomputes the Jet winner, requires its reference to match saved selection, enforces the local artifact boundary, loads it, and passes it at `:813`. |
| Shared synthetic/real receipt validator | `famjet_poc/protected.py:490`, `:579` forward the independent model; omitting it cannot admit Laguerre rows. |
| E4 synthetic sealing | `famjet_poc/protected.py:767` verifies the selected checkpoint-pair commitment and loads its Jet; `:827` checks population shape and `:829` passes the model. |
| Selected real pre-test reference | `famjet_poc/transfer.py:270`, `:274` retain the actual selected model, numeric identity and complete-inventory checks and pass the model object. |
| E4 real read/seal | `famjet_poc/transfer.py:770`, `:830`–`:832` load each independently bound mode's K12/V1 Jet and pass it for the coordinate receipt, including both normalized/native rows at sealing. |
| E5 synthetic replay | `famjet_poc/report_inputs.py:297` loads the frozen selected Jet through `paths.resolve`, with the population shape, for receipt admission. |
| E5 development replay | `famjet_poc/report_inputs.py:613`–`:619` require the journal selection to match the independently frozen shape-specific checkpoint and load it through the portable resolver. |
| E5 stress replay | `famjet_poc/report_inputs.py:637`, `:650`–`:652`, `:871` supply the verified freeze and load its selected K16/V8 Jet. |
| E5 real replay | `famjet_poc/report_inputs.py:747`–`:749` load the independently bound mode's K12/V1 Jet and pass it to normalized/native receipt validation. |

Regression coverage now makes the model substitution coherent across costs and every audit, recomputes the audit hash, and retains the independent checkpoint authority. The tests require rejection at resume (`tests/test_poc_coordinate_diagnostic.py:274`), shared receipt admission (`:296`), portable development/stress replay (`:322`), and actual synthetic sealing (`tests/test_poc_protected.py:213`). Portable tests remove the original run directory. The value-dimension forgery and `expected_model=None` cases are also rejected (`tests/test_poc_coordinate_diagnostic.py:138`).

**R2: empty-comparison maxima consistency — ADDRESSED.**

`famjet_poc/comparators.py:265`–`:266` require both absolute and scaled prediction maxima to be zero whenever no scalar was evaluated. `tests/test_poc_coordinate_diagnostic.py:130` changes the scaled maximum to 0.5, updates both the audit hash and summary, and requires rejection. The ordinary fallback case immediately preceding it remains accepted with full query scoring.

## New breakage in the fix diff

None found. The changes add model/shape admission checks without modifying the strict comparator default, original tolerances, state/mask checks, primary model parameters, prediction/scoring/fallback algorithms, scientific selection, or inference. Existing policy/count/label/grant/source/resource closures remain before the added shared validator call. The unit fixture's added selected-model references supply the newly required authority instead of bypassing it.

The E3 pin is updated consistently in `famjet_poc/transfer.py:105`, `docs/research/e2e-development-resource-policy.json:5`, and `docs/research/e2e-coordinate-source-compatibility.json:10`; revision history retains the superseded pin. No cache-adoption path, tolerance relaxation, deadline reset, or pipeline edit is introduced.

## Out-of-scope observations

None.

## Checks and evidence

- Read the entire fix package once in bounded segments and the appended report. No Git operation, suite rerun, fitting, protected access/generation, public preflight, or scientific execution was performed.
- Two focused context checks addressed fix-specific risks where the diff began mid-function: `study._audit_terminal_entries.local_ref` at `study.py:779` really enforces the local allocation boundary; the beginning of `RealReleaseRef.read` at `transfer.py:743`–`:752` establishes and verifies `modes` before the new checkpoint lookup. No unrelated source review was conducted.
- The retained `fix-round1/covering-02.json` names all eight covering test files, exit 0, 29.713821750003262s process duration, and the 180-byte raw log hash `60c11aa55c8bd60f2cc34dd939c9657928a8955ebfe9fc91b7fac8e9ae6d75b2`. Its raw log reports **89 passed in 29.42s**, with no warnings.
- `fix-round1/compile-final.json` covers the five changed production modules and both changed tests, exit 0 and empty output. Whitespace evidence is also clean. The two RED logs reproduce the original counterexamples; the first covering failure is retained and its fixture correction is visible in the diff.
- `fix-round1/verification-final.log` records all 13 explicit-model admission calls and reports preservation of 36 original evidence files / 66722 bytes, E1/E2 identities, and protected source areas. I reviewed the verifier and its output but did not rerun it. The callable inventory complements the actual substitution regressions; it is not treated as behavioral proof on its own.

## Verdict and limits

**Fix round: All findings addressed, no new Critical/Important breakage.** R1 and R2 are closed. **SPEC YES; QUALITY APPROVED** for the coordinate-diagnostic source amendment.

This source gate does not certify a full 56-block real release, current-source scientific completion, future mandatory state/mask success, or FP64 read equivalence. Root still owns ignored run01 byte preservation checks, fresh source-matched probes and the fixed fresh run under the remaining original absolute deadline, selected-model comparison, protected work, deterministic/copied final replay, and the separate whole-branch review. The original strict-read failures remain failures; no universal error bound follows from this approval.
