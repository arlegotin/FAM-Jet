# Task18 source-owned helper lifecycles — source-only report

Disposition: **HOLD. Final affected cover FAILED: 335 passed, 1 failed, 6 deselected.**
Implementation and static native inputs are committed as `34143e8c47728d65c098003724bfc8f1c2a0a5f4` from clean base `100bf1c900e955d855267ba86d11c94948dcd3dd`. Independent source and full-control review remains required. No native control, model, factor, numerical read, fixture/reference operation, setup or scientific retry was executed. Earlier failures remain unchanged.

## Contract and source connections

The adopted amendment is `docs/amendments/2026-10-18-source-owned-helper-lifecycles.md`; the architecture report and stopped03 report/E69–82 were read. The implementation adds `validation/kernel_stage_a/source_lifecycles.py`, a stdlib finite-generation registry shared by ordinary observer ps, numeric cleanup ps, both authority Git commands and reader launches. The owned root participates in collision detection, while its existing receipt remains separate.

The registry retains immutable launch fields, unique launch IDs/PIDs across families, family, source references, actual matching ends/reap/returncode, observation bounds and optional measured peak. `monitor.py` connects source journal launch/end ingestion, supervisor declarations, cleanup and Python generations. Declaration references retain original journal offsets or supervisor evidence offsets. Final charged `source_lifecycle` records join parent generation, completion and per-PID measured peak; a never-observed helper has null peak, not demonstrated zero cost.

`process_tree` launches and communicates/kills/reaps its retained Popen and now publishes that object's actual returncode in both the returned witness and end event. Numeric cleanup uses its retained Popen and the common registry, including global collision checks. Authority Git and `owned_reader_dispatch` already publish matching actual ends from their retained Popen; those source files are unchanged. No serialized dictionary is represented as a kernel-owned receipt. Direct supervisor evidence is distinguished from parent-reported source evidence.

An unambiguous nonnegative integer RSS row overlapping launch through actual completion can be attributed on genuine ordered macOS ESRCH, regardless of raw teardown spelling, with no prior live image of the helper. The current image is `image_unavailable`; `kernel_image` requires actual matching successful lookup. Source family/vector/artifact, phase, parent generation and reader deadline constraints remain. Successful helper images retain exact known display requirements. Present contradictory parent images/timing still fail, while absent or exited parents may use their retained qualified generation. Completion and observation time, rather than arrival order, determine compatibility.

Global duplicates, declared reuse, cross-family claims, missing/contradictory ends, malformed native lookups, impossible/nonfinite chronology, wrong source/vector/parent/artifact/phase and wholly late rows remain failures. Known-reader live display contradictions cannot fall through to unknown-child pending handling. Unknown children get only the existing bounded source drain, then stop. No sampler, delay, retry, grace or budget was added.

All observed helper RSS, including positive stale rows and cleanup, is charged fully with baseline zero under the existing peak aggregation. Pending lifecycle evidence grants no certification or baseline credit. Completed reader lifecycle without genuine baseline qualification is a full-charge `reader_lifecycle`, not a baseline-bearing worker. Existing SELF/live-image/baseline, clean launch, closed request, candidate/deadline, result/count and isolation gates remain. Nonzero completion is attributable cost, not operation success; authority success additionally requires actual zero helper statuses. Existing root receipt methods are AST-identical, and their test file is unchanged.

This is trusted-source attribution for bounded experiments, not continuous image proof, adversarial PID-reuse exclusion, exact death-time observation, an unsampled peak bound or universal native compatibility.

## Actual verification and failures

All pytest invocations used the absolute repository `.venv/bin/python` through `.venv/bin/python /private/tmp/task18-source-lifecycle-capture.py LABEL ...`. Each invocation had a fresh task-owned `/private/tmp/task18-source-lifecycle-LABEL-*` basetemp. `capture.py`, every full command/environment, pre-run UTC/monotonic timestamp, post-run timestamp, actual child exit and complete combined stdout/stderr are retained in `docs/research/task18-source-owned-helper-lifecycles-evidence/`. The inherited VIRTUAL_ENV pointed elsewhere; the executed interpreter was explicitly the repository venv, never PATH Python/Anaconda.

| Attempt | Actual pytest result | Exit | External seconds |
|---|---|---:|---:|
| red01 | 12 failed, 20 passed in 0.09s | 1 | 0.259001 |
| green01 | 32 passed in 0.05s | 0 | 0.194621 |
| green02 | 46 passed in 0.10s | 0 | 0.205617 |
| cover01 | 60 failed, 272 passed, 6 deselected in 2.08s | 1 | 2.182787 |
| diagnostic01 | 13 failed, 296 passed, 6 deselected in 1.90s | 1 | 2.006700 |
| diagnostic02 | 5 failed, 160 passed, 5 deselected in 0.41s | 1 | 0.524848 |
| diagnostic03 | 9 passed, 84 deselected in 0.09s | 0 | 0.199257 |
| green03 | 51 passed in 0.10s | 0 | 0.246625 |
| cover02 | 4 failed, 332 passed, 6 deselected in 2.36s | 1 | 2.510972 |
| cover03 | 1 failed, 335 passed, 6 deselected in 2.30s | 1 | 2.445707 |

The exact commands and complete failure node IDs are in `attempt-index.json` and each LABEL.json/LABEL.log. Focused commands selected `tests/test_kernel_stage_a_source_lifecycles.py -q` (later `-ra`). Covers selected the existing nine files: `owned_root_terminal`, `terminal_attribution`, `terminal_lifecycle`, `python_lifetime`, `python_lifetime_fix1`, `native_process`, `native_process_fix1`, `native_process_fix2`, `native_process_fix3`, each under `tests/test_kernel_stage_a_*.py`, plus the new focused file. The unchanged selector was:

```text
-k 'not python_launcher_is_rechecked and not owned_dispatch_once and not monitor_root_generation_reconciles and not git_launch_witness_write_failure' -q -ra
```

RED01 produced twelve intended behavior failures, rather than missing imports. It covers stopped03-shaped `(ps)`/3850240 B, forwarded exact display/1802240 B, arbitrary displays, overlapping completion, fast helpers, both Git vectors and reader full-charge attribution. Final focused coverage adds source reordering, global collisions/cleanup reuse, actual mocked-Popen status publication, missing end/source gaps, positive-RSS cap, cleanup failure and unmeasured cleanup. Existing tests cover numeric cleanup/truncation/cap/cleanup-error boundaries and root/baseline negatives.

Cover01 exposed 60 failures: simulated fixtures lacked the new current-protocol status/ordered lookup fields, old assertions encoded superseded reader/parent attribution, and implementation mistakes changed root-negative fallback or mutated retained cleanup launch dictionaries. Those source mistakes were corrected without changing root-negative assertions. Diagnostic01 retained 13 failures, including current-parent timing validation, stale parent/reader semantics, cross-family fixtures and two accidentally over-broad test-text edits affecting root expectations; those root expectations were restored. Diagnostic02 retained five failures caused by duplicate `method` keywords in simulated reader images; diagnostic03 verified the corrected nine cross-family cases. No failed invocation is discarded.

Fixture changes explicitly supply simulated actual returncode and ordered native method/reason/timestamps; they do not recover missing historical statuses. Superseded assertions now distinguish source attribution from reader baseline credit, allow retained genuine parent proof independently of current sample object/arrival, and charge pending authority cost without certifying authority attribution. Arbitrary reader teardown display moved from a negative to the new positive controls. Genuine contradictory-image/chronology/source/root negatives remain.

Cover02 retained four failures. Three led to concrete source/fixture corrections: known-reader bad live display was incorrectly pending; incomplete-end fixtures incorrectly said already reaped; an undeclared row after owner completion still expected pending. The fourth, repeated by final cover03, is the unchanged `tests/test_kernel_stage_a_native_process_fix2.py::test_unrecoverable_source_journal_is_failed_with_incomplete_accounting[partial]`.

cover02: outer_seconds 0.0883569159777835, returncode null, status FAILED, reason `outer timeout`; owning wait recorded TimeoutExpired. cover03: outer_seconds 0.08843000000342727, returncode null, status FAILED, reason `outer timeout`; owning wait recorded TimeoutExpired. The 80 ms real-sleeper control consumed its deadline before the owning wait could reap. The actual signal was attempted, the bounded wait failed, and cleanup remains incomplete in the retained verdict. The root ruled to preserve the assertion and both failures, with no standalone rerun, grace or budget change. **The covering run is FAILED, not a passing suite with an exception.** No later owning status is inferred. Independent review must assess this unresolved deadline/cleanup limitation before native allocation.

Pre-edit monitor/authority/production/README bytes and hashes were captured before RED, with UTC/monotonic provenance. Intermediate source/test revisions were not separately snapshotted; full run logs and final source are retained, so no claim of complete per-attempt source snapshots is made. `specimen-manifest.json` maps 46 selected task-owned specimen files (145806 bytes), including both cleanup failures, with original paths and original/archive hashes. No unrelated shared pytest tree or historical 8k audit was copied. Initial unprivileged git staging failed exit128 on `.git/index.lock`; authorized escalation staged/committed successfully.

## Static native inputs and preservation

The NEW parent and worker were only read, AST-parsed and hashed, never imported/executed. Parent SHA256: `1dd6da9b8e281e73309666ce3f3eb7e85493e494876fd08e6141bae5a0c59020`. Worker SHA256: `14a1f41cd099fed3bfe553340e2cbdf174e2e4c005312a25fb6c5c9b976de254`.

The proposed one-parent 10 s allocation contains two at-most-4.5 s cases and the existing .25 s parent reserve, 192 MiB incremental RSS, aggregate 64 MiB output, 4 GiB disk and thread1. It uses real authority Git, imported runtime baseline ps, numeric cleanup ps and the actual clean reader dispatch with deliberately invalid `{}`. Expected reader schema rejection is a failed operation with no read/factor; empty result/counter output alone is not treated as proof without the actual rejection path. The unknown-child case retains genuine socket line, numeric membership, owned signal-before-end0/−9 and EOF-before-fallback. No favorable sampling loop or retry is designed. A future PASS means only observed compatibility/joins/cleanup, never inference or science. Destination/source/clock await separate allocation.

`static-audit.json` records AST success, `git diff --check` success, unchanged root-receipt method ASTs and protected-file diff. Package hash remains `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`; lock remains `2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1`. No math, rates, frozen metadata, fixture/reference, command/seal/limit or old evidence/input was changed. README documents source-only/native-unobserved status. Independent SPEC/QUALITY review and any native/science allocations remain separate. HOLD.


## Fix round 1 — current disposition

**HOLD for scoped independent rereview. Affected cover PASSED: 361 passed, 6 deselected.** Source fix commit `4cd3a1a0205509801899a272ae7a8bf2daf4ad95` follows clean `919c2c93c7b355cb41c239dff034a82645389970`. Original failed invocations and historical status remain unchanged.

I1: the registry checks child launch/completion against its parent on either declaration/end arrival, including later parent completion and never-sampled children; contradictions stay sticky. Sampled parent validation also bounds child completion. I2: one Git phase predicate now runs at declaration, completion, phase end, sampled classification and finalization. The final sweep uses the same retained parent proof/reader-baseline qualification as sampled helpers. Controlled unsampled positives and early-launch, late-completion and unqualified-parent negatives exercise actual supervisor ingestion.

I3: normal polling sleeps at most the remaining work/candidate interval, preserving the existing cleanup reserve instead of always sleeping 20 ms. The 80 ms allocation, reserve formula and assertions are unchanged. A deterministic clock control demonstrates the near-work-deadline wait allowance. The unchanged partial-journal assertion now passes with actual owning returncode −9. Its deliberately malformed-source operation remains **FAILED/outer timeout**, with incomplete timed accounting: outer_seconds **0.08068754198029637**, and cleanup `wait` diagnostics contain `_MonitorStop('outer timeout')` while appending wait evidence. This is not a successful 80 ms operation or complete cleanup evidence. Earlier null statuses are not recovered; root's separate current absence query cannot establish historical reap. No rerun/grace/budget extension follows.

I4: the static unknown control requires successful nonabsent SIGKILL targeting the exact unreaped root before its matching actual end. Existing membership/socket payload/EOF-before-fallback conditions remain. I5/M1: report (1 MiB) and timing receipt (2048 B) are preallocated inside the original aggregate 64 MiB before monitor allowances. Bounded serialization and in-place overwrites add no temporary duplicate. Oversized serialization, aggregate excess or expired deadline produces NEEDS_CONTEXT without discarding logs. The receipt records the actual post-report-write boundary; stdout records after all artifact writes, explicitly before stdout itself. Bounded failure writes do not grant extra time or a successful overrun claim.

Only isolated validation/commit functions were AST-extracted for controlled tests; native module imports, main and worker were never executed. The pre-fix AST guard/commit slices provided behavioral RED, without running native input setup. No native probe, model, factor, read or scientific invocation occurred.

### Fix verification and retained evidence

Every attempt used `.venv/bin/python docs/research/task18-source-owned-helper-lifecycles-evidence/fix1/capture.py LABEL ...`, an absolute repository-venv pytest child and fresh task-owned basetemp. Exact commands/environment, UTC/monotonic start/end, exit and full output are in `fix1/attempt-index.json` and each LABEL.json/LABEL.log.

| Attempt | Actual output | Exit | External seconds |
|---|---|---:|---:|
| red01 | 14 failed, 58 passed in 0.23s | 1 | 0.382583 |
| red02 | 2 failed, 2 passed, 68 deselected in 0.08s | 1 | 0.185154 |
| green01 | 76 passed in 0.18s | 0 | 0.286674 |
| cover01 | 361 passed, 6 deselected in 2.27s | 0 | 2.375580 |

red01/green01 selected `tests/test_kernel_stage_a_source_lifecycles.py -q -ra`; red02 added `-k unsampled_git`. cover01 used the exact ten-file cover and unchanged six-operation selector listed above. RED01 included thirteen intended behavioral failures and one fixture error: a nonexistent fake interpreter failed before Git validation. Replacing only that fixture's interpreter/hash with the repository interpreter exposed the two intended RED02 failures (early Git launch and unqualified parent), with valid/late-end controls passing. No failed attempt is omitted. Final cover includes all 76 focused controls.

`fix1/pre-fix-manifest.json` timestamps/hashes five actual pre-fix files. `fix1/specimen-manifest.json` preserves 40 selected files/117374 bytes: RED02 accepted bad Git lifetimes, final Git controls, deterministic reserve control and the actual partial-journal specimen. No shared historical tree was copied. Intermediate edits were not separately snapshotted. The static audit confirms protected files and root receipt AST unchanged; package/lock retain the full hashes above. No previous input/evidence, math, command, assertion or budget changed.

Current static parent SHA256: `3275a093357ca2618973690e03c55f407d2219e60eb68572343b08dc20d42198`. Worker remains `14a1f41cd099fed3bfe553340e2cbdf174e2e4c005312a25fb6c5c9b976de254`. Current monitor/registry/test hashes are retained in `fix1/static-audit.json`. The new native control remains unobserved; scoped I1–I5/M1 rereview and any native/science allocation remain separate. HOLD.
