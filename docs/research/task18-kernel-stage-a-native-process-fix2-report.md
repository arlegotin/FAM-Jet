# Task18 native process fix round2 — F1 and adjacent F2

**DONE_WITH_CONCERNS; ready for the same reviewer's scoped F1/new-breakage review.** BASE was clean current main `6ba6100de56ad983920a07f067e6f460840081b9`. Verified source commit: `8bc8ef1884516fcd33237345e7ba30beb201d4a6` (`Retain late inner RSS before source proof copy failures`). Evidence is a subsequent separate commit; its full hash is returned in the delivery message to avoid a committed self-reference. No branch, worktree, push, subagent, source self-acceptance or scientific release occurred.

The round2 brief and full scoped fix1 review were read. I1's accepted main mechanisms were not reopened. F1 was reproduced exactly: a complete source journal contained inner RSS980, while failure duplicating its earlier declaration left the old verdict at70. The same loss occurred with witness-encoding failure. F2 was independently visible in the existing minimum-budget control: the emergency verdict omitted refusal/completeness fields.

No native functional sequence or scientific work was rerun. Actual scientific factor constructions/reads: **0 / 0**. No factors, model reads, fixture/reference/profile campaign, dataset/corpus/fit/train/panel/bootstrap/calibration/protected work occurred. Tests use controlled samplers and owned simple sleeper processes; existing focused authority controls retain their fake helpers/own-runtime observations. No new native ps/Git functional check, whole native Stage A pass, ordinary reader viability result or scientific readiness claim is made. The separate lifetime design remains **HELD**.

## F1 correction: numeric source accounting precedes copied proof

`monitor.py` now keeps a separate numerical cursor over `monitor-events.jsonl`. Before semantic event processing or copying a declaration/completion, a bounded pass scans the **new** complete source rows up to the file's current size snapshot. For `observer_sample`, it validates/retains PID/RSS numerical fields in the existing RSS ledger before advancing that numerical cursor. This pass does not append a duplicate, resolve identity, supply image proof, authorize a helper or change generation/lifetime policy.

The source journal is already charged output and remains the original raw evidence. Failure copying its earlier witness therefore cannot prevent a later already-written sample from reaching numerical peak/full-RSS accounting. The semantic cursor may still fail strictly on missing/unreconciled provenance; numerical completeness is independent of that failure. `source_event_accounting.complete/status/through_bytes/samples` records numerical recovery, while `identity_complete:false` labels failed semantic/provenance reconciliation. A semantic observer sample reuses its already-accounted numbers through `collect(...,accounted=True)`, avoiding double charging.

The pass is limited by the existing row-size/output cap, current source byte boundary and original deadline, checked per row. It is not an unbounded final drain, a new storage system, or another raw history. New source bytes are processed once numerically; no settled samples are rescanned or admitted by PID. Finalization attempts the same bounded numerical recovery before semantic failure handling. The old settled/pending work tests, late evidence controls, live/kill-before-end Git charges and exact native ESRCH control remain passing.

If the original deadline or unreadable/final-partial/truncated source journal prevents complete recovery, the verdict is explicitly **FAILED** and `source_event_accounting.complete:false/status:FAILED`. Known observed values remain reported, but do **not** certify a complete RSS bound. The code does not invent the unscanned900 RSS or turn incomplete recovery into a pass. Source truncation below the accounted cursor is detected explicitly. Numerical accounting tolerates absent identity parent fields long enough to retain RSS; identity admission remains strict and unchanged.

## Adjacent F2 disposition

F2 is addressed in the same bounded failure path. The independent emergency commitment retains `raw_identity_complete`, `refused_observations`, `refused_rss_bytes`, and `source_accounting_complete`. These do not require the normal JSON encoder or a larger reservation. The actual512-byte specimen contains a347-byte JSON payload with `raw_identity_complete:false`, refusal count1 and refused RSS70, plus padding. Its full absolute/incremental RSS70, STOPPED output-cap reason and durable/returned agreement remain.

No original cap/time/commit semantics changed:600s outer,90s candidate,201326592B incremental worker,67108864B output,4294967296B free disk, <=4 threads; the existing internal finalizer/space reserve stays inside those allowances. The exact five initialized filenames remain unchanged. `authority.py`, `commands.py`, all image/display matching and conservative later-Python-ESRCH policy are byte-identical to BASE. No self-image protocol or proof cache was added.

## Exact TDD commands and outcomes

Targeted command `N`:

```sh
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_native_process_fix2.py tests/test_kernel_stage_a_native_process_fix1.py -k 'late_inner_rss or unscanned_complete or minimum_failure'
```

New-file command `R`:

```sh
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_native_process_fix2.py
```

Final covering command `C`:

```sh
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_native_process_fix2.py tests/test_kernel_stage_a_native_process_fix1.py tests/test_kernel_stage_a_native_process.py tests/test_kernel_stage_a_preflight_fix2.py tests/test_kernel_stage_a_preflight.py tests/test_kernel_stage_a_preflight_fix1.py -k 'native or monitor or authority or observer or baseline or f3 or f5 or same_interpreter or prospective'
```

| Order | Command | Exit | Exact output summary | Raw artifact |
|---|---|---:|---|---|
| 1 | N RED | 1 | `5 failed, 13 deselected in 0.11s` | `red.txt` |
| 2 | N GREEN | 0 | `5 passed, 13 deselected in 0.05s` | `green-attempt1.txt` |
| 3 | C first covering | 0 | `55 passed, 24 deselected in 2.54s` | `cover-attempt1.txt` |
| 4 | R storage/partial/truncation controls | 1 | `1 failed, 6 passed in 0.24s` | `red2.txt` |
| 5 | C final covering | 0 | `58 passed, 24 deselected in 2.60s` | `final-focused.txt` |

All raw attempts, including both failed outputs, are byte-preserved in `docs/research/task18-kernel-stage-a-native-process-fix2-evidence/` with scratch→durable hashes. No full suite or native/scientific rerun was made. The first RED showed RSS70 instead of980 at declaration-cap/serialization failure, absent independent numerical completeness, absent FAILED status when recovery timed out, and the missing F2 label. The completion-cap intersection already retained RSS but lacked the new completeness contract. The second RED caught a truncated journal being mistaken for fully consumed; the explicit shrink guard fixes that failure. All named failures pass in the final covering output. Existing normalizer-free/late/baseline/partial-append/output/deadline/cleanup/native strict controls remain covered.

Also exit0, no output:

```sh
.venv/bin/python -m py_compile validation/kernel_stage_a/monitor.py tests/test_kernel_stage_a_native_process_fix2.py tests/test_kernel_stage_a_native_process_fix1.py
git diff --check
git diff --cached --check
```

Evidence packaging `git diff --cached --check` returned exit2 for the byte-preserved pytest output and reserved-verdict whitespace padding. The48334-byte exact diagnostic is preserved as `packaging-whitespace.txt`. Authored source/report checks remain exit0; raw evidence is intentionally not reformatted.

The source/frozen-byte audit returned exit0:

```text
PASS: package 15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050; authority/commands, frozen inputs, acceptance and all previous native/fix1 evidence/reports byte-preserved
```

## Actual preserved control specimens

The final run's eight control directories are durably copied byte-for-byte. The ordinary four-row sequence in each cap/encoding case is `observer_helper → observer_helper_end → observer_sample → baseline`. The outer sampler reports only root RSS70 and misses the inner observer. The already-written sample contains root RSS80 plus inner observer RSS900. Padding leaves exactly16 bytes of residual evidence capacity at the selected declaration/completion copy boundary; the raw source journal and accepted earlier rows remain intact. No scientific supervisor is run.

| Specimen | Actual output bytes | Reservation | Actual result |
|---|---:|---:|---|
| `declaration_cap/` | 16368 /16384 | 8192 | STOPPED; absolute980, per-PID peak sum980, conservative incremental980; numerical source COMPLETE, one sample/1560 source bytes; identity incomplete |
| `completion_cap/` | 16368 /16384 | 8192 | STOPPED output cap; absolute/peak-sum/incremental980; numerical source COMPLETE, one sample/1564 bytes; identity incomplete |
| `serialization/` | 10925 /16384 | 8192 | STOPPED monitor common failure; absolute/peak-sum/incremental980; numerical source COMPLETE, one sample/1564 bytes; identity incomplete |
| `unscanned_deadline/` | 9867 /67108864 | 8192 | FAILED outer timeout; source incomplete at byte0; known RSS70 remains70, not an invented900 complete bound |
| `storage/` | 9944 /67108864 | 8192 | FAILED read error; source incomplete at byte0; known RSS70 |
| `partial/` | 11605 /67108864 | 8192 | FAILED; source final row incomplete at byte0; known RSS70 |
| `truncated/` | 10382 /67108864 | 8192 | FAILED; shrink detected after accounted byte75; known RSS70 |
| `minimum/` | 512 /512 | 512 | STOPPED output cap; RSS70 full charge and explicit raw-refusal/count/RSS labels retained |

In the declaration-cap case, semantic finalization still rejects the unmatched completion because the declaration could not be copied/stored; the final reason is `monitor common failure`. This strict identity failure is intentionally preserved, while the earlier independent numerical pass has already recovered980. Completion-cap remains output-cap failure; witness-encoding failure remains monitor common failure. None admits the inner observer from missing proof. The tests assert the observer's baseline0/full charge900, unresolved role, bounded directory, readable prior accepted JSONL and returned/durable agreement.

These are actual synthetic evidence costs, not native memory forecasts. The original journal is charged; the new cursor adds no file or raw duplicate. Existing event/evidence duplication and bounded final-reservation padding retain their prior I1 cost model. All owned test children are killed/reaped on these stopping paths.

## Identity records, unchanged boundaries and remaining authority

Source changes are exactly `validation/kernel_stage_a/monitor.py`, its README, the new `tests/test_kernel_stage_a_native_process_fix2.py`, and two assertions strengthening the existing minimum-budget test in `tests/test_kernel_stage_a_native_process_fix1.py`. The source commit contains four paths. The new verification JSON binds their exact hashes and HEAD, all raw logs/specimens and mappings, actual byte counts, finding dispositions and nulls.

Required full report: `.superpowers/sdd/2026-10-16-famjet/task-18-native-process-fix2-report.md`; equal durable copy: `docs/research/task18-kernel-stage-a-native-process-fix2-report.md`. Verification: `docs/research/task18-kernel-stage-a-native-process-fix2-verification.json`. Prior reports are left entirely unchanged; this round does not amend or reinterpret their native/synthetic records. No old acceptance, prior raw evidence or verification JSON was rewritten.

Production package remains `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`. No `famjet/`, numerical/math source, lock/dependency, fixture definitions, frozen metadata, cache/source guard or reader numerical protocol changed. Both prior native/fix1 evidence directories, both prior reports/verifications, the preflight source acceptance, authority/commands and frozen input files compare byte-for-byte to BASE. Runtime/helper hashes are prior evidence only; no fresh functional-native identity is claimed.

Scientific nulls remain `implementation_review`, `represented_rate_records`, `static_exports`, `resource_measurement_boundary_seal`, `fresh_launch_snapshot`, `output_directory`, and `root_stage_A_release`. Lifetime design stays HELD. Legitimate Python exit before a later image lookup can still stop unresolved, as mandated; no earlier PID proof is reused. Existing sampled-RSS/allocator-peak, path-file/mapped-image, and storage-refusing-both-final-writes limitations remain. Root owns scoped source review/acceptance and any later viability/lifetime ruling or scientific release.
