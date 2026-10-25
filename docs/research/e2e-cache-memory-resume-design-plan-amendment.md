# E6 R5 cache memory and public timing resume amendment — 2026-10-25

**Status:** HOLD for root review and actual resume admission. This amendment changes resource observation and a preprotected public retry only. The E3 model, fit, benchmark producer, protected data, scoring, and source qualification are unchanged.

## Diagnosis and design

Run04 stopped at the `timing_k16` RAM admission after K16 development completed. The Darwin observer counted only free plus speculative pages. At the observed host state, a large file backed inactive cache was reclaimable under normal pressure, so that raw count understated admission headroom. Apple describes cached files as using memory that can be overwritten; the half credit below is our bounded heuristic, not an Apple guarantee. The normal pressure flag value `1` comes from Apple's [kernel pressure translation](https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/bsd/kern/kern_memorystatus_notify.c) and [dispatch flags](https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/bsd/sys/event_private.h).

For Darwin only, parse finite nonnegative integer `vm_stat` page counts and require free and speculative counts. Set `raw = (free + speculative) * page_size`. Under `sysctl -n kern.memorystatus_vm_pressure_level` exactly `1`, set `credit = max(0, min(inactive, file_backed) - speculative) * page_size // 2`; otherwise credit is zero. Missing or malformed optional cache statistics and unknown or unavailable pressure yield zero credit. The existing `free_ram_bytes` admission input becomes `raw + credit`; receipt fields separately retain page observations, raw bytes, credit, pressure, and the estimate policy. Linux `MemAvailable`, the 1.5 GiB RSS cap, 2 GiB minimum headroom, 0.75 RAM fraction, disk reserve, and continuous live guard stay as before.

The pipeline marks only the existing `timing_k16` call as retryable in this amendment. `StageLedger` still compares its original input hash and failed output bytes, keeps failed generations, and charges a retry to the first timing start plus the original 1,800 seconds. The original run policy clock stays fixed. A failed protected stage stays blocked.

The new standalone run04 witness is prepared in the ignored SDD folder for root promotion. It checks a root authored hash bound baseline of every old output byte, an exact original revision, all immutable source/config bytes except `famjet_poc/pipeline.py`, a chained public ledger ending in failed timing, completed K16 development, the original timing start, the original global run policy, a clean expected new HEAD, the exact monitored CLI with the invoking Python executable, and fresh disjoint PREP. It rejects exhausted timing or global allowance before child launch and rechecks immediately before launch. Its own resource admission uses the same conservative Darwin estimate. Its external process deadline remains the allocated wrapper limit constrained by the original **global** clock; the inner `StageLedger` enforces timing's own deadline while timing runs, allowing later stages to continue after successful timing completion. It monitors and can stop only its new process group.

## Bounded implementation plan

- [x] Reproduce the low raw free plus cache admission failure and the missing `timing_k16` retry flag.
- [x] Add failing tests for normal pressure cache credit, zero credit cases, and exact timing retry call.
- [x] Change only the Darwin observer and `timing_k16` call; preserve all hard limits.
- [x] Prepare a new run04 witness and disposable fake repository checks for prelaunch gates, unchanged old bytes and clocks, exact executable, cache admission, and post timing child lifetime.
- [x] Run affected pipeline, resource, CLI, report, transfer, and resume tests; compile and inspect the diff.
- [ ] Root verifies the actual old baseline, remaining clocks, clean expected HEAD, and helper review; root alone decides whether to execute a real resume.

## Amendment boundary

This is a resource accounting correction plus authorization of one preprotected failed public timing retry. It does not establish a scientific result, excuse the failed attempt, reset any clock, alter old output bytes, or assert that a real resume has occurred.
