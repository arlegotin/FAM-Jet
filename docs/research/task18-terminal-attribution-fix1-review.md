# Scoped terminal attribution fix1 re-review

18 October 2026. **R1: ADDRESSED. SPEC: APPROVE. QUALITY: APPROVE.** No new Critical, Important or Minor finding was identified in this fix delta. These verdicts close the sole source finding in my original finite-task review; they do not certify native compatibility or release scientific work.

Reviewed prior HEAD `2fa298a5af3ed78b44f7ea50c56838e11498bffa` to HEAD `15326ea3bed42e94c6969137b8669ddc00d7282d`, source commit `919caa9ecdddcc8674c446c8d3f59400bca14f0a`. Scope was R1 and new breakage from its fix, as requested. The earlier finite-task review and accepted lifecycle reviews were not repeated or broadened.

## Why R1 is addressed

At `validation/kernel_stage_a/monitor.py:693`, central registration now rejects any PID already in `launch_pids`, independently of launch ID or source family. Successful registration updates both directions of the mapping. The entries survive completion, so a truthful old end cannot authorize a later generation to reuse that known PID. Existing launch-ID collision rejection remains in place.

Registration precedes family insertion for root/reader Python and both helper stores. At `monitor.py:694`, the rejection path first determines the incoming PID and any existing owner of the colliding launch ID. It marks and wakes every affected PID in one loop, then charges known PIDs in a separate loop. Thus a charging exception cannot prevent the other affected generation from being marked failed or awakened. Wakeups still target existing PID discovery keys and accepted generation dependencies; rejected generations do not replace those keys. Later events cannot clear the failed set or publish a new qualifying baseline for the failed PID.

At `monitor.py:268`, the direct literal-terminal seam rejects a PID present in more than one family store before the former Python-priority return. The normal end-of-classification failure update makes that rejection sticky even if a caller subsequently removes the conflicting table. The added observer and authority variants exercise this exact seam with an interval overlapping the old completion and new launch. This directly closes the wrong-generation selection from R1.

The change remains finite: one inverse registration map, bounded collision handling and a direct conflicting-store guard. It does not attempt birth-token reconstruction, choose the newest generation, or expand the separately scoped private numeric cleanup-query policy.

## Failure charging, evidence and pending rows

The retained failed cover and follow-up logs show two genuine intermediate regressions, not hidden successful checks. The first cover (219 passed, one failed) exposed a stale pending role after the earlier central rejection skipped old helper-store charging. The immediate-charge follow-up then reached the existing assertion that both attempted witnesses must be retained and failed there (10 passed, one failed). The current source corrects both without changing that existing test.

`declaration` now appends the attempted raw helper witness at `monitor.py:709`, then registers it, and only inserts into the family table at line 715 after successful registration. Retaining an attempted declaration therefore does not admit it. A refused journal write remains subject to the original output/deadline failure handling; no extra allowance is introduced. Python launch attempts already pass through the existing raw event append before registration.

I inspected the final retained specimen for `test_late_native_witness_reconciles_history_without_authorizing_reuse[True]`. It records STOPPED, helper role `unaccounted`, baseline 0, helper incremental RSS 100, total incremental RSS 120, and both witness launch IDs (`source-1`, `later-generation`). This supports the narrow charge/retention correction with actual preserved output.

The four new cross-family ingestion specimens also retain STOPPED with `ValueError: duplicate/reused source launch generation`. The reused PID is `unaccounted`, baseline 0 and incremental RSS 100. Their original sample-3 resolutions remain pending; none gains a favorable worker/helper resolution after the rejected launch. Tests additionally inspect the actual in-memory stores to require the original family entry to remain and the rejected second entry to be absent, then classify the original terminal row directly and require `unaccounted`.

The revised assertions are appropriate for interrupted finalization: they require failure, conservative known cost, exclusion of the rejected family and no later favorable attribution. They do not pretend that a second resolution was emitted when a later contradictory end interrupted reconciliation. The sticky failed set and direct rejection check remain substantive requirements.

The shared-ID/distinct-PID specimen retains both PIDs as `unaccounted`, each with baseline 0 and full known RSS 100, while the second helper declaration is excluded. Both distinct-PID/different-family positive specimens retain COMPLETED and resolve the original pending row to its proper family. This provides a positive boundary for the new global uniqueness rule.

## Evidence and review limits

Read my complete original review, the binding fix/re-review briefs, the entire 8,325-byte addendum, and the exact two-authored-path source supplement. Inspected the affected current registration, classification, charging and event-ingestion code, the new tests, relevant retained failure logs and decisive archived JSON specimens. The supplied full package remains the archival delivery; no archival crawl or broad repeat review was performed.

The corrected behavioral RED's retained reader→observer specimen demonstrates the original defect through controlled supervisor ingestion: COMPLETED, a reused PID treated as a worker with baseline 100/incremental 0, and sample 3 changing from pending to worker. The final corresponding specimen stops at registration and preserves full known charging. This is stronger source-only evidence than my original isolated local counterexample, but remains a mocked native-boundary test.

Read the final exact command and output: **220 passed, 6 deselected in 1.89s**, covering the changed attribution tests and the same directly related lifecycle/Python/native-identity suites. The unchanged exclusions remain the launcher/runtime recheck, owned dispatch, real-process lifetime seam and Git-launch seam. No test suite, native control or synthetic check was rerun by this reviewer. The only Python execution in this re-review parsed retained JSON using the standard library; it imported no project modules and performed no monitor execution.

Root's independent delivery verification was read and relied upon for delivery integrity, rather than duplicated: 1,669 new entries / 11,192,224 bytes, 204 raw symlink payloads, 1,444 original→archive mappings, 1,447 attempt-file hashes, five source hashes, final tested source equality, and preservation of 6,182 prior entries / 74,668,344 bytes. It confirms the package, lock, frozen native input and worker are unchanged. All nine actual attempts, including failures and assertion corrections, remain retained. These are root-verified delivery facts, not a second hash audit claimed by this reviewer.

No source, existing report/evidence, native input or Git mutation was made. Read-only Git status was clean before this report. This new review report is the only authored artifact. No subagents, numerical imports, scientific work or protected operation were used.

## Remaining gate

The original finite source task's sole Important R1 is closed, and no fix-created breakage was found in this scoped re-review. The frozen future native control remains unexecuted and requires its own separately authorized allocation. Native compatibility, continuous OS identity, security containment, unsampled peaks and scientific readiness are not established by these source tests or review. Protected/scientific work remains CLOSED.
