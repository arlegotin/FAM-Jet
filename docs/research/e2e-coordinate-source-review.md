# E6 coordinate-diagnostic amendment task review

SPEC: NO. QUALITY: NEEDS FIXES.

Reviewed base `7547deac07b13f8f90aecbb1db3c7279e59f5692` through head `254424b0f91f7517af503ca04ae9a49f5bc8a00f`, using the supplied package and task brief, committed design/short plan, and implementer report. This is the source-task gate, not the later whole-branch or scientific-results review.

## Spec compliance

The implementation follows the explicitly chosen diagnostic route and preserves the original default failure, but numeric-model provenance is not validated against the selected checkpoint outside the selected real pre-test reference. This misses the brief's requirement to validate model numeric identity through E3/E4 synthetic and real/E5 and reject model mismatches (Important R1 below).

The Root amendment explicitly authorizes the diagnostic route after the Decimal evidence. I found no plan-authority defect in choosing that route. Prospective stage resource metadata retains the historical allocation and unchanged overall deadline: `docs/research/e2e-development-resource-policy.json:4`, `:23`, `:35`; `docs/research/e2e-coordinate-source-compatibility.json:11`, `:98`.

## Strengths

- `famjet_poc/comparators.py:100`, `:143`, `:149`, `:154`: the keyword mode is explicit and boolean; state finiteness/original tolerance and all five masks are mandatory; the strict default still raises. Prediction-only failure remains `FAILED` with the original 1e-12 tolerances.
- `famjet_poc/comparators.py:159`, `:194`: history/query inventory, scalar counts, state/mask booleans, model/policy identities, original tolerances, and maxima are preserved and checked. Summary reconstruction and audit hashing reject ordinary missing/altered records.
- `famjet_poc/study.py:544`, `:589`: equivalent evaluation explicitly requests diagnostic mode, persists the records in hashed costs, and validates their summary. Scoring and worker paths remain unchanged; diagnostic timing is included.
- `famjet_poc/transfer.py:245`, `:271`, `:548`: selected real pre-test reference validates the exact four-history × 120-query inventory and actual selected K12 Jet numeric identity. Its `diagnostic_complete` status correctly permits a retained strict-read `FAILED`, without calling equivalence passed.
- `famjet_poc/report_inputs.py:165`: portable selected-reference validation rebases both row and model I/O paths in a copy and returns the original reference. The existing temporary-derived-probe adapter is untouched.
- `famjet_poc/report.py:141`, `:168`: machine and Markdown output expose each coordinate receipt's coverage, failure counts, maxima, and state/mask status, with original run01 failure/cost and diagnosis kept separate. The checked projection functions preserve costs for development, synthetic, and both real modes.
- `tests/test_poc_coordinate_diagnostic.py:35`, `:59`, `:89`, `:181`: the new tests exercise real cancellation, all five mask/state hard failures, normal fallback scoring, producer-shaped E3/E4 records, and copied replay with the original directory removed. Existing query/method tamper coverage was retained.

## Issues

### Critical

None found.

### Important — R1: bind every coordinate audit to the expected numeric model

**Locations:** `famjet_poc/protected.py:578`; `famjet_poc/report_inputs.py:607`, `:644`; `famjet_poc/study.py:800`; underlying optional identity check at `famjet_poc/comparators.py:210`.

These consumers call `validate_coordinate_audits(costs, rows)` without its `model_numeric_sha256` argument. Consequently, the function checks that the model digest in each history agrees with the digest in the same costs object, but never proves it is the frozen/selected model for that phase. The selected-reference path at `famjet_poc/transfer.py:271` does perform that proof; protected synthetic and real releases, development/stress replay, and development resume do not.

The existing outer model/grant commitments do not close this new relationship: protected receipts bind a checkpoint-pair commitment (`protected.py:694`), and real receipts bind their mode/checkpoint (`transfer.py:707`), while `validate_scored_receipt` never compares either to the coordinate numeric digest. E5 checks the outer commitment at `report_inputs.py:262` and `:704`, then invokes that unbound validator at `:296`, `:736`, and `:737`. A coherent diagnostic bundle for another numeric reader can therefore pass while the outer receipt still names the expected model. In development/stress, the same digest substitution also passes the new audit check.

**Focused reproduction:** an in-memory one-history/one-query fallback audit with model digest A validates. Changing both `costs.coordinate_model_sha256` and the history's `model_numeric_sha256` to digest B, updating the audit hash, and keeping the otherwise valid summary also validates. Passing expected digest A explicitly rejects the identical modified bundle. No fitting, files, arrays, or scientific execution were involved.

**Fix:** derive the expected numeric digest from the phase's already verified selected Jet checkpoint and pass it through the E3 resume/E4 release/E5 replay admission paths. Bind the expected shape/value dimension at the same boundary where appropriate. Add producer-shaped tests that change all internal model digests coherently, recompute the local audit hash, retain the independently frozen checkpoint commitment, and require rejection for synthetic, real, development/stress, and portable replay. Preserve the current selected-reference check.

### Minor — R2: reject a nonzero scaled maximum when no prediction scalar was evaluated

**Location:** `famjet_poc/comparators.py:249`–`:254`.

The zero-evaluated-scalar branch requires `max_prediction_absolute_error == 0` but does not require `max_prediction_scaled_error == 0`. A fallback diagnostic with zero evaluated scalars, zero absolute maximum, and scaled maximum 0.5 passes both summary generation and required-summary validation. This cannot be emitted by `_errors` for an empty input and is contradictory diagnostic metadata. The producer is correct, so this is a validator consistency weakness rather than an observed scientific scoring error.

**Fix:** require both maxima to be zero for an empty comparison and add a small pure-validator regression. Consider rejecting other impossible zero/nonzero absolute/scaled combinations while retaining valid floating-point behavior.

## Evidence and focused cross-task checks

- Read the packaged diff in sequential segments. Initial tool-output truncation affected documentation/evidence portions; the affected opening metadata was recovered. Production/test changes were reviewed from the diff, not by rereading changed functions. No Git command, suite rerun, fit, protected generation/access, or actual benchmark was performed.
- Reviewed final recorded evidence: `docs/research/e2e-coordinate-source-evidence/green-final-02.log:1` reports 84 passed in 18.06s with no warnings; its adjacent JSON records exit 0, 180 bytes, SHA-256 `72d093e748bd77dc9c408069237b062346a6e4651097633f05ba73069aa194b5`, and 18.34038179199706s process duration. `compile-final-02.json:17` records exit 0 and empty output; whitespace evidence is also clean. Earlier failed attempts remain recorded rather than hidden.
- **Named risk: report projections could discard coordinate costs.** Inspected focused unchanged `project_development_journal`, `_release_rows`, and `_verify_real_release` in `report_inputs.py`. They preserve costs at lines 571, 308, and 781 respectively, so the recursive report collector can expose all requested scopes.
- **Named risk: new numeric identity might lack a binding to the independently selected checkpoint.** Inspected focused unchanged `_evaluate_cell_body` in `protected.py` and `_evaluate_real_mode_body` in `transfer.py`, plus the unchanged release-validation portions of the functions above. They establish the outer commitments but do not bind them to the new numeric audit identity; this substantiates R1.
- **Named risk: stress might swallow mandatory state/mask failures.** Inspected unchanged `pipeline.run_stress` (`pipeline.py:398`). Its Laguerre call at line 470 is not wrapped in a catch that converts the hard comparator exception into success.
- Ran only a focused pure-validator probe using `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -` with in-memory dictionaries. Exit 0 in 0.6s. Output: `ACCEPTED: internally consistent model B instead of expected model A when consumer omits external model identity`; `REJECTED: same model substitution with explicit expected model identity`; `ACCEPTED: evaluated_scalar_count=0 and max_prediction_absolute_error=0 but max_prediction_scaled_error=0.5`.

## Limits and assessment

The package shows no modifications to core53/E1/E2 models/data/inference, worker/wire/cache/timing/locks, pipeline, scientific selection, or primary metrics. The retained verification receipt reports E1/E2 unchanged and the new E3 source pin. I did not independently rerun that verification or inspect the ignored run01 byte inventory; Root retains those checks. The SDD report mirror's byte equality is also outside the committed diff and remains a Root check.

Actual current-source probes, fresh-run resource/deadline enforcement, old/new selected-model equality, protected results, complete deterministic/copied report replay, and whole-branch review remain future Root work. The source-task test evidence cannot establish those outcomes or a universal numerical bound.

**Task quality: Needs fixes.** The comparator and selected-reference implementation are careful and the focused test evidence is useful. The unbound numeric-model relationship in other release/replay paths must be closed before treating the full diagnostic chain as validated.
