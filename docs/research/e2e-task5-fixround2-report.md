# E5 fix round 2 — candidate model and row closure — 24 October 2026

Base `58e33bcc6f8d69f4b2e6bbda64bd261f90937eb3`; scoped rereview `.superpowers/sdd/2026-10-16-famjet/e2e-task-5-fix1-review.md` found N2 only. Source/tests commit `83bbd072`. This round did not run the scientific program, protected arrays, legacy/core suites or E2 calibration.

## Repair

`project_development_journal` now requires a complete, correctly typed model reference and row reference together for every qualified candidate and post-fit scored failure. It admits missing refs only for the explicit terminal pre-model `numerical_fit` failure with a nonempty error, unavailable loss, and no score or costs. `_verify_development` then loads both artifacts for every candidate with a model. The row loader and model loader still verify the referenced bytes. The source change is confined to `famjet_poc/report_inputs.py`.

The added producer-shaped test mutates a 36-candidate journal at the selected qualified candidate or a post-fit scored failure. It covers both refs missing, either ref missing, wrong ref types and incomplete ref dictionaries. For each mutation it also writes a fresh hash-consistent journal artifact and enters `_verify_development` through its actual stage/freeze SHA boundary; the rejection is the candidate evidence guard, not a mismatched outer SHA. The existing positive producer fixture retains the permitted pre-model failure and passed.

## Exact commands and retained output

All commands ran from repository root with `FAMJET_REPORT_PYTHON=/private/tmp/famjet-report-20261024-01/bin/python`. [`invoke.py`](e2e-task5-fixround2-evidence/invoke.py) records exact child argv, environment, raw combined stdout/stderr bytes and SHA-256, exit status and elapsed time. Prior 39 E5 invocations remain untouched.

| Label | Child argv | Result | Raw output and receipt |
| --- | --- | --- | --- |
| RED | `.venv/bin/python -m pytest -q tests/test_poc_report_scientific.py -k candidate_model_and_rows` | Exit 1; ten expected failures exposed absent/optional refs. | [`log`](e2e-task5-fixround2-evidence/red-candidate-refs-01.log), [`receipt`](e2e-task5-fixround2-evidence/red-candidate-refs-01.json) |
| First green attempt | Same child argv | Exit 1; nine passed, one expected-error-message mismatch on a rejected scored failure. | [`log`](e2e-task5-fixround2-evidence/green-candidate-refs-01.log), [`receipt`](e2e-task5-fixround2-evidence/green-candidate-refs-01.json) |
| Green | Same child argv | Exit 0; ten passed, five deselected. | [`log`](e2e-task5-fixround2-evidence/green-candidate-refs-02.log), [`receipt`](e2e-task5-fixround2-evidence/green-candidate-refs-02.json) |
| Final scoped gate | `.venv/bin/python -m pytest -q tests/test_poc_report_scientific.py tests/test_poc_report_inputs.py tests/test_poc_report.py` | Exit 0; **26 passed in 1.37 seconds**. | [`log`](e2e-task5-fixround2-evidence/final-fix2-pytest-01.log), [`receipt`](e2e-task5-fixround2-evidence/final-fix2-pytest-01.json) |
| Compile | `.venv/bin/python -m py_compile famjet_poc/report_inputs.py tests/test_poc_report_scientific.py` | Exit 0; zero output. | [`log`](e2e-task5-fixround2-evidence/final-fix2-compile-01.log), [`receipt`](e2e-task5-fixround2-evidence/final-fix2-compile-01.json) |

The scoped source/test `git diff --check` and staged source/test whitespace check passed. Failed pytest logs retain their exact traceback bytes; the evidence commit uses scoped checks on source and report text and retains raw logs unchanged.

## Limit

These hash-consistent fixtures exercise the production projection and journal verification boundary. They do not constitute a complete E4 release, actual production `render_report`, copied production archive replay, or scientific result. Root owns those later gates. The previously reviewed E5 I1–I4 and two minor repairs remain as accepted in the scoped rereview; this round does not reopen them.
