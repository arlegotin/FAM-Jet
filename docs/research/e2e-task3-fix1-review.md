# E3 FIX1 scoped rereview — 24 October 2026

**SPEC: NO**  
**QUALITY: NEEDS FIXES**

The original I1–I5 findings and voluntarily patched M1/M2 are addressed in isolation. One Important regression introduced by the cache-admission fix prevents otherwise admitted resumptions. That regression is the sole blocker from this scoped rereview.

## Scope and evidence

Reviewed the original brief and amendments, the original review findings, the complete appended FIX1 report, and the changed source/test hunks in `e2e-task-3-fix1-review-package.md`, from FIX_BASE `764e3d305f29c8a04ed88bf509a2761e1834e8d1` to HEAD `c8f95d6a11bb2c078258a34315137d4a0927bdae`. Source changes are confined to cache, study and wire; the worker consumes the new content-bound limits through its existing `decode_request` call. The three changed test files were reviewed for coverage of these corrections.

The supplied `full-fixround1-final.json/.log` records **44 passed**, pytest **7.07 s**, wrapper **7.353596 s**, exit **0**, with all five numerical thread environment values set to 1. The supplied final compile record reports exit **0**. These are existing evidence, not independently rerun results. Root owns the separate raw-byte and preserved-path verification.

No tests, Git commands, benchmarks, protected-data access, source edits or subagents were used. This report is the only new authored artifact.

## Original findings

| Finding | Status | Source assessment |
| --- | --- | --- |
| **I1 — cache population identity** | **ADDRESSED** | `famjet_poc/study.py:676–691` compares the ordered history/spec-hash pairs and membership in declared specs. `study.py:700–705` binds existing probe output to its manifest/allocation. Changed-seed and incompatible-probe regressions cover the original identity defect. The newly added disk-ceiling comparison has the separate integration regression R1 below. |
| **I2 — diagnostic-policy resume** | **ADDRESSED** | `study.py:296–302` centralizes diagnostic policy construction. `study.py:754–792` checks each row's expected primary/diagnostic policy, scope, method and inventory hashes, rejects duplicates and requires the complete full-query union. The added mixed-eligibility persist/reload/audit test covers the original rejection. |
| **I3 — preallocation wire admission** | **ADDRESSED** | `famjet_poc/wire.py:42–49`, `wire.py:93–250`, `wire.py:341–419` bind finite caller limits into the request identity, enforce them in both producer and decoder, and precheck registered static/snapshot/query layouts and the snapshot digest before reconstruction. The decoder uses the carried limits bounded by the worker maxima, so leaving `worker.py` unchanged does not preserve the original bypass. New tests cover the 256-byte caller limit, declared child limit, extra payload, byte-valid wrong layout, both ridge families and registered bounded controls. |
| **I4 — renewable wall allocation** | **ADDRESSED** | `study.py:221–233` rebases admission from a durable first-start epoch and the larger previous elapsed admission. `study.py:811–833` persists/uses that clock and checks admission before cache reopening. Additional checks precede fits and history/worker batches. The helper fake-clock test and expired-resume integration test cover the original renewal. The stated continuous-wall policy conservatively also charges time between invocations. |
| **I5 — JSON-size selection tie** | **ADDRESSED** | `study.py:386–394` selects by `active_static_bytes`, and `study.py:917–922` obtains it from the loaded model's parameter ledger while retaining `wire_static_bytes` separately. The added tie regression makes differing wire lengths irrelevant to the configuration-hash tie break. |
| **M1 — ignored lower LRU ceiling** | **ADDRESSED** | `famjet_poc/cache.py:252–253` rejects a requested training LRU ceiling different from the shared cache ceiling. The added regression checks the smaller-ceiling rejection. |
| **M2 — incomplete prefix cost record** | **ADDRESSED** | `study.py:961–965`, `study.py:979–996` measure encompassing fit/preparation/save/load and row-persistence time and record standalone/amortized views using the candidate shared-cost allocation. This is a source correction; production cost values remain unmeasured. |

## New breakage in FIX1

### Important R1 — resume counts an existing cache against free disk space a second time

**Introduced check:** `famjet_poc/study.py:686–689`, particularly `limits['disk_bytes'] < cache.disk_bytes`.

**Affected callers:** probe cache admission at `study.py:712–723`; development cache admission at `study.py:834–846`. `_admit` at `study.py:208–218` already measures every existing output file when calculating `remaining_disk_bytes`.

On cache reuse, `_cache_for` now treats the supplied disk ceiling as a total allowable cache size. Its callers supply remaining free workspace bytes, after the already-existing cache has been included in the workspace total. A cache that occupies more than the remaining free space is therefore rejected even though it is unchanged, fits its configured cache ceiling, and the whole output directory is within the allocation.

A concrete source-derived example is a 1,000,000-byte phase allocation with 700,000 existing output bytes, including a 600,000-byte training cache, and a configured cache ceiling of at least 600,000 bytes. `_admit` correctly reports 300,000 bytes remaining. The development caller passes that value to `_cache_for`, whose new comparison rejects the existing 600,000-byte cache. No extra 600,000-byte write is needed. This example was reasoned from the inspected code; it was not executed as a test or experiment.

The same problem applies to the development cache and to same-manifest probe reuse. It is newly introduced by the FIX1 comparison, rather than an untouched observation or a demand for production feasibility evidence. It breaks the required resume behavior under a valid finite disk allocation.

**Required correction:** distinguish the configured total cache ceiling from the incremental disk allowance for new writes. For an existing validated cache, enforce the total cache ceiling and whole-directory phase admission without subtracting its bytes twice. For construction or genuinely additional files, retain the remaining-space bound. Preserve the new spec/hash/LRU checks and the direct rejection of a cache exceeding its actual configured ceiling.

Add a focused caller-level regression where the existing training/development cache remains within both configured cache and total phase limits, but its size exceeds unused phase disk space. Reuse must proceed without regenerating or rewriting the episodes. The current new cache test checks a genuinely lower explicit cache ceiling, and the new development-resume test stops on expired time before reaching cache admission; neither covers this integration case.

### Critical / other Important / Minor findings in the fix diff

No Critical finding and no additional actionable finding identified in the scoped changes.

## Separate out-of-scope / cannot-verify ledger

- No new untouched-source issue is promoted into this fix round. Earlier requirements outside I1–I5/M1–M2 were not reopened.
- Production feasibility, real 40-fit/46-panel costs, protected evaluation and a full timing campaign remain unallocated and unverified. The reported 44-test run does not establish those outcomes.
- The existing lifetime-peak memory proxy remains distinct from current whole-tree RSS, physical concurrency and inference workspace. Root's separately allocated whole-tree monitoring remains required for actual execution; its absence is not the reason for this source verdict.
- Root separately verifies evidence raw bytes and the 78 preserved source paths. This review does not claim an independent repository-history audit or the later complete executable freeze.
- Source acceptance of the new implementation would not repair or reclassify historical failures.

**Disposition:** correct R1 and rereview that narrow integration change. Do not repeat unrelated reviews or allocate science merely to resolve this source-level disk-accounting regression.
