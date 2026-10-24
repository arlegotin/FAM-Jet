# E3 FIX2 narrow rereview — 24 October 2026

**SPEC: YES**  
**QUALITY: APPROVED**  
**R1: ADDRESSED**

This verdict closes the sole open source-review finding, R1, and preserves the prior acceptance of I1–I5 and M1/M2. No new breakage was identified in the FIX2 source/test changes. It does not establish production feasibility or authorize an experiment.

## Scope

Reviewed R1 against the adopted brief and the complete appended FIX2 report, then inspected the changed source/test hunks in `e2e-task-3-fix2-review-package.md`: FIX_BASE `c8f95d6a11bb2c078258a34315137d4a0927bdae` through HEAD `ee0705c63b9af8ee575fa7fcceb21b80ecb770bd`. The implementation change is confined to `famjet_poc/study.py`; affected tests are the cache and study test files. No unrelated source review was reopened.

No tests, Git commands, benchmarks, protected-data access, source edits or subagents were used. This report is the only authored artifact for the rereview.

## R1 assessment

At `famjet_poc/study.py:676–698`, `_cache_for` now distinguishes the configured total cache ceiling from the optional incremental allowance for new disk writes:

- Existing caches retain the ordered history/spec-hash checks, source/hash validation, fixed LRU ceiling and configured total-size check. They return without requiring their existing bytes to fit unused phase space.
- New caches receive the smaller of the configured total ceiling and incremental allowance. Zero incremental allowance rejects construction, while valid reuse is permitted.
- Probe callers at `study.py:719–730` and development callers at `study.py:839–853` pass total and incremental values separately for both caches. The development-cache total ceiling deducts the training cache once from the shared configured cache budget. Whole-directory `_admit` continues enforcing the phase disk total.

This removes the double charge identified in FIX1 without weakening the accepted population-identity or finite-disk checks.

The added caller regressions at `tests/test_poc_e3_study.py:255` and `tests/test_poc_e3_study.py:295` prebuild both real tiny-population caches, set free phase space below each cache's size, prohibit regeneration, reach the post-reopen fit boundary, and verify unchanged cache hashes and modification times. The helper checks at `tests/test_poc_e3_cache.py:91–96` cover zero-space reuse and insufficient-space construction; the earlier rejection of an actually insufficient configured total ceiling remains present. These tests exercise the distinction missing from FIX1. They deliberately stop before performing a development study.

## Findings

Critical: none. Important: none remaining in scope. Minor: none identified in the fix diff.

## Supplied evidence and limits

`fixround2/scoped-cache-study-final.json/.log` records the two affected test files: **25 passed**, pytest **2.16 s**, wrapper **2.382702 s**, exit **0**, with all five numerical thread environment values set to 1. `fixround2/compile-fixround2.json` records compilation of the changed implementation and two test files, exit **0**. These are supplied results, not rerun verification. Root separately audits raw evidence bytes and preserved source paths.

Actual production runtime, disk-volume feasibility, 40-fit/46-panel outcomes, protected evaluation and complete timing remain unentered. Current whole-tree RSS/physical concurrency and inference workspace remain distinct from the existing lifetime-peak proxy and require Root's separate monitoring/allocation. The later full executable freeze remains separate from scoped E1/E3 identities. None of these unclaimed experiment obligations blocks this narrow source approval, and source approval does not repair historical failures.

**Disposition:** no further R1 fix round is required. E3 is approved at the reviewed source level, subject to Root's separate evidence/preservation audit and explicit allocation of any actual experiment.
