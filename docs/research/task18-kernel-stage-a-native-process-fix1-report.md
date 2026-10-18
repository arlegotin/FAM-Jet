# Task18 native process fix round1 — I1

**DONE_WITH_CONCERNS; ready for the same reviewer's scoped I1/new-fix-breakage re-review.** Source commit `2f3189b0c066d2571a7e50983fced1e13de6e5c3` on current main, based on clean `a0353ba6cb51b453e49929aa7c7d0a48b3f86ace`. Evidence is a separate subsequent commit, whose full hash is provided in the delivery message to avoid a committed self-reference. No source self-acceptance or scientific release occurred.

Root's fix brief and full independent review were read. I1 was reproduced: eight settled polls classified160 entries, growing raw observations were uncharged until final serialization, and controlled final encoding could cross the deadline yet persist COMPLETED. The fix addresses that representation/work/finalization boundary. The earlier six closed preflight findings were not reopened. The narrow identity admission functions, libproc mapping, exact display/deadline rules and launch vectors remain unchanged.

No native functional sequence was rerun. No scientific factor/model/read/reference/fixture/profile/dataset/corpus/panel/fit/train/calibration/bootstrap/protected execution occurred. Actual scientific factor constructions/reads: **0 / 0**. Focused controls use controlled samplers and simple sleeper/finish-file processes; existing authority controls also use their existing fake helpers/own-runtime identity observations. No new native ps/Git functional check was run. The original 0.867s native record remains explicitly about its original dirty snapshot, not this fix or a full supervisor/scientific verdict.

## Bounded evidence and resource representation

The supervisor now creates `monitor-evidence.jsonl` and a bounded preallocated `monitor.json` before launching the group. Root explicitly authorized the concrete integration dependency: authority's initialized-output inventory must contain **exactly** `stdout.log`, `stderr.log`, `monitor-events.jsonl`, `monitor-evidence.jsonl`, and `monitor.json`. No wildcard or generic filename allowance was added. Authority's new focused closed-inventory check rejects extra names and missing monitor reservation; the existing full synthetic authority launch control exercises its consumer.

The verdict reservation is `min(8192,max(512,output_bytes//2))` bytes inside the existing output cap, including whitespace padding. The initial readable JSON is `STOPPED` / `monitor incomplete`; it cannot be mistaken for completion. Inputs below512 bytes are refused before launching. The reservation and every event/evidence/log byte are charged from launch; no extra output allocation exists. Source defaults remain600s outer,90s candidate,201326592B worker incremental,67108864B output,4294967296B free disk and <=4 numerical threads.

Accepted raw sample batches, source witnesses/completions, runtime identity, source events, and separate sample-ID resolutions are appended and flushed incrementally. The evidence file, not a growing final JSON backlog, holds complete accepted native `comm`/`args`/lookup/lifetime records. The exact raw sample is written before identity mutation; resolution is a separate record. A partial append is truncated back to its previous accepted boundary, preserving prior complete JSONL rows.

Numeric RSS is accounted before raw encoding or event/identity handling. A batch that cannot fit is explicitly rejected: its bounded refusal has a reason, process count, RSS sum and `raw_identity_complete:false`. Its raw identity is not called complete or replaced by unlabeled truncation. Full sampled RSS remains in absolute totals, per-PID peak accounting, and conservative full-RSS charges. `observed_pid_peak_sum_bytes` and refusal RSS sums retain complete aggregate numerical charges even when all raw identity cannot fit; inline details are labeled incomplete when bounded. Accepted earlier raw records remain unchanged. Conservative sums can combine peaks from different instants and do not claim simultaneous allocator peaks.

`monitor.json` no longer embeds full `process_samples` or `source_launch_witnesses` arrays. It points to `monitor-evidence.jsonl`; accepted samples are `kind:sample`, witnesses `kind:witness`, and identities/roles `kind:resolution` keyed by sample ID. Inline worker details are limited to16 and include `workers_complete_inline`; phase details likewise have counts/completeness flags or a compact summary. A size-limited encoder rejects report growth before joining/writing an oversized report. The bounded verdict overwrites only its existing reservation, avoiding final temporary/report overlap and an unbounded rewrite/size fixed point. Normal metadata/encoding/write failures use an independent bounded emergency commitment after cleanup, with full numerical RSS and a STOPPED reason. Returned and stored JSON agree in tested normal, cap, timeout and error paths.

## Incremental reconciliation and identity policy

Every new observation is classified using its own actual image evidence. Settled raw batches leave reconciliation memory after their resolution is durably recorded. Pending batches have dependency indexes and revisit only when a relevant declaration/completion/baseline arrives. Scalar worker/helper RSS aggregates update incrementally; no settled history scan occurs before/after each poll.

A source launch-ID keyed pair of maximum observed sample/lookup bounds exists only for **negative helper-lifetime consistency**: a later completion contradicting a settled helper's sample invalidates it and stops without reclassifying every historic raw batch. This metadata never supplies image proof to a new sample and is not a Python/PID image-proof cache. Duplicate launch generations and contradictory completions still fail immediately. Authority phase end, live Git before helper-end, completed helpers, and kill-before-end charges remain covered. Late inner observer samples and declarations still resolve; per-PID peaks prevent duplicate sample charging.

Root explicitly retained the conservative Python ESRCH policy. Earlier successful image samples stay separate in the evidence log; a later missing-image/ESRCH sample still stops unresolved and does not borrow earlier proof by PID. Legitimate reader completion can therefore stop the diagnostic. This is a mandated viability limitation, not silently fixed by this round. There is no new lifetime/self-image protocol, family, generic framework or numerical/request/schema change.

## Time, finalization and cleanup

Collection reserves `min(0.1s,10% of the control's original remaining allowance)` **inside** the original deadline for finalization. Checks bracket collection/encoding, each affected reconciliation batch, event ingestion, and final per-worker reconciliation. A deadline reached during classification, summary encoding, or final write yields STOPPED; finalization cannot turn it into completion. Group kill/reap still runs for collection/serialization/write errors. Accepted raw evidence and complete numerical RSS survive finalization failures.

The returned `outer_seconds` is explicitly scoped by `timing_boundary`: it ends before the bounded final commitment, after completed reconciliation and the first bounded summary encoding. Final encoding/write cannot be included in a timestamp serialized before that future operation. Callers measure full elapsed through return. The control injecting a30ms final write verifies external caller elapsed exceeds the named boundary by at least20ms, and the separate commit-clock-crossing control proves a write that exhausts the original deadline cannot persist COMPLETED. There are at most a bounded candidate encoding, a final encoding and one deadline-adjusted encoding/emergency commitment; no timestamp/size fixed-point loop. Cleanup costs remain failed/charged elapsed, not a new allocation.

## Exact TDD and covering evidence

New-control command `N`:

```sh
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_native_process_fix1.py
```

Final covering command `C` (no full-suite rerun):

```sh
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_native_process_fix1.py tests/test_kernel_stage_a_native_process.py tests/test_kernel_stage_a_preflight_fix2.py tests/test_kernel_stage_a_preflight.py tests/test_kernel_stage_a_preflight_fix1.py -k 'native or monitor or authority or observer or baseline or f3 or f5 or same_interpreter or prospective'
```

All failed and successful saved outputs remain byte-for-byte under `docs/research/task18-kernel-stage-a-native-process-fix1-evidence/`, with scratch→durable hash mappings in the verification JSON. An intermediate covering summary overwritten by the final run is also listed below. No failure was omitted.

| Order | Command | Exit | Exact output summary | Raw artifact |
|---|---|---:|---|---|
| 1 | N initial RED | 1 | `5 failed, 1 passed in 0.24s` | `red.txt` |
| 2 | N finalization-time RED | 1 | `6 failed, 1 passed in 0.36s` | `red2.txt` |
| 3 | N initial GREEN | 0 | `7 passed in 0.39s` | `green-attempt1.txt` |
| 4 | C first cover | 1 | `6 failed, 38 passed, 24 deselected in 2.08s` | `cover-attempt1.txt` |
| 5 | C second cover | 1 | `2 failed, 42 passed, 24 deselected in 2.05s` | `cover-attempt2.txt` |
| 6 | N late-end/commit-time RED | 1 | `2 failed, 7 passed in 0.62s` | `red3.txt` |
| 7 | C third cover | 1 | `1 failed, 45 passed, 24 deselected in 2.24s` | `cover-attempt3.txt` |
| 8 | C fourth cover | 0 | `46 passed, 24 deselected in 2.15s` | `cover-attempt4.txt` |
| 9 | N pending/partial-write GREEN | 0 | `11 passed in 0.78s` | `green-attempt2.txt` |
| 10 | C minimum/caller-time GREEN | 0 | `50 passed, 24 deselected in 2.49s` | terminal summary; final output later replaced |
| 11 | N final-metadata RED | 1 | `1 failed, 13 passed in 0.89s` | `red4.txt` |
| 12 | C final GREEN | 0 | `51 passed, 24 deselected in 2.47s` | `final-focused.txt` |

The initial RED proved missing charged raw evidence, quadratic work, missing bounded error commits/closed inventory, and pre-finalization timing. First covering failures identified four old tests reading removed inline history, plus final missing-baseline charge and old oversized-report expectations. The tests now inspect the same complete raw/resolution evidence in the charged log; their identity/RSS assertions remain. The old output-overflow control now expects early `output cap` and additionally asserts directory bytes <=8192, replacing its old oversized-write expectation. Second/third covering failures caught finalization's overly broad conservative fallback changing resolved late charges, then a minimal fallback dropping optional worker detail on an already stopped timeout. Those paths now preserve known charges and the detailed bounded STOPPED verdict. Later RED controls proved negative consistency for late helper completion and deadline failure during final commit, and moved final metadata/hash errors inside the same bounded failure path. All named regressions pass in the final covering run, including old fix2 live/foreign/cap controls and the conservative Python ESRCH test.

Also exit0, no output:

```sh
.venv/bin/python -m py_compile validation/kernel_stage_a/monitor.py validation/kernel_stage_a/authority.py tests/test_kernel_stage_a_native_process_fix1.py tests/test_kernel_stage_a_native_process.py
git diff --check
git diff --cached --check
```

Evidence packaging `git diff --cached --check` returned exit2 for verbatim pytest whitespace and the exact preallocated verdict whitespace padding. Those raw bytes are deliberately preserved, not reformatted. The28305-byte diagnostic is saved as `packaging-whitespace.txt`; source-only checks remain exit0. No authored source/report whitespace failure is hidden by that raw-evidence result.

The source-only byte/hash audit returned exit0:

```text
PASS: package 15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050; all frozen/acceptance/native verification and18 raw prior artifacts byte-preserved
```

## Retained actual controlled specimens

Five final-run control directories are durably copied byte-for-byte under the fix1 evidence directory. Their full JSONL/reserved-verdict/event/log files and original→durable hashes are preserved; these are synthetic monitor controls, not native/scientific evidence.

| Specimen | Actual output bytes / budget | Verdict bytes | Actual outcome / counts |
|---|---:|---:|---|
| `bounded/` | 13031 /16384 | 8192 | STOPPED output cap; two complete raw sample batches and two source witnesses accepted;10 accepted log records/4606 evidence bytes; one20000-character raw identity refused; RSS500 retained, conservative incremental640 including prior helper peaks |
| `linear/` | 23901 /67108864 | 8192 | COMPLETED controlled sleeper; eight settled batches,16 classified process observations (prior reproduction160); absolute140, incremental130 |
| `pending/` | 24678 /67108864 | 8192 | COMPLETED controlled sleeper; eight pending batches,32 classified observations after exact declaration; no poll-only rescan; absolute140, incremental130 |
| `partial/` | 10036 /67108864 | 8192 | STOPPED monitor common failure; second sample's partial append rolled back; prior one complete sample retained; rejected RSS72, full incremental72; five accepted records/1688 evidence bytes remain readable |
| `minimum/` | 512 /512 | 512 | STOPPED output cap; readable independent bounded verdict; absolute/incremental70 fully retained; no raw observation falsely claimed accepted |

Controlled clocks separately exercised classification, final encoding and final commit crossing the deadline. Error injection exercised final metadata serialization, final JSON encoding, final Path commit, and a partial append. These are assertions over actual controlled behavior, not timing forecasts or native resource measurements.

## Changed inventory, identities and remaining authority

Executable source changes are confined to `validation/kernel_stage_a/monitor.py` and the concrete initialized-inventory helper/call in `authority.py`. `commands.py` and its exact vectors/hash rules are unchanged. Other source-commit paths: `validation/kernel_stage_a/README.md`, `tests/test_kernel_stage_a_native_process_fix1.py`, `tests/test_kernel_stage_a_native_process.py` (evidence reader only), and `tests/test_kernel_stage_a_preflight_fix1.py` (bounded-output assertion/expectation only).

The new `docs/research/task18-kernel-stage-a-native-process-fix1-verification.json` binds all six committed source hashes, package identity, exact tests/output/exit, raw log/specimen hashes, byte counts, operation/resource model and remaining nulls. This report is also durably copied to `docs/research/task18-kernel-stage-a-native-process-fix1-report.md`; the required `.superpowers/sdd/2026-10-16-famjet/task-18-native-process-fix1-report.md` remains the full equal report. The original report receives only an appended link to this fix; its earlier body remains an exact byte prefix. Existing native verification, raw RED/GREEN/native records and acceptance records are untouched.

Production package remains `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`. No `famjet/`, numerical source, lock/dependency, fixture, frozen metadata, cache/source guard or reader request/output numerical protocol changed. No new runtime/helper identity is claimed: the original native mapping/helper hashes remain prior evidence, and this fix adds no functional-native observation.

Scientific nulls remain `implementation_review`, `represented_rate_records`, `static_exports`, `resource_measurement_boundary_seal`, `fresh_launch_snapshot`, `output_directory`, and `root_stage_A_release`. Root owns source acceptance and any later changed normal-exit/lifetime design or scientific release. Current normal-exit ESRCH conservatism, path-file/mapped-byte limitations and sampled-RSS/allocator-peak limitations remain. If storage refuses both the normal and independent emergency write, a durable final artifact cannot be guaranteed; the error propagates after cleanup rather than returning a passing verdict. No full Stage A viability conclusion follows from these source controls.
