# I1: NOT ADDRESSED to acceptance

**SPEC: Needs fixes. QUALITY: Needs fixes.** The main I1 mechanisms—incrementally charged evidence, settled-sample reconciliation and bounded finalization—are implemented and supported by focused evidence. One Important new failure path in event ingestion still violates the fix requirement to retain late inner RSS on failure. One Minor requirement gap loses the explicit raw-refusal label in the emergency verdict.

Review scope: `a0353ba6cb51b453e49929aa7c7d0a48b3f86ace` → `6ba6100de56ad983920a07f067e6f460840081b9`, I1 and new breakage in that fix only. No old preflight findings or unchanged native identity policy were reopened.

## Strengths / I1 mechanisms addressed

- `validation/kernel_stage_a/monitor.py:193` bounds JSON encoding to available bytes; `:204` overwrites the preallocated verdict instead of appending an unbounded report. `:223` reserves verdict space inside the existing cap, and `:239` charges accepted JSONL records immediately and rolls a partial append back to its prior complete-record boundary. Accepted raw observations are separated from subsequent resolutions.
- `validation/kernel_stage_a/monitor.py:332` accounts direct observation RSS before raw encoding and marks rejected raw batches explicitly. `tests/test_kernel_stage_a_native_process_fix1.py:21` verifies accepted prior samples/witnesses, rejected oversized identity, retained RSS and the complete directory size under a small cap. The retained `bounded/monitor.json:1` records two accepted sample batches, one rejected observation and its full RSS.
- `validation/kernel_stage_a/monitor.py:390` processes new/affected pending batches and `:425` removes settled batches. Negative helper-lifetime metadata is separate from proof for any new sample. The settled and pending controls at `tests/test_kernel_stage_a_native_process_fix1.py:49` and `:186` test actual classification counts and late declaration resolution, rather than just asserting implementation structure.
- Deadline checks bracket collection, affected reconciliation and final work. `validation/kernel_stage_a/monitor.py:520` bounds the candidate summary, `:526` measures completed first encoding, and `:535` prevents a final write crossing the deadline from leaving a returned COMPLETED verdict. The explicitly named timing boundary and caller-measured final commitment are within the root's ruling. Controlled classification/encoding/commit crossings and cleanup/error controls are meaningful; no full-runtime timing conclusion is inferred.
- `validation/kernel_stage_a/authority.py:209` admits exactly the five root-authorized initialized filenames. The new test at `tests/test_kernel_stage_a_native_process_fix1.py:118` rejects an extra name and a missing reservation. No wildcard allowance, numerical protocol or cap increase appears in the fix diff.
- Existing native tests now read complete raw/resolution records from the evidence log; their identity and RSS assertions remain. The changed overflow test additionally checks the actual directory fits its budget. The normal-exit Python ESRCH policy and separate held design are unchanged.

## Issues

### Critical

None identified in this scoped re-review.

### Important F1 — Exhausted evidence space can prevent already-written inner samples from being numerically accounted

**Locations:** `validation/kernel_stage_a/monitor.py:310`, `:314`, `:343`, `:352`, `:353`, `:357`, `:358`, `:480`, and `:485`.

`read_events()` advances `event_offset` before processing a complete event. A helper declaration writes another witness record to the evidence log **before** storing the declaration in memory. If that append fails at the output cap, the outer loop stops with the cursor already beyond the declaration. Finalization resumes at the next event. For the ordinary inner-baseline sequence `observer_helper`, `observer_helper_end`, `observer_sample`, `baseline`, it now encounters a completion whose declaration was never stored. `completion()` raises `ambiguous helper completion`, aborting the final event pass before the `observer_sample` is read.

The inner raw sample is already durably present in the charged `monitor-events.jsonl`, but its RSS never reaches `collect()`/`numeric()`. The final conservative fallback uses `rss_peak_sum`, which includes only previously ingested PIDs; it cannot recover that missed inner observer/worker charge. The same coupling can arise when appending other already-persisted source-event duplicates exhausts the remaining evidence space. This is a new resource-accounting failure caused by the bounded representation, not a reopening of the old native exit policy.

The exact precondition is a complete inner event sequence on disk with insufficient residual evidence capacity for its first duplicated witness. This is a source-level control-flow finding; I did not run a new test or claim it occurred in the saved specimens. Existing cap tests reject a direct outer sample and existing late-inner tests have ample space, so neither exercises this intersection.

**Required correction:** decouple numerical/failure accounting for already-written source events from successfully duplicating their provenance into the evidence log. After cap/serialization failure, use a bounded failure reconciliation path that can account complete available inner sample RSS without treating a skipped declaration as a reason to abandon later numeric records. Keep identity unresolved where proof could not be reconciled, retain full RSS, and explicitly distinguish copied/accepted evidence from source evidence or refused metadata. Preserve the existing cap and deadline. Add a focused controlled cap-at-inner-declaration/completion case with the outer sampler missing the inner observer, and assert its numerical charge survives in the bounded durable verdict. No native or scientific rerun is required.

### Minor F2 — Emergency verdict omits the required bounded refusal/completeness label

**Locations:** `validation/kernel_stage_a/monitor.py:296`, `:438`, `:538`; `docs/research/task18-kernel-stage-a-native-process-fix1-evidence/minimum/monitor.json:1`; `tests/test_kernel_stage_a_native_process_fix1.py:242`.

`refused()` builds the required refusal reason/count/RSS and `raw_identity_complete:false` metadata, but `emergency()` drops all of it. The saved 512-byte specimen proves the resulting verdict contains the STOPPED reason and full RSS70, but no rejected-observation count, raw-evidence completeness flag or refusal label. Its evidence file is empty, so the required label is not preserved elsewhere. The existing test checks bounded size and RSS but does not check this requirement.

This does not turn the result into a pass or lose the specimen's aggregate RSS; it is a smaller explicit reporting-contract gap. Preserve a minimal bounded refusal/completeness indicator and numeric refusal summary in the emergency commitment when refusal occurred, within the existing reservation, and assert it in the minimum-budget control.

## Checks and limits

- Read the fix brief, full implementer report, executable/test/documentation portions of the supplied diff and the relevant saved verdicts. Used the supplied diff for exact new-line references and extracted saved test summaries; no regenerated diff, Git command, source mutation, broader source crawl or outside-diff source check was needed.
- The final raw output at `docs/research/task18-kernel-stage-a-native-process-fix1-evidence/final-focused.txt:1` records **51 passed, 24 deselected, 2.47 s**. The saved RED/GREEN/cover summaries agree with the report; no warning summary appears. No tests, benchmarks, native probes or scientific work were rerun.
- The five retained controlled specimens support their claimed bounded bytes and normal tested branches. Artifact/hash/package/clean-HEAD validation and complete byte inventories are controller-provided checks, not independently repeated by this reviewer. Raw pytest whitespace and preallocated JSON padding are intentionally preserved; their packaging check exit2 is documented, while source-only check exit0 is separate.
- No new native functionality, full native supervisor pass, ordinary reader-completion viability or scientific readiness is established by these synthetic controls. All scientific nulls remain unreleased. Conservative later-Python-ESRCH failure remains intentionally unchanged and is not a finding in this fix review.

## Assessment

**I1: NOT ADDRESSED to acceptance; main growth/work/finalization mechanisms addressed, but F1 blocks closure of the required failure-accounting behavior. SPEC: Needs fixes. QUALITY: Needs fixes.** F1 should be corrected with a narrow failure-ingestion change and focused synthetic control; F2 is a bounded reporting correction. No broader native-policy change or repeated scientific validation is requested.
