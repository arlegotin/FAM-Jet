# Task18 CPU64 operational results review — 2026-10-17

**Spec-compliance verdict: approved for the declared two-update operational profile. Evidence-quality verdict: approved; no blocking findings.** This does not accept Task18 scientific results, authorize sustained training, or broaden the approved configurations. Candidate source remains `adb8a74980610c8570dc52aaceb727913afe1e6d`, package `b898bef145c0edbd2298240a022f6458fa6724f0b8ba0b1144488fe1a1b51bbc`.

Scope was the new saved results and their mapping. I inspected existing artifacts, compared helper ASTs and tensor values, decoded checkpoint envelopes/wire arrays without reconstructing models, and checked hashes/accounting. No model execution, suite, numerical campaign, source edit, index change, or Git mutation was performed. Earlier production-source and analytic-oracle reviews remain separate gates.

## Numerical mapping and composition

- `artifacts/task18-evidence/procedure-scripts/task18_decimal_checkpoint.py:13` and `:65`: the only changes from the reviewed original helper are optional input/output paths. All five function ASTs (`oracle`, `flatten`, `tensor`, `compare`, `controls`) are identical. Archived helper SHA256 is `dbcb91eb8e7f692d640cf77d9369b0d163be1bbdf9f9036b063a3dfe569ac717`; the archived driver selects both families, every ordinal 0–11, and each fitted step-2 input directory (`task18_decimal_step2_run.py:5`). No tolerance or candidate arithmetic changed.
- `learned-rate-numeric64.py:25` loads a checkpoint against exact source/config identities and asserts its completed step. Its unchanged SHA256 is `ad64ca5007d331d6986f4dfd849c4912f92b8e58bf93c6a61001817376c13bd6`. I independently verified all four retained checkpoint SHA256 values, checksum envelopes, completed steps, source, canonical config, fit provenance and target-statistics hash. Decoded saved rate/logit wire values exactly match the fitted procedures and summaries; the checkpoint model-state logits also match. Every saved model-state tensor is float64. The procedures use the exact 768-history fit and target hash `0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21`.
- All 24 step-2 Decimal cases map by SHA256 to the fitted candidate tensor files and original procedure hashes. I checked each aggregate summary hash, reference80 JSON hash, source, ordinal/history identity, raw hashes, represented sigmoid values and probe coefficients. The regenerated fixture DataConfig, data seed and length set equal the fitted config; the input presentation path is unchanged. This is saved-artifact/procedure verification, not a fresh independent regeneration of raw inputs.
- `artifacts/task18/learned-rate-cpu64-decimal-step2/summary.json:1`: all 24 cases pass unchanged pointwise `atol=rtol=1e-12`. Worst candidate ratios are Jet **0.4128710309**, Bank **0.5054998338**. Recomputed maximum recorded Decimal60/80 difference is **9.9933372549375261209e-50**. All cases retain both control outcomes and full reference evidence.
- All 24 fitted step-0 files contain bitwise-identical original memory/state/feature/reference tensor fields to the corresponding accepted initial fixture files. Their rates, logits, candidate-event hashes and raw hashes also match. Therefore the accepted initial Decimal gate composes with these fitted step-0 memory results. The old Jet step-0 binary64-reference failure remains honestly recorded; it was not overwritten with a blanket pass.
- `learned-rate-numeric64.py:83` adds fitted task prediction/loss, task input/logit gradients and common-reader parameter-gradient comparisons. Across all 48 family/step/cell fixtures, all those checks pass the original pointwise tolerances. Worst ratios by family/step are Jet0 **0.000842194**, Jet2 **0.000516346**, Bank0 **0.000517073**, Bank2 **0.000852974**. These compare the same fitted reader/objective using recurrence features versus direct-event features; they are not an independently implemented reader or task-loss oracle.

The original scope limitations remain: candidate **logit** gradients are captured; no candidate raw `dL/dr` tensor was captured, so direct candidate raw-rate gradients are not certified. `query_inputs` is shared with production and not independently certified. Decimal stream-feature checks contract captured stream states; the fitted binary64 procedure separately checks actual production stream features.

## Actual resource and byte evidence

`artifacts/task18/telemetry-{jet,bank}-learned-cpu64/cost.json:1` records the conservative external cold boundaries:

| Measurement | Jet4 | Bank8 |
|---|---:|---:|
| External cold elapsed seconds | 188.667627 | 185.382815 |
| Additional cumulative RSS high-water bytes | 163,741,696 | 167,559,168 |
| Absolute RSS high-water bytes | 388,022,272 | 391,643,136 |
| Actual parameter bytes from saved tensors | 88,168 | 88,200 |
| Actual optimizer tensor bytes | 175,324 | 175,388 |
| Snapshot payload bytes | 9,345 | 9,345 |

Both additional peaks are below **201,326,592 B**. These are process cumulative high-water deltas, not stage-isolated live allocation or evidence that sustained training fits. The internal development timing/peaks use slightly narrower boundaries; the external numbers above include wrapper overhead.

Both development artifacts report configured horizon 32768 and actual completed stop 2. Each final evaluation has 768 query rows from 96 histories; every payload byte record is 9345. Saved optimizer moments are float64 and step counters float32. The telemetry records finite float64 gradients at both updates, with 87,648/87,680 gradient bytes. Saved checkpoint parameter and optimizer byte totals were independently recomputed from tensor element sizes.

`artifacts/task18/learned-rate-cpu64-preparation/summary.json:1` reports 352.795207 seconds for cache generation and 352.957313 seconds for its helper. I compared all 6144 ordered manifest entries with the prior corpus across ordinal, history ID, length, regime, raw hashes, file SHA256 and byte fields: they are identical and sum to **953,874,048 B**. Both cold run records report actual full-file read/SHA256 verification of that payload. I did not repeat that approximately 1 GB disk scan.

For step-2 Decimal evidence I independently summed recorded case compute time (**40.001250 s**) and maximum additional RSS (**51,675,136 B**). The driver reports about **63.900378 s**, including subprocess overhead. Its reported **54,058,712 B** artifact count is a boundary subtotal; the directory after aggregate output contains **54,062,912 B**. Likewise development `disk_bytes` 11,946,355/11,948,883 B precede later checkpoint-verification output; current corresponding directories contain 11,958,417/11,960,755 B. Closure accounting should retain these timing/measurement boundaries explicitly rather than treating the earlier subtotals as current inventories.

## Nonblocking record limitations

1. `task18_decimal_checkpoint.py:67` retains the historical phrase “uniform full initial numerical reference.” This text is stale for step 2. Actual input-root selection, checkpoint/procedure hashes, trained rates and all 24 candidate hashes establish the correct step-2 mapping. Preserve the immutable record and explain this in the closure mapping; no rerun is required.
2. Fitted `procedure.json:1` embeds inherited config numerics of `1e-5/1e-6`, while its executed procedure fields and every relevant metric explicitly use `1e-12/1e-12`. Root already ruled to preserve current source/config/checkpoint identity and disclose this discrepancy. It does not weaken these checks; later scientific configuration freeze must explicitly use the approved stricter fields.
3. The retained Jet checkpoint-verification output failure is a JSON-container serialization error after successful assertions; the corrected verification record and independently inspected checkpoint bytes substantiate the intended check. No model failure is inferred from it.

The evidence supports only the closed CPU64 learned-rate, fixed-writer, width64/two-layer, raw finite6144, 768-fit/96-development, microbatch1/effective3, two-update calibration. It provides no convergence, final accuracy, family-comparison, confirmation, or sustained-resource acceptance.
