# Task18 native process FIXROUND4 — residual N1

Submitted for scoped root/reviewer assessment; no source self-acceptance or scientific release. BASE `6ae27aa9ceacd83905d47de60bfee5961cf752e1`; actual source HEAD `daa89fcd7986e9a4c600869d256451fbba65c927`, current branch `main`. Relevant covering result: **64 passed, 24 deselected in 3.03s**, exit0. Native functional attempts0, scientific factor constructions0, scientific/model reads0.

## Binding scope and N1 disposition

Read the full fix4 brief and fix3 review before implementation. Exact copies are retained in `task18-kernel-stage-a-native-process-fix4-evidence/contract/`. This round addresses only the residual failed-boundary attribution path and checks relevant controls for breakage. The source commit changes exactly `validation/kernel_stage_a/monitor.py` and `tests/test_kernel_stage_a_native_process_fix3.py`.

The reviewer’s path reproduced directly: authority_start is admitted in an earlier poll; the source then records authority_end, a strictly later root sample500, and baseline500. Copying authority_end fails after the semantic cursor advances but before the phase state changes. Numerical recovery retains500; the old source then uses the stale active phase during final reconciliation and attributes500 to authority. Both strengthened tests failed with authority500 versus expected0/60. The old test cap100 masked this path by stopping on an earlier empty batch.

The regression now sets incremental cap1000 only for the two controlled copy-failure variants. Successful baseline variants retain cap100; production limits are unchanged. The test requires the later500 sample and its resolution row to exist, requires the resolution and final worker role to be `unaccounted`, requires unresolved count1 and source identity completeness false, and requires authority0/60 alongside full raw and conservative500. Thus an earlier stop or a dropped sample cannot satisfy the strengthened regression.

The fix uses the existing source `identity_complete` flag to gate reconciliation. When source provenance has failed, later batches receive unresolved `unaccounted` roles instead of invoking classification against a potentially stale phase. The existing charge/failure paths retain the full conservative RSS sum; previous authority peaks remain intact. No missing end timestamp is reconstructed, and the failed phase is not silently repaired. In the final copy-failure specimens the phase remains active with no admitted end, source identity remains incomplete, and status remains STOPPED/output cap. The post-end sample contributes no new phase-attribution or identity proof.

This is one local guard using existing state and failure roles. It adds no journal, process/storage framework, authority cache, source identity rule, lifetime policy, numerical proof or new evidence limit. Successful actual-overlap attribution and prior valid authority peaks keep their existing behavior. The README is unchanged because its existing failed-copy attribution statement now holds for the strengthened path.

## Exact commands and all attempts

Each pytest invocation ran through `docs/research/task18-kernel-stage-a-native-process-fix4-evidence/run_attempt.py`, with positional attempt `red`, `green` or `cover`, followed by the command below without its final basetemp argument. The runner adds that exact argument, captures combined stdout/stderr verbatim, records exit status and current HEAD, snapshots test/source inputs before execution, then immediately archives the complete owned basetemp and copies every existing monitor-verdict directory. It refuses to reuse either an attempt destination or basetemp. No attempt was rerun for packaging.

```sh
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_native_process_fix3.py -k 'post_authority and True' --basetemp=/tmp/task18-native-fix4/pytest-red
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_native_process_fix3.py -k 'post_authority and True' --basetemp=/tmp/task18-native-fix4/pytest-green
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_native_process_fix3.py tests/test_kernel_stage_a_native_process_fix2.py tests/test_kernel_stage_a_native_process_fix1.py tests/test_kernel_stage_a_native_process.py tests/test_kernel_stage_a_preflight_fix2.py tests/test_kernel_stage_a_preflight.py tests/test_kernel_stage_a_preflight_fix1.py -k 'native or monitor or authority or observer or baseline or f3 or f5 or same_interpreter or prospective' --basetemp=/tmp/task18-native-fix4/pytest-cover
```

| Attempt | Exit | Full raw log | Result |
|---|---:|---|---|
| RED, unchanged production source | 1 | `red/output.txt` | 2 failed, 4 deselected, 0.10s; authority500 versus0 and60 |
| GREEN, single source guard | 0 | `green/output.txt` | 2 passed, 4 deselected, 0.08s |
| Final relevant covering | 0 | `cover/output.txt` | 64 passed, 24 deselected, 3.03s |

No other pytest attempt occurred. The full suite was not run, as the binding brief restricts execution to these focused controls. The covering set retains positive overlap, F1/F2, unavailable-source accounting, bounded output, settled/pending work, deadlines/cleanup, strict native identity and source-admission tests. Native-named tests use the established controlled seams; no fresh native functional probe or scientific campaign was performed.

Additional executed checks:

```sh
.venv/bin/python -m py_compile validation/kernel_stage_a/monitor.py tests/test_kernel_stage_a_native_process_fix3.py
git diff --check -- validation/kernel_stage_a/monitor.py tests/test_kernel_stage_a_native_process_fix3.py
git add -- validation/kernel_stage_a/monitor.py tests/test_kernel_stage_a_native_process_fix3.py
git diff --cached --check
git commit -m 'fix: refuse phase attribution after source provenance failure'
.venv/bin/python docs/research/task18-kernel-stage-a-native-process-fix4-evidence/audit.py
```

Compilation and source whitespace checks returned0 with empty output; their raw files and commands are retained in `source-checks.json`. Staged source whitespace returned0 before the verified source commit. Source diff and commit metadata are retained as `source.patch` and `source-commit.txt`. The audit is a pure-file/hash/archive operation, with its exact script and output retained; it imports no project/scientific module. The initial read-only `cat AGENTS.md` returned1 because no root AGENTS.md exists; file discovery confirmed no applicable repository AGENTS.md. No edit or probe resulted from that read failure. No other failed execution beyond the intentional RED tests is claimed or omitted.

## Actual final controlled specimens

All paths below are relative to `task18-kernel-stage-a-native-process-fix4-evidence/cover/specimens/`. The full `specimens.json` records every actual verdict, exact verdict hash/bytes, directory bytes, status/reason, authority/RSS and source completeness. Original source journals and evidence rows retain their actual ordered timestamps; they were not normalized or regenerated.

| Specimen | Directory bytes | Status | Authority RSS | Incremental/conservative RSS |
|---|---:|---|---:|---:|
| `test_post_authority_baseline_b0/complete` | 10576 | COMPLETED | 0 | 0 |
| `test_post_authority_baseline_b1/complete` | 11915 | COMPLETED | 60 | 60 |
| `test_post_authority_baseline_b2/copy_failure` | 10238 | STOPPED | 0 | 500 |
| `test_post_authority_baseline_b3/copy_failure` | 11570 | STOPPED | 60 | 500 |
| `test_source_sample_overlapping0/overlap` | 10576 | COMPLETED | 80 | 80 |
| `test_source_sample_overlapping1/overlap` | 11922 | STOPPED | 80 | 500 |
| `test_late_inner_rss_survives_f0/declaration_cap` | 16368 | STOPPED | 0 | 980 |
| `test_late_inner_rss_survives_f1/completion_cap` | 16368 | STOPPED | 0 | 980 |
| `test_late_inner_rss_survives_f2/serialization` | 10926 | STOPPED | 0 | 980 |
| `test_minimum_failure_budget_st0/minimum` | 512 | STOPPED | emergency omits field | 70 |
| `test_unrecoverable_source_jour0/storage` | 9944 | FAILED | 0 | 70 |
| `test_unrecoverable_source_jour1/partial` | 11603 | FAILED | 0 | 70 |
| `test_unrecoverable_source_jour2/truncated` | 10382 | FAILED | 0 | 70 |
| `test_unscanned_complete_source0/deadline` | 9867 | FAILED | 0 | 70 |

Normal verdicts above reserve8192B; the minimum emergency verdict is exactly512B. Successful post-end baseline specimens retain raw peak/sum500 with baseline500 and worker increment0, while their prior authority remains0/60. The positive overlap80 is retained even with a later unbaselined500 observation. F1 preserves980 (root80 plus inner observer900) across declaration/completion/encoding refusal. F2 preserves `raw_identity_complete=false`, refused count1, refused RSS70 and full70 in512B. Unavailable source controls remain FAILED with incomplete source accounting; they do not invent an unobserved900 bound. The strengthened copy-failure cases remain STOPPED, not false COMPLETED outcomes.

## Preservation, hashes and boundaries

The three attempts preserve **50 actual monitor verdicts** (RED2, GREEN2, covering46) and **571 original-to-durable mappings** (24,24,523). Each attempt includes all regular basetemp files in `all-specimens.tar.gz`, with individual original/member SHA256/byte mappings; monitor output directories are additionally retained as readable copies. The full archives also retain non-monitor test inputs and fixture outputs. Symlink metadata is preserved in the archive; per-file mappings enumerate regular files, not symlink aliases. All current round4 output specimens survive independently of scratch. The prior round3 missing-specimen limitation remains disclosed and unchanged; no earlier attempts or missing specimens were reconstructed.

The audit verifies every mapped original, archive member and readable copy; checks every recorded input snapshot hash; compares the RED monitor snapshot to BASE and GREEN/cover snapshots to the committed source; checks ordered N1 timestamps, final sample resolution and absent new identity proof; and verifies **1846 earlier tracked files** are byte-preserved against BASE. This covers all earlier tracked evidence/reports/verifications, package files, frozen data/metadata/seals, dependencies and untouched implementation interfaces. Only the two authorized source paths differ from BASE. No earlier artifact bytes were rewritten.

| Source path | Bytes | SHA256 |
|---|---:|---|
| `validation/kernel_stage_a/monitor.py` | 41807 | `5a7e72be8a4d0987bc8f5de2d8f46fb2fedae599fcc3e24c58b35e8ea8d89cf0` |
| `tests/test_kernel_stage_a_native_process_fix3.py` | 5795 | `2a2c0dcde2f1a3ce7dc01e7e4e486397efb9e875213c11b2d7c556ba7133bc1c` |

The package remains `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`. Required local report `.superpowers/sdd/2026-10-16-famjet/task-18-native-process-fix4-report.md` and this durable report are byte-equal. `task18-kernel-stage-a-native-process-fix4-verification.json` inventories artifact hashes/bytes, attempt commands/exits, source HEAD and preservation status. It excludes its own hash to avoid circularity. Documentary packaging postdates the verified source commit and the synthetic runs.

Original limits remain600s outer/90s candidate/201326592B net/67108864B output/4294967296B free/CPU64/at most4 numerical threads, with internal reservations inside those limits. Initialized output remains the same fixed five filenames. Authority/commands/production/entrypoint/reader-worker behavior, mathematical state/rates/factors/fixtures, metadata/lock/dependencies, sourceguard/cache and numeric protocol are untouched.

Scientific nulls remain `implementation_review`, `represented_rate_records`, `static_exports`, `resource_measurement_boundary_seal`, `fresh_launch_snapshot`, `output_directory`, `root_stage_A_release`. Lifetime work remains HELD. Strict per-sample Python ESRCH behavior is unchanged, including later ESRCH after a previously proved sample. No whole-suite, fresh native-image, full native Stage A, ordinary-reader viability or scientific-readiness claim follows from these synthetic controls. Existing sampled-RSS/allocator-peak, path-file/mapped-image and both-final-writes-storage-failure limitations remain. Root owns acceptance and any later work or release; this submission does not start another task.
