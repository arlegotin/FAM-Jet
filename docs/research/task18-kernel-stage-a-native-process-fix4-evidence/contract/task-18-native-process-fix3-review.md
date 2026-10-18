# N1: NOT ADDRESSED to acceptance

**SPEC: Needs fixes. QUALITY: Needs fixes.** Successful boundary ingestion now uses actual sample intervals and the authorized adjacent charge correction. One residual N1 path remains when copying `authority_end` fails: later final reconciliation can still attribute a post-end sample using the stale active phase. The current copy-failure test stops before reaching that attribution because its memory cap is lower than the conservative failure charge.

Scope: `1b0bb18aed81bcb88a0faec5f6d56397fb2de5d7` → `6ae27aa9ceacd83905d47de60bfee5961cf752e1`, N1 and new fix breakage only. F1/F2, earlier accepted I1 mechanisms, the six preflight findings and the held lifetime design were not reopened.

## What is corrected

- `validation/kernel_stage_a/monitor.py:288` makes early numerical recovery independent of the mutable authority flag and ordinary role charging. It preserves raw maxima and marks newly seen PIDs unresolved at `:293`.
- `validation/kernel_stage_a/monitor.py:345` retains the actual numeric root RSS with its pending sample. Reconciliation at `:454` records the RSS of an interval classified as authority, and `:274` uses that attributed peak rather than the root's whole-lifetime peak. This implements the specifically authorized adjacent correction.
- `tests/test_kernel_stage_a_native_process_fix3.py:14` covers post-end baseline500 with no prior authority observation and with genuine prior authority60. The retained successful final specimens report authority0/60, raw peak500, baseline500 and worker increment0. They establish the successful-ingestion N1 correction.
- `tests/test_kernel_stage_a_native_process_fix3.py:63` supplies a positive overlapping interval and an additional later unbaselined500 sample. The retained final specimens preserve authority80 while retaining the larger raw/final conservative cost500. This checks that the fix does not simply omit genuine authority cost.
- `validation/kernel_stage_a/monitor.py:484` makes a failed semantic/proof-copy path retain the known per-PID sum conservatively. The retained F1 specimens still report980, and the minimum emergency specimen retains full70 and refusal labels. No numerical recovery or cap increase is used to authorize identity.

## Important — residual N1: failed boundary copying still permits later stale-phase attribution

**Locations:** `validation/kernel_stage_a/monitor.py:429`, `:454`–`:457`, `:484`; `tests/test_kernel_stage_a_native_process_fix3.py:14`, `:17`–`:21`, `:39`.

The new failure handler sets `conservative=True` when semantic identity/provenance processing fails. This correctly preserves full known costs, but it does not invalidate the authority phase used by `reconcile()`. The new attribution block at `monitor.py:454` still updates `authority_phase_peak_bytes` and `authority_worker` whenever classification returns `authority_worker`, independently of that failed-boundary state.

The existing copy-failure control supplies a concrete path:

1. `authority_start` is already ingested, so semantic `phase.active` is true.
2. The complete journal then contains `authority_end`, a sample starting strictly after that end, and baseline500.
3. Copying `authority_end` raises `_MonitorStop('output cap')`. Its semantic cursor has advanced, but the phase-end state update has not happened. Numerical recovery has retained500, and `failure()` conservatively charges500.
4. During final recovery, semantic ingestion resumes after the failed end event and can collect the following sample/baseline. The phase still has no admitted end. Reconciliation therefore classifies the post-end sample against the stale active phase and the new attribution block records500 as authority RSS.

The test currently sets `incremental_bytes=100`. Its second outer sampler call returns an empty batch before the source sample is collected. On final reconciliation, the already-conservative500 charge exceeds100 while processing that preceding empty batch, so reconciliation stops before reaching the post-end sample. This makes the authority0/60 assertions pass without exercising the remaining attribution branch. With the same controlled journal and an incremental cap above500—for example1000, without changing the production limit—the early stop no longer masks the later authority500 attribution. This is a source-supported path; no additional test or native execution was performed or claimed.

The returned run remains stopped and the full failure cost is retained. The defect is incorrect phase-specific evidence, not an observed false COMPLETED verdict. It nevertheless violates the binding requirement that attribution follow actual sample intervals and ordered boundaries, and the new README/report claim that failed boundary copying retains conservative costs without inventing attribution.

**Required correction:** prevent a failed or unavailable semantic boundary from authorizing new authority-specific attribution during later reconciliation. Retain any previously established authority peak and the full conservative known RSS sum, and keep failed/unresolved provenance explicit. Do not repair the missing boundary by assuming the stale active flag is current. Strengthen the existing copy-failure parameterization with a cap above the recovered500 so final reconciliation must reach the post-end sample; it must retain full conservative500 and authority0/60. Keep the positive overlap control and F1/F2 controls. This is the same narrow boundary-failure requirement, not a request for a broader accounting or lifetime redesign.

## New-breakage assessment

No independent new Critical or Important finding beyond the residual N1 path above is established. The deferred ordinary-charge concern was considered from the supplied code; no separate supported production regression was established, so it is not promoted to a finding. No additional Minor code defect is identified.

## Evidence, checks and limitations

- Read the root fix3 brief, full prior review and full final implementation report, including its packaging correction. Read the supplied exact three-path authored-source diff. Used the full review package only to extract retained test summaries and final specimen verdict fields, without rereading bulk archival numeric records or regenerating Git output.
- `docs/research/task18-kernel-stage-a-native-process-fix3-evidence/final-focused.txt:1` records **64 passed, 24 deselected, 2.93 s**. Saved summaries also show the initial four N1 failures, the two intermediate unresolved-role failures, corrected focused results and the justified final covering run. These results support the exercised branches but do not cover the below-cap failure-reconciliation branch described above.
- The final specimen verdicts substantiate the reported successful0/60 authority values, positive overlap80, conservative copy-failure500, preserved F1 recovery980, emergency70 and explicit FAILED/incomplete-source cases. Their full byte inventories/hashes, the380-file audit,204-artifact/203-mapping records,33 surviving specimen directories,173 unchanged prior files, clean main and package identity are controller-provided verification; this reviewer did not repeat those audits.
- The report explicitly discloses that pytest pruned transient RED/first-GREEN/corrected-GREEN specimen roots4354–4356. Their raw logs survive, but those early output directories and exact earlier whole-test-file snapshots are not byte-preserved. This is an archival limitation relative to the brief's preservation request, not evidence that the final retained runs failed. No reconstruction or rerun is requested or claimed; the controller owns acceptance of that disclosed limitation.
- No outside-diff source inspection was needed in this round. No tests, benchmarks, native probes, scientific work, Git mutation, source edit or subagent dispatch occurred. Only this requested review report was written.
- No fresh native image observation, full native Stage A pass, ordinary-reader viability or scientific readiness follows from the synthetic controls. F1/F2 remain closed except for any future demonstrated new breakage; the conservative Python ESRCH policy is unchanged. Lifetime work remains HELD, all scientific nulls remain unreleased, and source/scientific acceptance remains the root's responsibility.

## Scoped verdict

**N1: NOT ADDRESSED to acceptance. SPEC: Needs fixes. QUALITY: Needs fixes.** The successful-boundary and adjacent-branch correction is soundly supported. The existing boundary-copy-failure control must reach final attribution below the memory cap, and that path must preserve conservative costs without extending the failed authority phase.
