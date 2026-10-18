# Terminal lifecycle fix1: scoped re-review

18 October 2026. Reviewed prior HEAD `4815000fef3060f88518a8577713a0085aebb1f4` through delivered HEAD `aea79458d645e0fa586501488067b0054fef689e`, with source/test commit `75c0d0f4913388668e71444156ae3e63bee032db`.

**R1: ADDRESSED. R2: ADDRESSED.**

**SPEC verdict: PASS for the scoped R1/R2 corrections.**

**QUALITY verdict: PASS for this fix diff.** No new Critical, Important or Minor findings identified in the corrections or their directly affected test expectations. These verdicts close the two findings from the earlier source review; they do not establish native compatibility or constitute root acceptance/scientific release.

## R1: helper termination and independent reap after wait failure

Checked `validation/kernel_stage_a/monitor.py:365`–396 and the six new helper failure controls in `tests/test_kernel_stage_a_terminal_lifecycle.py:245` onward.

The previously missing branch now retains the initial wait error, attempts helper termination when no prior termination was attempted and the owning returncode is still None, and independently attempts another owning wait. Both waits calculate their timeout from the original `bound`; there is no new grace window. Termination remains an immediate attempted syscall even when the original allowance is exhausted. The cached integer returncode guards against signaling a reaped PID. A prior drain error still causes termination, and `kill_attempted` prevents a duplicate signal. Kill denial does not bypass the independent wait. The final witness continues to derive reaped status and returncode from the actual owning object; subsequent successful reap cannot erase the initial failure or make the observation complete.

Read the six `helper-outcome.json` specimens from the final scoped cover. They corroborate the source and report:

| Case | Recorded operations | Final outcome |
| --- | --- | --- |
| remaining | wait(0.5), kill at 100.1, wait(0.4000000000000057) | Incomplete query; reaped true, returncode -9; initial wait failure retained. |
| exhausted | wait(0.5), kill at 100.5, wait(0) | Incomplete query; reaped false, returncode null; actual end 100.51 and timeout/error costs retained. |
| kill_denied | wait(0.5), attempted kill at 100.1, wait(0.4000000000000057) | Incomplete query; denial and first wait error retained despite subsequent owning returncode 0. |
| reap_failed | wait(0.5), kill at 100.1, second failed wait | Incomplete query; reaped false, returncode null; both wait errors retained. |
| already_reaped | two waits, no kill | Incomplete query; truthful returncode 0; no released numeric PID signal. |
| read_error | kill at 100.0, two waits | Incomplete query; no duplicate kill; read and initial wait errors retained. |

These are explicit deterministic process seams. They demonstrate correction of the identified missing call path, without claiming that a real native helper failure was reproduced.

## R2: primary violation survives emergency finalization

Checked `validation/kernel_stage_a/monitor.py:883`–914 and 1023–1034, the seven new emergency controls, and the changed existing finalizer assertions.

The independently encoded emergency result now selects the existing primary `reason` before the later finalizer failure. It retains a separate bounded `finalization_failure` string and a factual `cleanup_failure_count`. With no earlier primary, the finalizer failure supplies the primary reason. Failure status, conservative known RSS, refusal/accounting flags and timing boundary remain in the emergency payload.

The local ASCII quoting code handles quotes/backslashes, control characters, BMP Unicode, non-BMP surrogate pairs and lone surrogates without invoking the failed normal JSON encoder. It budgets escaped output against the existing reservation, bounds primary and secondary diagnostic text, and marks truncation. The fallback uses the existing independent fd write and preallocated verdict file; it does not call the failed `_commit_monitor` path or create another output allowance.

Read all six finalizer `monitor.json` specimens from the final scoped cover. The three prior-cap cases retain exact reason `incremental worker memory cap`, STOPPED status, actual returncode -9, conservative incremental RSS 500,001,024 B, cleanup failure count 2 and separately escaped OSError/_MonitorStop finalization text. The three no-earlier-primary cases use the finalizer failure as primary, remain STOPPED, retain actual owning returncode 0 and conservative known RSS, and separately record the diagnostic. Each retained verdict file is exactly 8,192 bytes. The source tests assert returned/durable equality through the shared exercise.

The minimum-reservation specimen is exactly 512 bytes and parses successfully. Its quoted/control/Unicode/lone-surrogate primary round-trips intact; its long separate secondary text is visibly truncated. The corresponding test retains the total 1,024-byte output cap and returned/durable equality checks.

The three adapted existing finalizer expectations are appropriate: their missing post-import baseline violation precedes the injected encoding/write/metadata error. Preserving that primary and checking the separate later OSError follows the binding first-failure requirement. Their reap, known numerical cost, output and durable-result checks were retained; no identity guard was relaxed.

## Review work and evidence boundary

Read the fix1 review brief first, the binding fix brief, original R1/R2 findings, the complete 22,014-byte fix report, the independent root verification record and the exact three-authored-path source supplement. Inspected the corresponding current production code and focused test changes. Root's intervening document-only `7055537` and the future terminal-row amendment are not implementation scope for this re-review.

Read the full final scoped-cover log and selected decisive retained specimens listed above. The log reports **55 passed in 0.64 s**: 46 lifecycle cases, eight directly relevant finalization cases and one report-overflow case. The report and independent root record preserve the earlier R1 6-fail/6-pass and R2 failed/7-pass attempts; these failures remain historical evidence rather than being relabeled as passes. This is not an all-repository or all-133-test result.

Relied on the supplied independent root audit for all 433 new entries / 4,323,447 B, 254 original specimen mappings, 4,615 prior entries / 62,606,889 B, source hashes, final-cover source equality to `75c0d0f`, unchanged identity ASTs and package digest `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`. No archival re-audit was repeated.

No tests, native controls, project imports, scientific operations or subagents were run during this re-review. Read-only standard-library JSON parsing was used to inspect archived specimens. No source or Git mutations occurred; this report is the only artifact written. No concrete uncovered doubt required further execution.

## Remaining operational gate

Native compatibility remains **NEEDS_CONTEXT; survivor NOT RUN**. The first historical attempt failed multiline display identity and reaped root -9 after cancellation. The corrected file-input attempt established real live file-vector proof and actual natural root exit 0/end before reconciliation, but its retained `<defunct>`/ESRCH/RSS0 terminal row still produced STOPPED / foreign process identity under the unchanged strict policy. Neither historical survivor objective was reached.

This fix does not implement a terminal-row policy amendment. Its synthetic passes do not satisfy the independent native gate, release the failed original setup, authorize another native attempt or reopen scientific/protected work. The existing sampled-RSS, parent/supervisor exclusion, identity and physical emergency-write limitations remain. Root acceptance is a separate decision.
