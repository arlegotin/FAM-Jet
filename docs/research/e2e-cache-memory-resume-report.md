# E6 R5 cache memory admission and run04 resume preparation report

**Date:** 2026-10-25 UTC

**Status:** HOLD — source correction and helper preparation verified; root review and actual resume are outstanding.

**Base:** `27dc49a0f61a12e9cf319d20c6cc9aeefe2a84dc`

**Source/test commit:** `5a6441cf` (`fix: admit bounded Darwin cache headroom for public timing retry`)

## Failure and bounded correction

Run04 stopped with exit 1 at `timing_k16` RAM admission after K16 development completed (40 fits and six controls). Its peak owned RSS was 867,942,400 bytes over 1,700.733107708 seconds; no live guard cap fired. The raw host observation near 01:10 UTC had 16,384 byte pages, 55,310 free, 75,548 speculative, 944,049 inactive, and 1,112,139 file backed; pressure level was `1`, swap zero, and `memory_pressure -Q` reported 87%. The old observer counted only free plus speculative pages, below its 2 GiB admission floor, even though a bounded portion of file backed inactive cache was available under normal pressure.

The Darwin observer now uses `raw = (free + speculative) * page_size` and, only when the `sysctl` pressure level is exactly `1`, `credit = max(0, min(inactive, file_backed) - speculative) * page_size // 2`. `free_ram_bytes` is `raw + credit`. The receipt includes raw page observations, raw free bytes, credit, pressure, page size, and policy string. Missing or malformed optional cache counts and missing, malformed, warning, or critical pressure provide zero credit. Required free/speculative counts must parse as nonnegative integers. Linux continues to use `MemAvailable`. The existing 1.5 GiB incremental RSS cap, 2 GiB headroom floor, 0.75 reserve gate, disk guard, and live guard are unchanged. The heuristic deliberately counts only half of a bounded file backed inactive estimate; it is not an operating system guarantee of instantly available memory.

The `run()` call for `timing_k16` now passes `retryable=True`. `StageLedger` already retains the failed generation and bytes, requires identical input and output hashes, and uses the first running generation's start plus the original 1,800 second timing allocation. No general retry policy or protected stage behavior changed. The original global policy remains 21,600 seconds from its first start.

## New standalone run04 witness

The ignored SDD helper `.superpowers/sdd/2026-10-16-famjet/e2e-run04-resume-witness.py` is prepared for root promotion; SHA-256 and its fake repository evidence are in [verification.json](e2e-cache-memory-resume-evidence/verification.json). It extends the previously rejected witness with:

- Exact Python executable bound to the resolved invoking `sys.executable`, followed by `-m famjet_poc run --out OUT --resume`, with OUT matching the monitored old directory.
- A root authored hash reference to the exact old OUT file set and every byte, original revision `27dc49a0f61a12e9cf319d20c6cc9aeefe2a84dc`, and all numeric/E3/config/lock source bytes. The sole immutable source exemption is `famjet_poc/pipeline.py`; report modules are immutable. It requires a clean exact new HEAD before and after execution.
- A chained public ledger ending in failed `timing_k16`, completed `development_k16`, matching first timing start, and no freeze or protected stage. It checks the original 1,800 second timing and run policy global allowances before creating PREP and again immediately before `Popen`. Expiration rejects before any child or ledger mutation.
- The same conservative Darwin cache estimate as the pipeline, with raw page/pressure/credit fields in its admission receipt. Its output cap includes all old OUT bytes and new PREP bytes, and it monitors only its new child process group.
- An external work deadline bounded by the original **global** clock, not the timing stage clock. The inner ledger enforces the timing clock during timing; a successful timing stage can be followed by later work.

The helper does not construct the actual baseline, read protected outputs, or execute the actual study. The earlier `e2e-resume-witness.py` and original f7 process witness remain historical and unchanged.

## RED and GREEN evidence

Before the observer fix, seven new Darwin observer cases failed with missing `raw_free_ram_bytes`/`cache_credit_bytes`; the first raw low memory case could not admit. The original `timing_k16` call had no `retryable` keyword. After the bounded changes, [affected-pytest.stdout.log](e2e-cache-memory-resume-evidence/affected-pytest.stdout.log) records **142 passed, 1 skipped** across pipeline, resources, CLI, report inputs, report, scientific report, transfer, and resume tests. The skip belongs to the existing affected suite. The direct observer cases cover low raw memory with half credit, file backed only, anonymous inactive only, warning/unknown/missing pressure, invalid or missing cache statistics, speculative subtraction, and unchanged admission caps. Existing ledger tests cover failed bytes, first start, and protected retry rejection; the new entrypoint check pins `timing_k16` to explicit retryability.

The [fake repository summary](e2e-cache-memory-resume-evidence/fake-repo/) contains 20 stdlib subprocess cases with exact argument vectors, exit codes, times, raw stdout/stderr logs, and byte SHA-256 commitments. Positive cases prove a new owned process group, clean changed pipeline HEAD, old byte and clock preservation, conservative cache admission, and a child continuing past timing's deadline after launch without a false external kill. Negative cases reject existing OUT without baseline, changed old bytes, changed numeric source, wrong baseline hash, protected ledger, wrong OUT or missing resume, altered clock, extra/symlink old output, missing immutable file, existing PREP, expired timing/global clock, arbitrary executable, warning pressure, and missing cache statistics. No actual model or protected data was loaded.

The [verification receipt](e2e-cache-memory-resume-evidence/verification.json) records each exact command, UTC start/end, exit, raw log size and SHA-256. Compilation and committed diff check both exited zero. `git diff --name-only 27dc49a0f61a12e9cf319d20c6cc9aeefe2a84dc HEAD` lists only `famjet_poc/pipeline.py`, `tests/test_poc_pipeline.py`, and `tests/test_poc_resources.py` before this report commit. The unchanged source IDs comprise `famjet/**/*.py`, every `famjet_poc/*.py` other than `pipeline.py`, `requirements.lock`, `docs/reporting-requirements.lock`, `docs/research/e2e-study-config.json`, `docs/research/e2e-development-resource-policy.json`, `configs/manifests/beijing_v2_targets.json`, and `docs/research/e2e-inference-qualification.json`. Source, configuration, locks, rates, seeds, metrics, model, training, timing producer, and protected qualification bytes were not edited.

## Files created or changed

| File | Purpose |
| --- | --- |
| `famjet_poc/pipeline.py` | Darwin estimate/receipt and timing retry flag |
| `tests/test_poc_pipeline.py` | Observer and exact timing entrypoint tests |
| `tests/test_poc_resources.py` | Existing mocked Darwin observer updated for pressure query |
| `docs/research/e2e-cache-memory-resume-design-plan-amendment.md` | Dated bounded design, plan, and amendment; mirrored in SDD |
| `docs/research/e2e-cache-memory-resume-report.md` | This report; mirrored in SDD |
| `docs/research/e2e-cache-memory-resume-evidence/` | Raw verification logs, receipts, and disposable fake repository results |
| `.superpowers/sdd/2026-10-16-famjet/e2e-run04-resume-witness.py` | Ignored new witness awaiting root promotion |
| `.superpowers/sdd/2026-10-16-famjet/e2e-cache-memory-resume-test-witness.py` | Ignored stdlib fake repository checks |
| `.superpowers/sdd/2026-10-16-famjet/e2e-cache-memory-resume-record.py` | Ignored exact command evidence recorder |

## Root gate before any real resume

Root must independently review the helper and this report, bind its already authored baseline to the actual old run04 OUT and old revision, verify the exact clean new HEAD and source exemptions, verify old OUT bytes and stage/global clocks have remaining allowance, check the total existing OUT plus PREP budget, promote the helper, and choose whether to launch its own guarded resume. The first timing start is `1792890563.801858`, so its deadline is `1792892363.801858` (about 01:39:23.802 UTC); that clock is never reset. The original global end is about 03:41:39.663497 UTC. A review or launch after the timing deadline must remain HOLD and reject before child launch. No actual run04 resume was attempted here, and no scientific result is claimed.

## Fix round 1 — original global deadline on child exit

The scoped independent review found one blocking helper gap: the external monitor checked the original global deadline only inside its `while child.poll() is None` loop. A child exiting just after that deadline, before the next poll, could return 0 with no guard and be accepted against only the new wrapper deadline. This finding is valid. The original helper SHA-256 `d1fb1fdb48e9aa5ded8a1fb851698ddf027eed80230e8dc00b506e69d78a78e6` and its 20-case evidence remain historical.

The ignored helper now retains `original_global_deadline_epoch_seconds` in the baseline binding and admission/exit receipts, records `end_epoch_seconds`, sets `guard_failure=original_global_deadline` when finalization reaches or passes the old deadline, and requires `end_epoch_seconds < original_global_deadline_epoch_seconds` in its final success predicate. Fresh mode has no original global deadline. The new helper SHA-256 is `38c47eb064e23c1949f21560b49ebe30c9b708b0fe3fac6f5819659f4a78391f`. No tracked source, pipeline test, old run04 output, or original clock was changed in this round.

**RED:** The new `global_expiry_during_poll` disposable repository case delayed one monitor poll while the fake child exited after the original global deadline. Against the reviewed helper it failed as intended: the child returned 0, `guard_failure` was null, and the wrapper wrongly exited 0. The case also asserts that a real child marker exists, so an earlier prelaunch refusal cannot satisfy it.

**GREEN:** The same case now records child return 0, final `guard_failure=original_global_deadline`, wrapper exit 1, clean source, and `end_epoch_seconds=1792891348.203813` after the retained original deadline `1792891345.2139552`. A deterministic direct test of the helper's final predicate accepts `999.999` before a `1000.0` deadline, rejects equality and `1000.001`, and preserves fresh mode with no original global clock. The original 20 fake repository cases remain green. The covering test file is `.superpowers/sdd/2026-10-16-famjet/e2e-cache-memory-resume-test-witness.py`.

Exact commands, selected output lines, and the full raw logs with byte SHA-256 are in [fix round 1 verification](e2e-cache-memory-resume-evidence/fix-round-1/verification.json):

```text
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python /Users/artemlegotin/Documents/git_alter/FAM-Jet/.superpowers/sdd/2026-10-16-famjet/e2e-cache-memory-resume-test-witness.py
global_expiry_during_poll PASS
21 fixture cases passed
exit 0

/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python -m py_compile /Users/artemlegotin/Documents/git_alter/FAM-Jet/.superpowers/sdd/2026-10-16-famjet/e2e-run04-resume-witness.py /Users/artemlegotin/Documents/git_alter/FAM-Jet/.superpowers/sdd/2026-10-16-famjet/e2e-cache-memory-resume-test-witness.py
exit 0
```

The earlier 142 passed/1 skipped affected source suite was not rerun because this round touched only the ignored helper and its fixture. Status remains **HOLD** pending root's scoped re-review and any actual resume decision; no actual resume was launched.
