# E6 R4 report timing contract review

## Spec Compliance

- ✅ **SPEC YES.** `_verify_timing` excludes only `laguerre` from the scored roster, requires exact seven-method summaries with Q1/Q8/Q64 keys, and checks all 12 method/query/block combinations exactly once (`famjet_poc/report_inputs.py:624-644`). A missing Bank, row, block, query count, or summary key still raises; the new corruption cases cover these paths (`tests/test_poc_report_scientific.py:314-337`).
- ✅ The timing projection records Gamma as `not_measured` with `query_seconds: null`, while retaining the producer's seven summaries and other timing metadata (`famjet_poc/report_inputs.py:640-645`). The chart excludes Gamma's nonexistent latency and marks its omission explicitly (`famjet_poc/report.py:75-102`); the Markdown caption explains the seven measured methods and Gamma's retained scored data (`famjet_poc/report.py:305-319`).
- ✅ All eight scored methods remain in the development projection and machine report (`famjet_poc/report.py:196-215`); the test checks Gamma loss, reference-validation cost, unchanged chart inputs, and machine timing status (`tests/test_poc_report_scientific.py:69-100, 131-144`). No metric, numerical model, or timing producer change appears in the scoped diff (`famjet_poc/report.py:75-102, 305-319`; `famjet_poc/report_inputs.py:624-645`).
- ✅ The claimed focused verification is present: the producer-shaped RED output shows the former `KeyError` and inventory rejection (`docs/research/e2e-report-timing-fix-evidence/red-01.log:1-86`); the final focused run reports 25 passed without warnings (`docs/research/e2e-report-timing-fix-evidence/green-final.log:1-2`), and compilation and scope receipts report exit zero (`docs/research/e2e-report-timing-fix-evidence/compile-final.json:1-14`; `docs/research/e2e-report-timing-fix-evidence/verification-final.log:1-9`). I did not rerun tests or the interrupted study.
- ⚠️ Actual release rendering and resumed run completion remain unverified by this task, as stated in `docs/research/e2e-report-timing-fix-report.md:33-49`. Root should retain its planned existing-output checkpoint witness and resume gate; this is not a defect in the scoped correction.

## Strengths

- The validator checks record identity rather than count alone, so a duplicate cannot conceal a missing timing block (`famjet_poc/report_inputs.py:627-638`).
- The chart carries omission metadata without altering the raw scored controls, and the machine report passes through development and timing projections (`famjet_poc/report.py:89-102, 211-215`).
- The focused tests exercise a hash-bound producer-shaped artifact and both success and corruptions (`tests/test_poc_report_scientific.py:280-337`).

## Issues

### Critical (Must Fix)

None.

### Important (Should Fix)

None.

### Minor (Nice to Have)

None.

## Named risk checks

- **Producer field/schema risk:** The unchanged producer emits `method`, integer `query_count`, and integer `block` records for non-warmup blocks, plus string query-count summary keys (`famjet_poc/timing.py:137-143, 205-206, 230-250`), matching the new validator (`famjet_poc/report_inputs.py:627-638`).
- **Renderer metadata risk:** The unchanged renderer validates and plots `methods` and `effects`, with no whole-object key restriction; it therefore accepts `omitted_methods` and plots only the seven measured entries (`famjet_poc/plots.py:36-53, 77-98`; `famjet_poc/report.py:99-102`).
- **Scored Gamma retention risk:** `_science_machine` includes full development and timing projections, and `_science_markdown` still prints simple-control rows and the coordinate diagnostic section (`famjet_poc/report.py:196-215, 293-319, 414`).

## Assessment

**Task quality: QUALITY APPROVED.** The scoped implementation fixes the seven-timed versus eight-scored mismatch while preserving Gamma's scored evidence and rejecting incomplete actual timing inventories. The focused receipts are clean; actual run completion remains Root's separate gate.
