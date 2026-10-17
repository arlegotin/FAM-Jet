# Task18 width128 operational evidence/config review — 2026-10-17

**Spec-compliance: approved for the operational evidence and expressly bounded fresh2048 allocation. Evidence/config quality: approved; no blocking findings.** This does not establish convergence, accepted scientific baselines, a family advantage, or final Task18 acceptance.

Reviewed the task brief, implementer report and new record/config delta BASE `321b01b4059469375c11f63b021800465b85defa` to HEAD `ddb55b7748e1a55dcfb1535bada6175156ae7fc7`. The previously reviewed production package remains `3a54cb7201bd8a0a888dcfa4ee09c9de581fcbab720882815a243f4c389f7bf8`; the actual profile artifacts preserve origin321b. I inspected structured records, helpers, hashes and saved tensors/checkpoint envelopes, and invoked the allocation-free configuration/policy guard. No model, raw-corpus scan/regeneration, numerical campaign or passing suite was rerun. No source/index/Git mutation occurred.

## Provenance, numerical applicability and actual profiles

`docs/research/task18-width128-closure.json:1` contains **35** promoted mappings. Every promoted file matches its original file and recorded SHA256, including the promotion-verification record added after its own earlier count of34. All **21** profile-inventory hashes and the aggregate summary hash also match. The calibration's two origin development-record hashes are valid; no origin is relabeled as the later results/config commit.

The initial and actualstep2 Decimal checks use the previously reviewed unchanged oracle helper SHA256 `dbcb91eb8e7f692d640cf77d9369b0d163be1bbdf9f9036b063a3dfe569ac717`. I verified all **48** case candidate/reference/procedure/source/raw-input mappings and each metric's unchanged `atol=rtol=1e-12`; all pass. Initial maxima are Jet0.198879465/Bank0.269351023, and actualstep2 maxima are Jet0.456885175/Bank0.258001986. Step2 maximum recorded Decimal60/80 difference is 7.6531046059491016197e-50. Original binary64 misses remain retained, including Jet step2 key-gradient ratio1.323276. This is uniform correction, not selection of favorable entries or a candidate/tolerance change (`docs/research/task18-procedures/task18_width128_decimal2.py:10`).

All four actual fitted0/2 checkpoint hashes/checksum envelopes, completed steps, origin source, canonical configs, saved rate/logit wire arrays and target-statistics identities agree with their capture procedures. Each has the common768 fit and target hash `0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21`, schema2 `observed_event_targets_v2`. All **24** fitted step0 memory/stream/feature/input-gradient captures are bitwise equal, including dtype, to the accepted initial captures at identical represented rates and input hashes. This substantiates the composition in `docs/research/task18-procedures/task18_width128_fitted_r2.py:25`.

All **48** family/step/cell fitted task/reader and terminal/stream raw-feature checks pass the original pointwise limits. Their maxima are Jet0/2 **0.1033835694/0.01397558225** and Bank0/2 **0.1033835694/0.1028344684**. They reuse the actual cold-fit checkpoints without refitting. The separately declared small initial reader check uses first ordinal0, identity transforms and no statistics fit; its candidate hashes and checks pass. It does not substitute for the full fitted checks.

As in prior accepted gates, the corrected reference certifies captured states/contractions and key/value/gate/**logit** gradients. There is no separately captured candidate raw `dL/dr`, and `query_inputs` remains shared rather than independently certified. The fitted comparison uses the common production reader/objective over independent memory features, not an independently implemented MLP oracle.

Both cold profiles completed exactly2 updates with configured horizon32768. Their saved development inventory exactly equals the common96-history inventory; final768 query rows contain96 unique histories and actual9345B payloads. Recorded full-cache reads/SHA verification cover953,874,048B in each profile. I separately compared all6144 ordered manifest entries against the retained prior raw corpus: ID/length/regime/raw/file hashes and bytes match exactly. New cache identity binds the current package, canonical DataConfig, data seed and population; the bulk disk scan was not repeated in review.

## Static and runtime accounting

I recomputed parameter and buffer bytes from the saved0/2 checkpoint tensors and checked recorded state bytes and optimizer dtypes. All model-state floating tensors and AdamW moments are FP64; step counters are FP32. Saved gradients at both updates have verified file hashes, finite values according to telemetry and FP64 dtype. The model/static ledger includes buffers rather than treating9345B as the full model footprint.

| Quantity | Jet4 width128 | Bank8 width128 |
|---|---:|---:|
| Allocated parameters | 30,221 | 30,225 |
| Parameter bytes | 241,768 | 241,800 |
| Buffer bytes | 2,128 | 2,128 |
| Total model static bytes | 243,896 | 243,928 |
| Persistent state bytes | 9,345 | 9,345 |
| Static model plus one persistent state | 253,241 | 253,273 |
| Measured cold additional RSS peak | 162,643,968 | 166,363,136 |
| Cold profile perf-counter seconds | 189.565780 | 186.822233 |

Actual ledgers are embedded in `docs/research/task18-width128-{jet,bank}-verification.json:1`. The expected29,952 MAC/query and objective-active **upper bounds**29,452/29,456 remain honestly distinguished from allocated parameters. No padding is reported. The process RSS measurements include allocated model, buffers, optimizer and runtime work and remain below201,326,592B. The static-plus-state sums above are inference storage accounting, not a substitute for measured training peak. Two updates do not prove sustained resource stability.

## Failure and clock ledger

`docs/research/task18-width128-profile-report.md:21` preserves the first external driver serialization failure after completed Jet capture: its traceback and clock record remain at `artifacts/task18-evidence/width128-initial-driver.txt` and `width128-initial-time-boundary.json`, with returncode1 and **3.318890** perf seconds. Recovery reuses the completed Jet capture; the failed helper and corrected helper are both archived. The successful initial driver costs **55.716580** perf seconds; the small reader check costs **0.122328** seconds.

The original fitted helper fails on the dtype argument before numerical capture; its failed version, traceback, **1.305156**-second external record, API preflight and corrected version are promoted (`docs/research/task18-width128-helper-recovery.json:1`). The corrected path loads the existing cold checkpoints and does not repeat the fit/profile. The separate failed ad hoc checkpoint-envelope inspection is disclosed as a metadata-only failure. Original binary64 numerical failure rows remain beside the corrected references.

Strict new-source raw preparation costs **366.310808** helper perf seconds (**366.312387** UTC), with953,874,048B payload and all old caches/costs retained. Fitted0/2 verification costs **7.122461/6.969816** seconds; uniformstep2 costs **53.649793** perf seconds. Full cold external wrapper UTC/perf pairs are **190.804476/190.804069** and **187.796919/187.796526**, distinct from internal profile durations. The report labels these boundaries and disclaims CPU-time, thermal stability and interchangeable wall-time interpretations. No power override occurred. These retained records satisfy the scoped requirement that trials, failures and their measured compute survive; they are not presented as one exact complete campaign civil duration.

## Bounded learning configurations and acceptance limits

Both new YAMLs retain CPU64, fixed writer, learned bounds[1/5224,1], Jet4/Bank8, raw width128/two-layer reader, LR.001/AdamW/wd0, microbatch1/effective3, four threads, seed, canonical population, 768fit/96dev, finite6144 and no feature cache. Their DataConfig/seed/optimizer settings match the prior common comparison. Numerics explicitly use1e-12. I loaded both and ran the actual `resolve_policy`: each passes the unchanged package/full-model/data/cache calibration applicability guard; canonical calibration and manifest hashes match. The measured calibration retains origin321b and the original profile hashes (`docs/research/task18-cpu-calibration-width128.json:1`). Existing promotion verification records the full raw-cache integrity scan, so I did not repeat it.

`docs/research/task18-width128-learning-procedure.md:18` explicitly requires **`run_development(load_config(config), run_directory, stop_at=2048)` with no resume**. The YAML32768 horizon is potential schedule context; it is not authorization to invoke unrestricted CLI/default-horizon training. The fresh pair starts under the new full Git identity, preserving strict checkpoint lineage and avoiding resume from the profile's step2 checkpoint. Only observers through2048, endpoint fitted/uniform24 checks and one frozen6144 training-risk pass per family are allocated. Current simple scores are reused. No automatic4096+, optimizer grid, width256, source change or protected phase follows.

The prospective procedure uses curves, cell slopes, empirical training risks and existing controls to inform later allocation. It explicitly retains the unresolved convergence/family-acceptance questions and does not infer convergence from matched epochs. The previous width64 sufficient-fixture control is diagnostic context, not acceptance of width128 on the actual benchmark. This meets the scoped Task18 constraints while leaving final scientific acceptance open.
