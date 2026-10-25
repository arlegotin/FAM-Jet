# Terminal lifecycle fix round 1 — immutable linked addendum

Status: **DONE_WITH_CONCERNS** for the scoped R1/R2 implementation and evidence delivery; independent root/reviewer acceptance remains pending. This is a separate linked addendum to the [original lifecycle report](/Users/artemlegotin/Documents/git_alter/FAM-Jet/docs/research/task18-kernel-stage-a-terminal-lifecycle-report.md) and [file-control report](/Users/artemlegotin/Documents/git_alter/FAM-Jet/docs/research/task18-kernel-stage-a-terminal-lifecycle-file-control-report.md). Neither original report nor any of its hash-covered evidence was modified. The [full independent SPEC+QUALITY review](/Users/artemlegotin/Documents/git_alter/FAM-Jet/docs/research/task18-terminal-lifecycle-fix1-evidence/provenance/task-18-terminal-lifecycle-review.md) identified Important R1/R2; root verified both and dispatched only those corrections.

Source/test commit `75c0d0f4913388668e71444156ae3e63bee032db` is based on `4815000fef3060f88518a8577713a0085aebb1f4` on current main. It changes only `validation/kernel_stage_a/monitor.py`, `tests/test_kernel_stage_a_terminal_lifecycle.py` and the directly relevant expectations in `tests/test_kernel_stage_a_native_process_fix1.py`. Meaningful focused RED/GREEN evidence is retained for each finding, one at a time. The single scoped covering selection passed **55/55 in0.64s**. This is not a new all-repository/all-133 claim. Historical failed broad covers, native attempts and setup remain failed; native compatibility is still **NEEDS_CONTEXT** with both historical survivor cases **NOT RUN**. No native invocation or scientific allocation occurred in this round.

## Binding scope and chronology of authority

The fix1 brief was read first, then the full review, with receiving-code-review, systematic-debugging, TDD and verification instructions applied. Copies of the binding brief and complete review are retained under `provenance/` and hashed in the new manifest. R1 requires termination/reap attempts after helper EOF followed by failed owning wait, within the original helper allowance. R2 requires that an earlier primary violation survive failed final encoding/write with a separate bounded finalization diagnostic, including safe emergency text escaping independent of that failed boundary.

No defunct admission/classifier/proof/authority/commands/reader/math/config/data/dependency change is included. Parent/root separately committed document-only status/design material as `7055537` after this source commit. Those README/PROGRESS/DECISIONS and promoted terminal-defunct/source-review documents were left untouched and unstaged by this implementer; they are separate future source scope, not native/scientific permission in this fix. There was no branch/worktree, push, subagent/reviewer dispatch or self-acceptance by this implementer. Source and evidence were committed with explicit path staging only.

## R1: helper EOF is not owning completion

Verified original branch: clean stdout/stderr EOF left `errors` empty; initial helper wait then raised with returncode None, and the helper returned incomplete without ever attempting termination or another reap. The later worker group signal cannot reach this helper because it is in the supervisor group. The RED controls reproduced this missing cleanup at the actual new helper function with explicit pipe/owned-process seams and no real native child.

The fix tracks whether helper termination has already been attempted. A prior drain/read error still triggers immediate termination while the Popen is unreaped. If the initial owning wait raises, its original error stays first in the bounded error list. If termination has not yet been attempted and the helper is still unreaped, it is attempted nonblockingly; a separately protected owning wait then uses only `max(0, original_bound-current_time)`. No signal targets an already-reaped PID, no bound is renewed and no success/completion is invented. Actual kill and subsequent wait errors remain recorded, including elapsed failure cost. Successful later reap does not clear the initial wait failure or turn the observation complete.

Observed deterministic helper call sequences from the final cover (clock100.0, original deadline100.5) are preserved in complete `helper-outcome.json` specimens:

| Case | Actual seam operations | Final truthful reap |
| --- | --- | --- |
| remaining | wait(0.5) → kill at100.1 → wait(0.4000000000000057) | True |
| exhausted | wait(0.5) → kill at100.5 → wait(0) | False |
| kill_denied | wait(0.5) → kill at100.1 → wait(0.4000000000000057) | True |
| reap_failed | wait(0.5) → kill at100.1 → wait(0.4000000000000057) | False |
| already_reaped | wait(0.5) → wait(0.4000000000000057) | True |
| read_error | kill at100.0 → wait(0.5) → wait(0.4000000000000057) | True |

The exhausted case attempts kill at the original deadline and second wait(0), retaining returncode null/reaped false and unsuccessful status. Kill denial does not bypass the independently protected reap attempt; a later integer owning returncode is retained without making the observation successful. A second reap failure leaves no fabricated end. An initial wait error with already-integer returncode sends no signal. The prior-read-error case does not send a duplicate termination signal, and still gets its independent second wait. These are explicit deterministic seams, not proof of actual native ps failure behavior.

## R2: preserve primary reason through independent emergency finalization

Verified original branch: the normal finalizer exception handler supplied its later failure as `emergency(why)`, discarding an existing cap. `_MonitorStop` text containing quote/backslash/control characters could also produce invalid JSON because the old emergency concatenated it unescaped. RED retained both the primary-cap erasure and JSON decode failure, without replacing those failed specimens.

The emergency builder now chooses the existing `reason` first and uses the later failure as primary only when no primary exists. It retains a separate `finalization_failure` string containing exception type and bounded message, plus factual `cleanup_failure_count`. The normal richer cleanup diagnostics remain unchanged; the emergency count reports their existence within its finite reservation. It preserves all existing numerical/full-RSS conservative fields, raw/refusal/source-accounting flags, status and timing boundary. A failed finalizer always commits unsuccessful status, never completion.

A small independent ASCII JSON string encoder handles quotes, backslashes, controls, Unicode, non-BMP pairs and lone surrogates without calling the failed normal JSON encoder. It budgets escaped bytes, bounds primary text to at most256 encoded bytes and secondary text to at most256 encoded bytes/the remaining reservation, with explicit `...` when truncated. Fixed primary categories such as `incremental worker memory cap` survive exactly. The secondary field and quoting costs consume the existing reserved bytes; no new file or output allowance is created. The independent fd write still overwrites only the preallocated verdict reservation, preserving original raw padding and durable/returned agreement.

Six cap/no-earlier-primary cases exercise OSError from final encoding, OSError from final commit, and `_MonitorStop` from final encoding with actual quote/backslash/newline/tab/NUL/Chinese/emoji text. In all three cap cases the result retains exact `incremental worker memory cap`, at least500,000,000 B conservative known RSS, separately escaped finalization text and actual cleanup-failure count2. With no earlier primary, ordinary finalizer errors remain `monitor serialization/write failure` and the `_MonitorStop` reason remains its safely quoted actual text. Every result equals its durable padded JSON.

The minimum-reservation control retains an unusual quoted/control/Unicode/lone-surrogate primary plus a very long final encoding error within exactly512 verdict bytes and the original1,024-byte total output cap. The diagnostic is safely truncated; the primary round-trips exactly. Its first fixture version injected a commit error, but the intentionally tiny normal report cannot reach commit because encoding fills its reservation first. That failed fixture/specimen was preserved; the injection was moved to final encoding and its separate RED again confirmed primary erasure before the fix. No production result or previous attempt was overwritten to hide that correction.

Three directly affected existing finalization expectations were adapted (two parameter variants and one metadata control). They already had a missing post-import baseline before the later finalizer error, so the new contract correctly retains `missing post-import worker baseline or unresolved declaration` as primary and asserts the separate later OSError. Their full sampled-RSS, cleanup/reap, byte-cap and durable/returned checks remain. No old identity/reader behavior was weakened.

## Every verification attempt and exact command

The pre-existing byte-preserving pytest runner was reused with only the new owned temporary prefix/evidence destination. The actual `.venv/bin/python` interpreter was used. Every attempt has a fresh explicit `/private/tmp/task18-terminal-fix1-…` base, full pre-run source inputs, complete stdout/stderr combined log, immediate complete specimen copy after exit, `attempt.json` command/timing/Git mapping and per-attempt hashes. Pytest default pruning roots were not reused. Preserved `current` symlinks retain raw link payloads; durable specimen directories are present. Full unabridged outputs are the `full-output.log` files referenced below.

### `task18-terminal-fix1-r1-green-rq03csh2`

Exit `0`; **6 passed in 0.03s**. Full process wall cost including startup/log handling through subprocess return: `0.14095115661621094`s. Complete output and source/specimen mapping: `docs/research/task18-terminal-lifecycle-fix1-evidence/task18-terminal-fix1-r1-green-rq03csh2/full-output.log`, `attempt.json`, `manifest.json`. Source Git records the pre-commit BASE; the frozen source input hashes identify each actual RED/GREEN working tree.

```sh
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python -m pytest tests/test_kernel_stage_a_terminal_lifecycle.py::test_helper_eof_wait_failure_terminates_and_reaps_only_with_original_remainder --basetemp=/private/tmp/task18-terminal-fix1-r1-green-rq03csh2/specimens -ra
```

### `task18-terminal-fix1-r1-red-pdyvok_6`

Exit `1`; **6 failed in 0.09s**. Full process wall cost including startup/log handling through subprocess return: `0.25902724266052246`s. Complete output and source/specimen mapping: `docs/research/task18-terminal-lifecycle-fix1-evidence/task18-terminal-fix1-r1-red-pdyvok_6/full-output.log`, `attempt.json`, `manifest.json`. Source Git records the pre-commit BASE; the frozen source input hashes identify each actual RED/GREEN working tree.

```sh
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python -m pytest tests/test_kernel_stage_a_terminal_lifecycle.py::test_helper_eof_wait_failure_terminates_and_reaps_only_with_original_remainder --basetemp=/private/tmp/task18-terminal-fix1-r1-red-pdyvok_6/specimens -ra
```

### `task18-terminal-fix1-r2-green-ewo945f5`

Exit `0`; **7 passed in 0.05s**. Full process wall cost including startup/log handling through subprocess return: `0.16408920288085938`s. Complete output and source/specimen mapping: `docs/research/task18-terminal-lifecycle-fix1-evidence/task18-terminal-fix1-r2-green-ewo945f5/full-output.log`, `attempt.json`, `manifest.json`. Source Git records the pre-commit BASE; the frozen source input hashes identify each actual RED/GREEN working tree.

```sh
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python -m pytest tests/test_kernel_stage_a_terminal_lifecycle.py::test_emergency_preserves_first_cap_and_separate_finalization_failure tests/test_kernel_stage_a_terminal_lifecycle.py::test_emergency_quoted_primary_and_long_secondary_fit_minimum_reservation --basetemp=/private/tmp/task18-terminal-fix1-r2-green-ewo945f5/specimens -ra
```

### `task18-terminal-fix1-r2-minimum-red-tczm5mhg`

Exit `1`; **1 failed in 0.07s**. Full process wall cost including startup/log handling through subprocess return: `0.18477892875671387`s. Complete output and source/specimen mapping: `docs/research/task18-terminal-lifecycle-fix1-evidence/task18-terminal-fix1-r2-minimum-red-tczm5mhg/full-output.log`, `attempt.json`, `manifest.json`. Source Git records the pre-commit BASE; the frozen source input hashes identify each actual RED/GREEN working tree.

```sh
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python -m pytest tests/test_kernel_stage_a_terminal_lifecycle.py::test_emergency_quoted_primary_and_long_secondary_fit_minimum_reservation --basetemp=/private/tmp/task18-terminal-fix1-r2-minimum-red-tczm5mhg/specimens -ra
```

### `task18-terminal-fix1-r2-red-bc72ds_7`

Exit `1`; **7 failed in 0.17s**. Full process wall cost including startup/log handling through subprocess return: `0.2812840938568115`s. Complete output and source/specimen mapping: `docs/research/task18-terminal-lifecycle-fix1-evidence/task18-terminal-fix1-r2-red-bc72ds_7/full-output.log`, `attempt.json`, `manifest.json`. Source Git records the pre-commit BASE; the frozen source input hashes identify each actual RED/GREEN working tree.

```sh
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python -m pytest tests/test_kernel_stage_a_terminal_lifecycle.py::test_emergency_preserves_first_cap_and_separate_finalization_failure tests/test_kernel_stage_a_terminal_lifecycle.py::test_emergency_quoted_primary_and_long_secondary_fit_minimum_reservation --basetemp=/private/tmp/task18-terminal-fix1-r2-red-bc72ds_7/specimens -ra
```

### `task18-terminal-fix1-scoped-cover-evy_hhso`

Exit `0`; **55 passed in 0.64s**. Full process wall cost including startup/log handling through subprocess return: `0.7864792346954346`s. Complete output and source/specimen mapping: `docs/research/task18-terminal-lifecycle-fix1-evidence/task18-terminal-fix1-scoped-cover-evy_hhso/full-output.log`, `attempt.json`, `manifest.json`. Source Git records the pre-commit BASE; the frozen source input hashes identify each actual RED/GREEN working tree.

```sh
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python -m pytest tests/test_kernel_stage_a_terminal_lifecycle.py tests/test_kernel_stage_a_native_process_fix1.py::test_finalization_failure_returns_bounded_durable_failure_and_reaps tests/test_kernel_stage_a_native_process_fix1.py::test_deadline_crossed_in_final_encoding_is_not_completed_or_timed_before_work tests/test_kernel_stage_a_native_process_fix1.py::test_deadline_crossed_in_commit_cannot_persist_completed tests/test_kernel_stage_a_native_process_fix1.py::test_partial_evidence_write_keeps_prior_rows_readable_and_full_rss tests/test_kernel_stage_a_native_process_fix1.py::test_minimum_failure_budget_still_retains_readable_numerical_verdict tests/test_kernel_stage_a_native_process_fix1.py::test_commit_cost_is_visible_to_external_caller_and_boundary_is_explicit tests/test_kernel_stage_a_native_process_fix1.py::test_final_metadata_serialization_error_uses_same_failure_commit tests/test_kernel_stage_a_preflight_fix1.py::test_f3_final_report_overflow_has_one_durable_returned_verdict --basetemp=/private/tmp/task18-terminal-fix1-scoped-cover-evy_hhso/specimens -ra
```

The single final cover is exactly the full changed lifecycle control file plus eight parameterized/direct finalization controls and the existing report-overflow control listed in its command. Its46 lifecycle cases plus8 finalization cases plus1 overflow case total55. No broad cover was rerun; no second covering selection was needed. Focused R1 GREEN passed6, focused R2 GREEN passed7, then covering GREEN passed55. The RED/failure output remains complete and is not claimed passing.

`git diff --check` for the three source/test paths and `py_compile` for those same paths exited0 before source commit. The final covering archive's three source inputs are checked byte-equal to source commit `75c0d0f4913388668e71444156ae3e63bee032db`. Compilation and preservation checks do not run native sampling, numerical backend or scientific controls.

## Self-review and limits

R1 review: original helper bound remains `min(original_deadline, start+1)`; all new waits use its actual remainder and exhausted wait0. Termination is attempted at most once under continuous owning PID reservation; integer cached completion prevents signaling after reap. Query completeness remains false after any first wait failure, even if subsequent cleanup succeeds. Witness `reaped` still requires actual integer Popen returncode, and image/launch admission logic was not broadened.

R2 review: emergency encoding is independent of normal `JSONEncoder.iterencode`, `_bounded_json` and `_commit_monitor`, and secondary text is bounded by bytes after escaping. Its fixed RSS/refusal/accounting/status/timing fields remain. Existing primary categories stay exact; larger arbitrary diagnostic strings can be explicitly truncated to fit. The512-byte test exercises that boundary and verifies equal return/durable JSON, while cap tests retain conservative known costs. A device refusing both ordinary and emergency OS writes can still prevent durable delivery; this inherited physical-write limitation is not converted into success.

Mental mutation checks, not additional executed mutation runs: removing independent reap fails the six R1 controls; removing the unreaped guard fails the already-reaped case; renewing the bound fails exhausted wait0 assertions; erasing primary reason fails all three cap cases and existing missing-baseline cases; using the failed normal encoder or unsafe concatenation fails quoted/Unicode/lone-surrogate controls; growing the verdict fails the exact512/8,192-byte and total output checks. These targeted checks constrain the actual new failure paths rather than mirroring an implementation helper.

No separate defunct/argv rule is implemented. AST comparisons to BASE verify unchanged `PythonLifetimes`, `classify`, `_synthetic_classify` and ordinary `process_tree`. Authority/commands/dependency lock and all famjet sources remain byte-equal. Package SHA256 remains exact `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`. Ordinary `PS_ARGV`, private numeric vector, worker/controller inputs, resource limits600s/90s/201326592B/67108864B/4294967296B and CPU float64/at-most-four-thread policy are unchanged. Parent/supervisor RSS exclusion and sampled resident-memory (not allocator peak/continuous exec/security containment) limits remain.

## Preservation and still-unfulfilled native gate

The reused auditor compares symlink payloads by raw link bytes and ordinary files by original Git blob bytes/SHA256. It verifies **4,615 prior Task18/lifecycle entries**, **62,606,889 bytes**, with **zero mismatches** against BASE. This includes old reports, controls, native outputs/manifests, raw verdict padding and earlier failures. Root's separately introduced documents are excluded from the immutable BASE inventory and were never staged here. `prior-artifacts-audit.json`, `source-audit.json`, `preservation-summary.json` and complete audit output retain the full proof. No new all-history auditing framework was introduced; the existing runner/auditor were reused with scoped destination/base/source updates and their established symlink handling.

The original failed scientific setup remains failed: no reused factors/exports or accepted setup reinterpretation. Both historical native attempts remain NEEDS_CONTEXT. The first failed live multiline-vector identity and actually reaped root−9 after cancellation. The file correction established real live file-vector proof, then actual `<defunct>`/ESRCH/RSS0 terminal representation with natural root exit0/end before reconciliation, yielding STOPPED/foreign process identity under unchanged policy. Both survivor scenarios remain NOT RUN. R1/R2 synthetic passes cannot satisfy that native acceptance gate; no new native/scientific allocation or source self-acceptance is inferred. Root independently inspects the evidence and returns this fix diff to the same reviewer for R1/R2-only re-review and new breakage.

## Delivery identity

Source/test commit: `75c0d0f4913388668e71444156ae3e63bee032db`. Exact current source/test byte counts and SHA256:

- `tests/test_kernel_stage_a_native_process_fix1.py`: 17193B, SHA256 `786eb0bf0dc96d49e453478f12c59bd42f569a9f9c0d6521505cad3cae34f0bb`.
- `tests/test_kernel_stage_a_terminal_lifecycle.py`: 20095B, SHA256 `f17f7c2ac948ceaadceef1c4f18243ef610218b73742468fd73e8554b73aa78c`.
- `validation/kernel_stage_a/monitor.py`: 68699B, SHA256 `0340aea63b1776ff8ac19ee6c67743e15bd5e6f1f392fcbd44492d62803409e2`.
- `validation/kernel_stage_a/authority.py`: 17718B, SHA256 `25d172f31df4ee70069f91840c5f48a2d12759d733744744fbb0ff30163af5d4`.
- `validation/kernel_stage_a/commands.py`: 2375B, SHA256 `01f1c14f53f5e31cd87640867a730080999c7dc12e5d5bcda2013428514658a0`.
- `requirements.lock`: 2658B, SHA256 `2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1`.

The evidence commit follows root's document-only7055537 and contains only the new evidence directory and equal report copies; its ID is delivered after commitment rather than creating a self-referential hash. Reports are `.superpowers/sdd/2026-10-16-famjet/task-18-terminal-lifecycle-fix1-report.md` and `docs/research/task18-kernel-stage-a-terminal-lifecycle-fix1-report.md`, checked byte-equal. The final new evidence manifest records all raw files/symlink payloads plus external report/source hashes; individual attempts retain their original manifests. No immutable earlier report was rewritten; this linked addendum satisfies the appended-fix reporting requirement without invalidating old proofs.
