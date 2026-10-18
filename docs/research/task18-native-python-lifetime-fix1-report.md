# Task 18 Python lifetime FIXROUND1: L1 baseline publication

Implemented the single adopted L1 correction from clean current-main BASE `dcd0a4f1265314485577637860b427e97a992b5e`. Verified source commit: `1114388e891021cf83ba18eaba32e7dc5744ef9a`. The subsequent delivery commit contains only new technical evidence and this report. No branch, worktree, subagent, reviewer, push, selfacceptance, native rerun or scientific work occurred.

The binding fix brief and full review were read before editing and are preserved under `docs/research/task18-native-python-lifetime-fix1-evidence/contract/`. Brief: 6604 bytes, SHA256 `c0bacb416d4266cd4bbc5954d748cc0bd3bc3fb6b1edb91500bd0f95920afc03`. Review: 12290 bytes, SHA256 `587c95ac2eea114541643d0b6ee575a6f0282ee92bd60f4c1bdcae9357047c36`.

This report has an equal durable copy at `docs/research/task18-native-python-lifetime-fix1-report.md`. All remaining evidence paths below are relative to `docs/research/task18-native-python-lifetime-fix1-evidence/`. Original source/evidence/reports/frozen metadata remain unmodified.

## Finding and correction

The review identified a valid conservative false failure. PythonLifetimes could finish a reader's generation/self-proof/baseline join, but supervisor accounting only copied that joined baseline while reconciling a sample containing the PID. Native pending-baseline samples deliberately settle and are discarded. A late baseline or launch could complete the join with no sample left to wake and no future reader row. Final accounting then falsely reported a missing baseline and charged full RSS.

The source repair adds one local `publish_python_baseline(pid, final=...)` operation inside supervise. Each event that can finish the join—baseline, tagged self sample or source launch—invokes it immediately after generation validation. It publishes only the affected generation's fully validated baseline, only with complete source identity provenance, and only if that PID is absent from the persistent failed set. If a sampled worker exists, the operation refreshes its existing charge. Unchanged baselines are a constant-time no-op. The former sample-dependent baseline-copy loop was removed.

This repairs the field handoff without retaining settled samples, inventing observations, adding a registry, scanning history or changing image/generation/lifetime rules. Root/direct-baseline behavior remains. All raw RSS is retained. Existing charge logic preserves monotonic peaks, conservative full-RSS costs, prior identity failures, cap reasons and unsuccessful execution statuses. A valid late baseline cannot turn an established cap stop into COMPLETED.

Only monitor.py and the new focused supervisor test file changed in the source commit. No authority.py, production.py, commands.py, __main__.py, reader_worker.py, library/dependency/schema/source guard or numerical behavior changed. Package digest remains `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`. Original 600s outer / 90s candidate / 201326592B incremental worker / 67108864B outputs / 4294967296B free / CPU64 <=4-thread limits and inside-limit reservations remain.

## Meaningful integration verification

The new tests use supervise's actual source-journal ingestion, candidate context, generation validation, sample reconciliation, settlement, wakeups, final charging and serialized verdict. A scripted sampler and fake owned process supply deterministic synthetic identity rows; they do not call the new publication helper directly or invoke native sampling. The fixtures use the exact existing reader command/vector/runtime-mapping validation and an actual tagged successful emitter self row. The supervisor owner and reader are synthetic PIDs 400001 and 400002; there is no OS process or numerical request associated with them.

For baseline-last and launch-last, the fixture inspects the supervisor journal at the next sampler call and confirms that the earlier reader row already resolved once as pending_baseline. That reader is absent from every later sampler call. The late valid baseline/end, or launch joining the earlier self row/baseline, is then delivered. Final accounting must resolve the worker without reopening or inventing the settled sample.

The self-sample-last case supplies one earlier outer live row, then the one delayed own source observer sample; that source event is the legitimate additional row. The test asserts exactly those two rows/resolutions. Negative controls cover mismatched baseline RSS; failed provenance preceding each of the three join-completing events; and a previously contradictory classified identity with otherwise complete source provenance. The latter specifically checks that the persistent failed set still prevents publication/attribution. A pending ESRCH control establishes a full-RSS cap violation before the late valid baseline/end is ingested during cleanup and confirms that the prior peak and cap reason persist.

Final controlled positive outcomes:

| Join completed by | Final role / baseline / net | Raw reader samples / resolutions | Supervisor elapsed |
| --- | --- | --- | --- |
| Late baseline | worker / 100B / 0B; COMPLETED, no unresolved PID | 1 / 1 | 0.004004375s |
| Late launch | worker / 100B / 0B; COMPLETED, no unresolved PID | 1 / 1 | 0.003059583s |
| Late self sample | worker / 100B / 0B; COMPLETED, no unresolved PID | 2 / 2 | 0.002976834s |

All retain an absolute peak of 100B. The cap control remains STOPPED, reason `incremental worker memory cap`, historical peak 100B despite a 50B test cap. The four invalid/provenance cases retain zero baseline and full 100B charge. The persistent-identity-failure case remains unaccounted with zero baseline and full charge while source identity provenance itself remains complete. These byte values are deliberate deterministic fixtures, not a scientific measurement or new production tolerance.

## Every actual new attempt

`run-attempt.py` refuses reused destination/basetemp paths, captures then-current full external helper modules and affected/helper test inputs before executing pytest, preserves the complete merged stdout/stderr, and immediately copies the entire actual pytest tree (including failures and symlinks) before returning its exit. No missing old output was recreated. Every attempt has `attempt.json`, `output.log`, `source-inputs/`, `specimens/` and `specimen-mappings.json`. The metadata records exact argv, Git HEAD, original `/tmp` and resolved `/private/tmp` basetemps, durable paths, exit and full runner elapsed. Unchanged covering test modules are additionally preserved as exact Git-blob input supplements bound to the actual recorded attempt HEAD (`cover-01/test-source-supplement.json`); their hashes match the unchanged workspace bytes. These are source-input copies, not recreated test outputs. Only the following three new pytest attempts occurred:

| Attempt | Exact pytest result | Disposition |
| --- | --- | --- |
| red-01 | exit 1; 3 failed, 3 passed in 0.08s | Baseline-last and launch-last reproduced L1's false missing-baseline STOPPED. The third failure was an overstrict new cap-fixture assertion that all reconciliation must finish after a cap stop; the existing bounded reconciler may stop with other samples pending. That assertion was corrected to require retained late valid evidence, peak and cap reason, without promising resolved status after a cap stop. The original failed inputs/output remain intact. |
| green-01 | exit 0; 6 passed in 0.06s | Corrected local publication and focused positive/negative/cap controls. Runner elapsed 0.208998875s. |
| cover-01 | exit 0; 105 passed, 24 deselected in 4.67s | One final relevant external covering run, including the expanded nine L1 controls and prior strict/native/monitor/authority/fix2 controls. Runner elapsed 5.088904167s. |

RED and GREEN commands (run separately with their own basetemp):

```sh
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_python_lifetime_fix1.py --basetemp=/tmp/task18-python-lifetime-fix1-red-01
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_python_lifetime_fix1.py --basetemp=/tmp/task18-python-lifetime-fix1-green-01
```

Final covering command:

```sh
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_python_lifetime_fix1.py tests/test_kernel_stage_a_python_lifetime.py tests/test_kernel_stage_a_native_process_fix3.py tests/test_kernel_stage_a_native_process_fix2.py tests/test_kernel_stage_a_native_process_fix1.py tests/test_kernel_stage_a_native_process.py tests/test_kernel_stage_a_preflight_fix2.py tests/test_kernel_stage_a_preflight.py tests/test_kernel_stage_a_preflight_fix1.py -k 'python_lifetime or native or monitor or authority or observer or baseline or f3 or f5 or same_interpreter or prospective' --basetemp=/tmp/task18-python-lifetime-fix1-cover-01
```

Each was launched through `.venv/bin/python docs/research/task18-native-python-lifetime-fix1-evidence/run-attempt.py <attempt> <the listed pytest paths/options>`. Attempt.json retains the actual absolute executable and argv. No full suite or additional routine covering repeat was run. The final set is justified by the supervisor event-to-accounting change and preserves the existing strict earlier-image-without-generation-proof failure tests and failed-provenance controls.

## Frozen source, historical native evidence and artifact audit

Actual fixed source HEAD: `1114388e891021cf83ba18eaba32e7dc5744ef9a`.

- monitor.py SHA256: `feeba692a258369ec21f2fb1bc9d4bd3a115b65216f6980e72176dce3f526442`
- New integration tests SHA256: `26d07e04b61e474b0378c85086fe49b7b9099ac91c72044045df377b21a9b75c`

`frozen-source.json` records actual source HEAD and every current external helper hash. The audit compares each file to its committed Git blob, verifies unchanged excluded source/dependency/package boundaries, verifies all archived specimen hashes/mappings, and examines the actual final supervisor outputs and sample/resolution counts. The cover source-input snapshot contains the tested fixed monitor/test bytes.

The original native sequence remains historical evidence on SOURCE `18c7753e982b9ea2a8d6191a35970c5151403ab7`: 2.031376834027469s, expected worker return codes 2 and 1, two actual ESRCH observations, zero numerical work. The fixed monitor has different whole-file bytes. It was NOT native-rerun, and the old native result is NOT represented as a new native proof of the fixed whole file. L1 changes only local supervisor baseline publication; no libproc, OS vector, owned dispatch or actual image-proof rule changed. New controlled supervisor integration is the meaningful verification authorized for this repair.

All 974 regular files in the prior lifetime artifact manifest were read and byte-verified against their recorded hashes. The previous source/evidence/report paths also have a zero Git diff from BASE. Original pytest symlink targets remain unchanged. The original native script, raw rows, result, runtime hashes, reports and frozen metadata remain intact; no earlier audit was rerun or rewritten.

Read-only new artifact audit:

```sh
.venv/bin/python docs/research/task18-native-python-lifetime-fix1-evidence/verify.py
```

Exit 0; full output and exit retained in verify.log/verify.exit, with structured `verification.json`. This is implementation artifact verification, not source acceptance or independent review. It makes no native sampling call and imports no project module. Its status explicitly says `VERIFIED_L1_ARTIFACTS_ONLY_NOT_SOURCE_ACCEPTANCE`.

The new `artifact-manifest.json` inventories actual durable regular-file sizes/hashes and symlink targets, with source-input and original specimen mappings in each attempt. Scratch pytest `*current` aliases remain preserved symlinks; concrete sibling specimen directories contain the durable outputs. Authored monitor/test/report whitespace checks are clean. Sixty-eight raw padded monitor.json files across the new attempts retain their exact reserved-verdict trailing padding, separately listed in verification.json; these are preserved raw evidence and were not normalized.

## Cost, scope and remaining limits

Publication adds a few constant-time mapping checks and at most one existing worker-charge refresh per newly completed join. It does not add source samples, scans, new state registries, backend operations, dispatches, requests or deadlines. The measured supervisor fixture timings above include the local charge/report work; they do not establish native or scientific performance. All test/output overhead and actual archive bytes are recorded; no scientific allocation is renewed.

No new native functional attempt or scientific factor/model construction, request, read, fixture/reference/profile campaign, dataset/corpus/history/cache, fit/train/panel/bootstrap/calibration/protected work occurred. Existing source-test imports remain ordinary permitted imports. No numerical population, metrics, protocol, seal or source-admission guard changed. Task 19's separate unadopted design was not touched.

The adopted sampled trusted-source identity limitations remain: no continuous image certificate, arbitrary argv-byte proof, kernel birth token, never-proved Python admission or PID-generation reuse support. No full native supervisor/resource feasibility run was executed. Scientific feasibility, successful numerical readers and all protected results remain NULL/HELD. Root verification and the same fresh reviewer's scoped L1/new-fix-breakage review remain required; no source acceptance or scientific release is claimed.
