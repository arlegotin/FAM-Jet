# Task 18 Python lifetime compatibility: SPEC and QUALITY review

**Verdict: changes requested — one Important integration defect.** No Critical issue found. This is a task-scoped review of BASE `d698a5e422d6b55148bb795f0ad0bd86d9c5e10b` to HEAD `dcd0a4f1265314485577637860b427e97a992b5e`, including source commit `18c7753e982b9ea2a8d6191a35970c5151403ab7`. It does not reopen accepted native I1, accept the branch, or authorize scientific work.

## Scope and evidence

Read the complete task brief, including its root status clarification; the complete adopted design; and the complete implementer report. The original HELD prerequisite is satisfied by the root's explicit release from accepted I1. The STOPPED clarification is binding: a failed worker must retain its failure/return code, without requiring a new monitor status enum.

Reviewed the supplied five-path authored-source diff covering `authority.py`, `monitor.py`, `production.py`, the new deterministic tests, and the exact native-control script. The diff cut the supervisor's charging, reconciliation, and finalization functions; read their surrounding bodies to trace late-event accounting and persistent failures. One focused outside-diff check read `commands.py` to verify the delegated exact-reader-vector/deadline validation. Read the root verification record and selected final covering log. Did not regenerate Git diffs, crawl the broader codebase, reread archival specimens, run tests/native controls/project imports, or modify source. This requested review artifact is the only write.

The selected raw final test log records **96 passed, 24 deselected in 4.36s**. Root's separate artifact verification records 1,201 manifest entries (974 regular files, 226 symlinks, one FIFO), 2,822,799 regular-file bytes, 1,114 original specimen mappings, and nine attempts. Those exhaustive archive/hash checks are root evidence, not independently repeated by this reviewer. Source-first/native/evidence sequencing and clean-main claims likewise rely on the supplied package and root verification rather than a new Git audit.

## SPEC compliance

| Requirement | Assessment |
| --- | --- |
| Narrow source-owned Python launch witness, exact vector/hash, PID/parent/role, pre-Popen time; launcher separate from framework image | Satisfied in the reviewed source. `authority.py:90` rechecks the resolved launcher and binds the explicit runtime image separately. Root and reader witnesses are attached to their actual Popen PID. |
| Exact root command and existing reader vector/deadline; no generic Python admission | Satisfied. `monitor.py:64` validates launch records against the exact stage vector or existing reader-vector helper; `monitor.py:192` retains exact display/image/parent classification. The focused commands check confirms canonical finite reader deadline validation. |
| ESRCH only, same-generation applicable image proof, trusted reaped completion, lifetime overlap, honest evidence labels | Satisfied at the generation/classification layer. `monitor.py:100`, `monitor.py:117`, and `monitor.py:160` require matching completion/proof/times and reject other native failures. Original ESRCH image evidence remains, with an explicitly source-owned attribution and proof reference. |
| Root proof only while owner unreaped; reader proof from its own tagged baseline observer row | Satisfied in reviewed paths. `monitor.py:129` gates root proof; `monitor.py:134` selects the one emitter self row, and `_self` excludes root self-emitter proof. `monitor.py:315` adds emitter/self tags without changing worker entry behavior. |
| Reject duplicate/reused generations, overlapping readers, unmatched final evidence, contradictory samples; no PID-only carry-forward | Satisfied in the reviewed state machine and failure paths. Duplicate IDs/PIDs and overlapping ownership fail; pending unbound events are checked at finalization. Contradictory classified observations enter the supervisor's persistent failed set (`monitor.py:616`), and semantic failures disable further attribution. |
| Bind post-import reader baseline to the same generation; support bounded delayed event joins through supervisor accounting | **Not fully satisfied: Important issue L1 below.** The generation object joins the baseline correctly, but supervisor accounting can miss that completed join after a native sample has settled. |
| Raw evidence and full RSS precede attribution; pending full charge and established cap violations remain | Satisfied by inspected numeric ingestion, append-only journal, pending charge, and monotonic peaks (`monitor.py:384`, `monitor.py:468`, `monitor.py:479`). The baseline defect causes an additional conservative false stop; it does not erase an established cap violation or undercharge memory. |
| Preserve one owned dispatch, exact stdin/env/files/cwd/original deadline, truthful cleanup and failure | Satisfied in the scoped change. `production.py:29` performs one Popen/communicate and emits actual reaped status/return code; `production.py:208` keeps the single ledger dispatch with the existing vector and payload. Remaining time is recomputed after witness work. `monitor.py:738` preserves nonzero execution as STOPPED rather than COMPLETED. |
| Retain bounded incremental representation and original scientific limits; no numerical/schema/package changes | No scoped violation found. New joins use per-generation state, a current-reader pointer, and bounded-journal dependencies; no all-history reconciliation or final JSON expansion was added. Only the five reviewed authored paths changed in the supplemental source diff. Unchanged package identity is supported by root's artifact verification. |
| Focused deterministic controls, committed-source native sequence, two genuine normal exits/real ESRCH, no numerical work | Substantially satisfied by the supplied tests/script and recorded evidence, with the supervisor ordering gap below. The script has explicit retained-ps-row synchronization, invokes the real native image lookup after natural reap, and keeps deliberate worker failure distinct from identity compatibility. |

## Strengths

- The extension has a clear, narrow identity boundary. A prior generic outer reader observation cannot become reader generation proof; successful post-reap root observations cannot establish root proof; never-proved Python remains pending/failing.
- Launcher and runtime image identity are distinct, and the admitted row continues to report actual ESRCH instead of being relabeled as kernel image success.
- Source events, raw RSS, reconciliation, and persistent peaks remain separate enough to retain conservative accounting when semantic attribution fails. The new code does not reset the original clock or caps.
- The implementation report candidly distinguishes expected nonzero native execution from identity-only PASS and discloses that these controls are not a complete native supervisor/candidate/resource pass. Failed intermediate attempts and old evidence are retained.
- Tests cover several important negative cases: duplicate generations, absent proof/end, wrong image/parent/display, out-of-lifetime evidence, post-reap root proof, baseline mismatch, timeout cleanup, and launch-witness write failure. The existing strict no-generation-proof coverage was not removed from the supplied change.

## Issues

### Critical

None found within this review scope.

### Important

**L1 — A successfully joined late reader baseline can be lost to supervisor accounting after the last reader sample settles.**

Primary location: `validation/kernel_stage_a/monitor.py:537` (reader baseline event handling). Related locations: `monitor.py:600` (only transfer of generation baseline to supervisor baselines), `monitor.py:625` and `monitor.py:631` (native pending-baseline observations deliberately do not remain pending), and `monitor.py:711`/`monitor.py:729` (final charging/missing-baseline failure).

The new reader event branch calls `python_lifetimes.baseline(event)` but does not publish the bound baseline into the supervisor's `baselines` mapping. That transfer happens only inside reconciliation of an entry for that PID. Native `pending_baseline` observations are deliberately settled and discarded, without a dependency that `wake(pid)` could reactivate. Consequently this valid schedule fails:

1. The exact reader launch and tagged successful self-image sample are read and reconciled before the separate baseline line arrives. The live reader row is `pending_baseline` and is then discarded from pending reconciliation.
2. The matching post-import baseline and trusted completion arrive within the original deadline. `PythonLifetimes` now contains the correctly bound baseline, but `wake(pid)` has no retained reader sample to revisit. The reader has exited, so subsequent outer samples need not contain its PID.
3. Final `charge(pid, final=True)` still sees no supervisor baseline. It retains `pending_baseline`, charges full native RSS, and reports a missing baseline/unresolved worker (or a cap failure), even though all required reader identity/baseline evidence is present before finalization.

This can also occur when a delayed launch is the event that completes an already-received self-row/baseline join. It is a conservative correctness regression, not an identity bypass: valid completed readers can falsely stop supervision, particularly when absolute post-import RSS exceeds the incremental budget. It violates the requested delayed-join compatibility and existing baseline accounting. Unlike a late event following an already-established cap violation, this schedule can fail with an otherwise generous cap and no prior violation.

**Required correction:** propagate each newly validated generation baseline into supervisor accounting when the join becomes available, regardless of whether another sample exists. Cover every event that can complete that join (baseline, self sample, or launch), and refresh the existing worker's charge without lowering historical peaks or clearing prior failures/cap reasons. This should remain a local incremental update; do not restore all-history scans.

**Focused verification recommended:** add one deterministic supervisor integration control that splits the observer self-sample and baseline across separate ingestion/reconciliation passes, removes the reader from subsequent samples, then delivers its valid baseline/end before finalization. Assert the final bound baseline and resolved reader status. Include the delayed-launch variant if the correction shares that join path, plus retention of any already-established full-RSS cap peak. Existing delayed-order tests operate on `PythonLifetimes` directly, and the sole new supervisor integration test exercises a root baseline through the unchanged direct-baseline branch; neither catches this reader transfer defect. No test was executed during this review; the finding follows directly from the inspected data flow.

### Minor

None requiring a separate change. The targeted integration test gap is part of L1 rather than a duplicate finding.

## QUALITY verdict and evidence limits

**Changes requested for L1.** The generation state machine and the narrowly owned dispatch are coherent, and the evidence package is unusually explicit about failed execution and nonnumerical limits. The missed handoff between the new generation state and existing settled-sample accounting prevents source acceptance of this revision as delivered.

Recorded native evidence supports two real ESRCH cases after natural reap, expected return codes 2 and 1, and a 2.031376834s single sequence including 0.991232084s import overhead. It uses a trusted harness parent for the reader. It does not establish a full native supervisor run, candidate-ledger/resource compliance, successful numerical readers, continuous image identity, arbitrary OS argv-byte identity, or absence of an unsampled exec. The latter remains the adopted trusted-source assumption. The package hash remains recorded as `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`.

No tests/native controls/scientific work were repeated here. No scientific release, factor/model construction, numerical read/request, acceptance, or self-release is implied by this review.
