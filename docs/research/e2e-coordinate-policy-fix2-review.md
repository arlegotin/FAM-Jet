# Scoped re-review: R3 runtime probe policy fix

**R3 obsolete prose gate — ADDRESSED.** `famjet_poc/pipeline.py:256-268` now requires `fresh_probe_required is True` while retaining the current E3/manifest checks and returning the same fresh probe allocation. `docs/research/e2e-development-resource-policy.json:5,32-35` keeps the current E3 pin and descriptive historical status, and adds the true machine flag. The fresh execution path still calls `execute_study_probe` and checks its source-bound receipt (`famjet_poc/pipeline.py:554-565`).

**Required regressions — COVERED.** `tests/test_poc_pipeline.py:312-327` uses the repository config and policy with real `study_manifest` and asserts the complete allocation. Lines 330-348 cover arbitrary provenance prose, E3 mismatch, and missing/`None`/`False`/integer/string flags. The retained `green-01.log` reports 23 passed in 1.47 seconds; `green-01.json` records exit 0. `compile-final.json` records exit 0 for the changed pipeline and test files. These are implementer runs; this review ran no tests.

**New breakage in fix diff — None found.** The resource JSON adds one field; the function retains the phase, allocation ID, limits, source binding, and fresh probe path. The retained `verification-final.log` reports unchanged E1/E2/E3 identities and unchanged production code outside this function; `docs/research/e2e-coordinate-source-report.md:154-158` correctly limits its claims about ignored run artifacts and the original deadline.

**Out-of-scope observations — None.** R1/R2 and the approved E6 numerical amendment were outside this review.

**SPEC YES. QUALITY APPROVED. Fix round: all R3 findings addressed, no new Critical or Important breakage in scope.** Approval is for the source gate; the actual run03 remains unexecuted by this reviewer.
