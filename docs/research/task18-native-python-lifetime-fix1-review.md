# Task 18 Python lifetime FIXROUND1: scoped L1 re-review

**L1 verdict: resolved. SPEC compliance: PASS for the fix scope. QUALITY verdict: PASS for the fix scope; no new blocking issue found.** This is a review recommendation to root, not branch acceptance, native revalidation, or scientific release.

Reviewed FIXBASE `dcd0a4f1265314485577637860b427e97a992b5e` to HEAD `d746726729b075804857d6dc5993ea527d69eba4`, with source commit `1114388e891021cf83ba18eaba32e7dc5744ef9a`. Scope is the original L1 baseline-publication defect and newly introduced breakage in this fix. The earlier lifetime review and accepted native I1 were not repeated.

## Evidence and review boundary

Read the full fix brief, original L1 review, complete fix report, exact two-path authored-source supplement, root verification record, and selected raw final covering log. Inspected the new helper and its three event call sites against the previously reviewed charging and sample-settlement behavior. The source supplement contains only `validation/kernel_stage_a/monitor.py` and the new supervisor integration test file. No broader source crawl or archival reread was necessary.

The raw final log records **105 passed, 24 deselected in 4.67s**. Root's independent verification records 524 manifest entries, 461 actual specimen mappings, three preserved attempts, 11 verified frozen source hashes, all 974 prior regular files unchanged, and clean main. These exhaustive artifact/Git checks are root evidence, not repeated by this reviewer. The report preserves the RED attempt's two L1 failures and the separate overstrict cap-fixture assertion failure, explaining the latter's correction without rewriting the failed output.

No tests, native controls, project imports, Git commands, or scientific work were run during this re-review. No source was modified. This requested review file is the only write.

## L1 resolution

`validation/kernel_stage_a/monitor.py:441` introduces a local `publish_python_baseline(pid, final=...)` operation. It reads the affected generation's validated `baseline`, publishes it to the supervisor mapping, and refreshes an existing worker's charge immediately. Publication no longer depends on a pending or future sample containing that PID. It skips unchanged values and adds no registry or historical scan.

Every event capable of completing the generation/self-row/baseline join invokes it after validation:

- Tagged own observer sample: `monitor.py:538`, after `PythonLifetimes.self_sample`.
- Reader baseline: `monitor.py:547`, after `PythonLifetimes.baseline`.
- Reader launch: `monitor.py:558`, after `PythonLifetimes.launch`.

The former reconciliation-time copying loop is removed. For the original baseline-last and launch-last schedules, a settled native `pending_baseline` sample may remain discarded: the late join now updates accounting directly. Existing `charge` recognizes the validated baseline and resolves the worker without reopening an observation (`monitor.py:384`, `monitor.py:388`). Self-sample-last follows the same publication path while retaining its legitimate new source sample.

The helper's early guard rejects publication when source identity provenance is incomplete or the PID is already persistently failed (`monitor.py:443`). It copies the validated generation value, not the raw event's claimed RSS. The existing generation validation remains unchanged. Root/direct-baseline handling remains on its prior path, including its existing charge behavior.

## SPEC compliance

| Fix requirement | Assessment |
| --- | --- |
| Publish the completed generation baseline without requiring another sample | PASS. The three join-completing source events publish immediately and refresh only the affected sampled worker. |
| Preserve self-image, lifetime, post-import boundary, and generation validation | PASS. Publication occurs after the existing validation methods and requires an actual generation baseline. No image/lifetime admission rule was changed. |
| Keep failed provenance and persistent identity failure effective | PASS. Explicit guards precede publication, with integration controls for all three provenance-failure event orderings and a separate already-failed identity. |
| Preserve full pending charge, raw RSS, historical peaks, and established cap stops | PASS. The fix uses existing charge logic and does not reset peaks or reasons. The aggregate peak remains monotonic at `monitor.py:418`; the cap regression control retains the established stop. |
| Keep settled samples discarded; no new history scan, registry, or observation | PASS. The former per-entry copying loop is removed, and the helper performs constant-time lookups for one PID. Tests assert the actual sample/resolution counts. |
| Preserve root baseline, status, deadline/cap, dispatch, and numerical behavior | PASS within the fix diff. Root/direct publication remains unchanged in effect; no status, deadline, cap, dispatch, or numerical source is changed. |
| Add meaningful supervisor integration coverage, including adverse cases | PASS. Tests exercise actual journal ingestion, reconciliation, settlement, final charging, and serialized verdicts rather than calling the new helper directly. |
| Preserve historical native evidence and avoid an unauthorized rerun | PASS on reviewed source/report and root evidence. The report explicitly binds the prior native result to the old source and makes no fixed-whole-file native claim. |

## Test quality and strengths

`tests/test_kernel_stage_a_python_lifetime_fix1.py:102` parameterizes baseline-last, launch-last, and self-sample-last. The fixture checks that the preceding reader observation has already resolved as `pending_baseline` before the late event is supplied, removes the reader from later outer samples, and asserts the final worker role, validated baseline, zero unresolved workers, and exact sample/resolution counts. This directly covers the original defect at the supervisor boundary.

`test_kernel_stage_a_python_lifetime_fix1.py:115` checks mismatched RSS and failed provenance before each join-completing event. `test_kernel_stage_a_python_lifetime_fix1.py:124` separately preserves a prior classified identity failure while source provenance remains complete. This distinction tests both guards rather than allowing one failure mode to mask the other.

`test_kernel_stage_a_python_lifetime_fix1.py:133` creates the conservative full-RSS cap stop before delivering valid late evidence during cleanup. It asserts the persistent peak and cap reason without requiring the bounded reconciler to finish every pending sample after stopping. That is the appropriate contract; the report clearly identifies and preserves the original overstrict assertion.

The repair is small and localized. It fixes the missing state transfer at the point the join becomes available, keeps one validated source of the baseline value, and does not add retained observations to work around settlement.

## Newly introduced issues

- **Critical:** none found.
- **Important:** none found. Original L1 is resolved.
- **Minor:** none requiring a change within this fix scope.

No concrete uncovered doubt justified another test run or native attempt.

## Out of scope and remaining evidence limits

This re-review does not re-audit the complete lifetime implementation, earlier native I1, excluded production modules, scientific protocol, or archival tooling. Root's record confirms unchanged `PythonLifetimes` AST and package digest `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`; those checks were not independently repeated here.

The earlier two-case native sequence remains historical evidence on source `18c7753e982b9ea2a8d6191a35970c5151403ab7`, with expected failed worker return codes 2 and 1. The repaired monitor's whole-file bytes were not native-rerun. New evidence establishes the controlled supervisor baseline handoff, not a complete native supervisor/candidate/resource run, successful numerical readers, or scientific feasibility. The adopted sampled trusted-source identity limitations remain unchanged.

Both scoped SPEC and QUALITY verdicts are PASS. Root retains acceptance authority; scientific results and allocation remain NULL/HELD.
