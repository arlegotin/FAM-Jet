# Binding01 retained-evidence diagnosis

**FAILED / HOLD.** The exact monitor rejection is a helper image-observation interval crossing its actual owning completion. Matching argv/image/hash does not satisfy the unchanged lifetime predicate. An independent worker import failure also prevents qualification. Neither finding authorizes a retry, Publication, source change, or native experiment.

This read-only diagnosis inspected bounded journal records, events, reports, and source; no project imports, tests, process probes, or global cleanup-membership dump. The inspected source has no diff against executed `9f47f8260374a0193198c6ba8faa3b68c5a016eb`. Monitor SHA remains `3c7e4aa237173895245444e1cb66a017275507398a6446133020ad509a00d30e`.

## Exact causal chain

`monitor-evidence.jsonl` is 103715 bytes, SHA256 `5495d72acbf9f92638ca60ec1894f1cc0e3a92ecbf3f23262a7cd67667d06199`; indices below are zero-based JSONL records.

1. Records 70–71 declare Git40705, parent40678, launch ID `bb646445800444199e1ae28453c53119`, exact `status --porcelain` vector/hash and Git artifact. Sample22 (72) observes matching native path/hash/display. Resolution74 initially gives Git `pending_source_lifecycle`, worker `authority_worker`: owning completion has not arrived.
2. Sample23 (75) retains Git RSS sample interval `[812636.389725500,812636.424019458]` and successful image interval `[812636.424884541,812636.426814791]`. Its observed argv/path/hash match the declaration. Records77–78 supply actual `completion_end=812636.426186583`, reaped=true, returncode0. Thus:

   `lookup_start < completion_end < lookup_end`.

   The image interval ends approximately 0.628208 ms after completion. Authority-end79 reports success=true; both exact Git operations completed successfully.
3. `source_lifecycles.py:68–84`, `SourceLifecycles.image_evidence`, rejects kernel evidence when `high >= entry.completion_end`. All reported matching identity fields cannot override that explicit temporal predicate. `attribute` returns `unaccounted` and retains PID40705 in `failed`. `monitor.py:345–388` propagates this through `helper_role`; reconciliation1020 raises `foreign process identity`. Resolution80 records sample23 Git unaccounted while the worker remains authority_worker.
4. Final resolution86 revisits sample22 after the PID failure is sticky. It now says Git unaccounted. Sample22 was not the initiating bad interval. Source events remain complete/identity-complete because their syntax, declarations, phase, and completions were accepted; those flags do not certify sampled lifetime acceptance.

`authority.process_image` (`authority.py:38–76`) brackets both the native path call and subsequent executable-file hashing with `lookup_start/end`. The retained interval proves overlap with reap; it cannot identify the exact kernel-call instant or prove a foreign executable. This is a fail-closed timing boundary in inherited lifecycle semantics, not evidence of malformed B helper wiring, PID substitution, hash mismatch, or a new unknown child. The alternative completion check `_end` also forbids completion at/before previously accepted image-end; merely changing event-drain order would not fix the underlying overlap.

## Independent failure and cleanup limits

`stage-b.json` (3957 bytes; SHA256 `6f43f8aa0794a6d179a8ef775327cf22afaa71cc7a4e3ca70c1e8698aa58ef7c`) records `INFRA_STOP`, phase `prepare`, `ModuleNotFoundError: No module named 'torch'` at812636.427049416. `_worker` calls `verify_worker`, then imports Torch before baseline. No baseline was emitted; the worker returned1 and was actually reaped1 (records83–85). Unresolved40678 therefore does not establish a second foreign-image observation; retained resolutions still label it authority_worker, without a baseline.

The exact sealed launcher is the resolved Homebrew Python executable with `-I`; bootstrap adds repository root only. The evidence establishes dependency unavailability in that invocation, not where Torch might be installed or which alternative runtime is admissible. No such environment was probed.

Cleanup's later `PermissionError/EPERM` is a separate failed cancellation diagnostic, not the initiating classification predicate. Actual wait evidence survives; neither that exit nor helper success erases cleanup failure. Zero constructions/encodes/reads/factors/predictions remain; terminal and binding reports are FAILED.

## Smallest options and ruling cost

- **Maintain current contract:** retain binding01 failure and HOLD. There is no demonstrated B-only declaration/vector correction that removes this native lifetime race. A future independently authorized binding with identical semantics could succeed under different scheduling, but is no correction or assurance. The import failure needs resolution first; no retry is proposed here.
- **Close runtime wiring separately:** identify an approved isolated launcher/dependency environment from retained configuration before proposing a change. Preserve launcher identity versus loaded image distinctions, exact argv binding, and current-A runtime comparison. Altering those requirements needs an explicit source/authority ruling and fresh acceptance; installing packages, bypassing `-I`, or skipping Torch/baseline is not an authorized remedy.
- **Deterministic temporal correction requires a contract exception:** a narrowly scoped redesign could distinguish native-call observation time from later file-hash completion while retaining both intervals and actual reap. That changes inherited native evidence semantics and needs an explicit amendment, source review, controlled boundary tests, and separately released qualification. It is outside this task and the current no-native-algorithm-change constraint. Relaxing the inequality, inventing later completion timestamps, sleeps, skipped Git operations, or whitelisting do not constitute supported fixes.

No earlier passing helper proof is needed to establish these predicates, and it cannot waive this run's retained failure.
