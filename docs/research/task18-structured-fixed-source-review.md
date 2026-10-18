# Task18 fixed-basis 8192 results and structured-reader source review

Reviewed combined BASE `2def54622c5d9a49c84145739792a084494fbbe9` → HEAD `7e0a798e8170583223bea1a49878f8569f65e8dd`: results promotion `1dbbdc7` and minimal source stage `7e0a798`. Requirements were the original Task18 brief and `docs/amendments/2026-10-18-fixed-basis-reader-followup.md`, with the final staged ruling in the fixed-basis procedure. Candidate source package: `18785561574bfb4d246f703bc1e2caff9f7764ff0b0d8d7f641bef978f4957e0`.

**Spec compliance: APPROVED for the completed exploratory results and the new source stage.**

**Code/artifact quality: APPROVED. No blocking or nonblocking findings.**

This approves neither a new scientific allocation nor whole-Task18 acceptance. The next structured numerical/probe stage requires root's separate ruling; full preparation, cold profiles and learning remain held.

## Source permission and lifecycle

The only production change is the reader alternative inside `fixed_basis_cpu64`: retain generic-contracted width128 and additionally admit structured Jet width125 or Bank width122. Parentheses keep the new alternatives confined to reader kind/width. The existing common phase/device/precision/one-hot dimensions/fixed writer/terminal encoding/support/abstention/two-layer/no-rank/no-budget-override conditions and subsequent family-specific J/fixed log-grid checks still apply. Multiscale does not gain a structured path. The change does not open generic-full, rank9, stripped bank-normalized, other widths, learned upstream, FP32 or MPS64. Data, cache and calibration policy code is unchanged.

Reference: `famjet/analysis/development.py:114`.

New tests exercise the actual factories and exports with independent literal counts: structured input dimensions105/113, allocated parameters30134/30021, MAC/query29875/29768, parameter bytes241072/240168 and buffers2288/2448. Both retain9345B state, fixed upstream and zero padding, under the approved30217/29952 ceilings. They check actual FP64 features/state/gradients and exact restored predictions. Five impossible task columns, unused support parameters and the guaranteed zero rate1/t_ref1 log column are accounted separately; objective-active counts remain upper bounds≤29258/29166. The test does not deduce inactivity from merely constant finite-panel observations or force equal parameter totals between families.

Reference: `tests/test_fixed_structured_development.py:46`.

The existing real lifecycle test now includes both structured shapes: four histories, two finite passes/eight optimizer updates, raw versus cached model and AdamW equality, sampler/consumed-ID equality, prediction equality and stop3/resume equivalence. It checks FP64 moments/FP32 counters, replay rejection, re-sealed transport/checkpoint dtype tampering, changed fit/basis identity and learned-upstream rejection. Cached timing reports zero actual encoding and128 source events per fixture update. A separate pre-allocation test rejects raw-reader calibration for the structured shape at the actual `run_development` boundary.

References: `tests/test_fixed_basis_development.py:88`, `:124`; `tests/test_fixed_structured_development.py:15`, `:81`.

Inspected retained logs and independently verified original/promoted log hashes plus report hash. RED8/9deselected; intermediate6pass/2fixture failures; GREEN8/9deselected; native covering205pass/55.04s support the report. The intermediate failures were early typed-config rejection of multiscale+structured outside the expected-exception block, corrected in the fixture without another production change. No suites were rerun.

Reference: `docs/research/task18-structured-fixed-source-verification.json:1` and its four linked logs.

## Executed results and aggregation

The three completed runs remain source `2def546…`/package `ad542def…`; the new source package is not retrospectively attributed to them. The launcher explicitly supplies `stop_at=8192`, rejects an existing output directory and records fresh/no-resume allocation and failure/interruption clocks. The aggregate checks seven prescribed observations,8192 timing rows,24576 actual source draws, four ordered6144 passes, and shared data/order/query-target identities. Its query→history-task→cell aggregation preserves equal histories/tasks/regimes/lengths and checks against central recorded losses rather than substituting a pooled query average.

References: `docs/research/task18-procedures/task18_fixed_basis_learn8192.py:10`, `:17`; `docs/research/task18-procedures/task18_fixed_basis_learning_summary.py:14`, `:24`, `:39`, `:49`.

Independently inspected the structured aggregate and all36 bundled endpoint summary/procedure/checkpoint mappings. They bind to the correct8192 checkpoint, common target statistics and executed helper; all active metrics retain pointwise atol=rtol=1e-12 and pass. Exact terminal/raw replay is explicit. Worst ratios Jet.002772412/Bank.001581835/multiscale.398650045 match the report. The endpoint helper checks initial-reference source/package and reference-definition file identity before composing unchanged fixed-memory evidence. Common production MLP/query-input and objective limitations remain explicit; no independent reader implementation or fixed-rate gradient claim is inferred.

References: `docs/research/task18-procedures/task18_fixed_basis_endpoint8192_case.py:26`, `:37`, `:50`, `:58`; `docs/research/task18-fixed-basis-learning8192-evidence.json:1`.

Frozen TRAIN evaluation reconstructs the saved model without fitting, uses `eval`/`no_grad`, reads exactly6144 fixed-feature records, retains flags and every history row, and applies existing `history_loss`. A model failure causes an objective failure rather than silent exclusion; the focused existing-loss lookup confirms this. Actual three risk summaries have512 histories in every length/regime cell and all flags zero. The21 development observations likewise have zero reported failure/nonfinite/fallback/infinite/quarantine flags. TRAIN and exposed development results remain separate.

References: `docs/research/task18-procedures/task18_fixed_basis_frozen_risk8192.py:20`, `:28`, `:37`; `famjet/train.py:120`.

Verified the promoted bundle SHA and13 exact-copy mappings, and checked the critical36 endpoint relationships and aggregate scalars. Root's existing131-original-SHA verification and previously accepted cache scans were not repeated. The126-record bundle retains complete endpoint/risk/procedure/clock metadata; binaries and full rows remain explicitly referenced, not falsely claimed promoted.

## Claims, accounting and remaining scope

Reported curves correctly show Bank's best observed4096 loss.391406724 slightly below Jet's8192 loss.391915604, with shared buckets.136494776 substantially stronger. Both the report and amendment treat all three arms as unconverged and deny a practical Jet advantage, family defeat, freeze-only causal contrast or protected inference. Long-cell and TRAIN errors remain visible. The original baseline/convergence requirements are unresolved, not declared satisfied by equal update counts.

All reported net peaks are below201326592B. Endpoint tensor totals separately retain241736B parameters and2160/2192/2224B buffers; earlier complete Python/config/basis ownership is correctly identified as a preparer snapshot, not a newly measured endpoint allocator total. Cached updates report zero encoded events and22020096 source events per family. External preprocessing and the retained failed preparation remain in earlier setup accounting. Recomputed current-stage learning+endpoint+risk total is1467.8430695819552s; prior1975.089738s setup is separate, with older costs additionally retained. Per-run UTC/perf and overall orchestration span are distinguished without speed, thermal or forced-wake claims.

References: `docs/research/task18-fixed-basis-learning8192-report.md:3`, `:11`, `:17`, `:27`; `docs/research/task18-procedures/task18_fixed_basis_learning_summary.py:53`.

Review was read-only apart from this requested report. The diff was read/parsed once with structured views for bulky records; only truncated helper/lifecycle context and the concrete loss-failure question required focused follow-up reads. No models, training, preparation, numerical campaigns, full cache/corpus scans, suites, source edits, Git mutations or subagents were used. Whole Task18, broad baselines and convergence remain OPEN; protected phases remain closed.
