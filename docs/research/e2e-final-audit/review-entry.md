# Final whole-branch review entry

Base: `78f7ba8` (original task start; current main was explicitly authorized). Head: `ed7060b40b1c2b88239232819e2ef9d0e372d6d7`. This is the single final whole-branch review, after task-scoped reviews and actual execution/replay. No merge or push is requested.

## Review package and coverage

- Complete original-base package: `.superpowers/sdd/2026-10-16-famjet/review-78f7ba87..ed7060b4.diff` (525,371,029 bytes, 295 commits). It includes all raw evidence and the 45-MB canonical machine JSON. Do not dump the full file into context.
- Source/test/config focused full diff: `.superpowers/sdd/2026-10-16-famjet/e2e-final-source-tests.diff` (3,214,686 bytes). Source can be inspected directly in bounded passes; all branch changes remain available in the complete package.
- Prior evidence index: `.superpowers/sdd/2026-10-16-famjet/e2e-final-evidence-index.md` (historical gate boundaries, recorded tests and preserved failures; R7 status there is historical and superseded by actual proofs below).
- Deferred/parked ledger context: `.superpowers/sdd/2026-10-16-famjet/e2e-final-open-observations.md`; full progress ledger alongside it. Triage these explicitly.
- Claim boundary scratch map: `.superpowers/sdd/2026-10-16-famjet/e2e-final-claim-map.md`. Its pending-recovery wording is superseded by the successful actual proofs. It is an attention aid, not source authority.

Given the raw volume, report risk-based coverage honestly: critical source paths read, evidence checked, areas sampled or declined, and limits. Do not imply every raw prediction line was manually reviewed. Do not spawn subagents or rerun already recorded unchanged suites. A specific unresolved concern may justify a small read-only verification, not another experiment.

## Binding requirements and adopted scope

User: deliver PoC end-to-end, current branch, meaningful commits, Superpowers and subagents. Core runs on this M3 Max locally, with no required cloud model/API/GPU/extra machine. Source authority includes the supplied research plan and `docs/superpowers/specs/2026-10-16-famjet-design.md`; the entered finite completion is defined by:

- `docs/superpowers/specs/2026-10-24-famjet-core-delivery-design.md` and matching plan;
- the exact linked model/data and conditional-inference contracts;
- `docs/superpowers/specs/2026-10-25-evaluation-budget-design.md` and dated policy;
- `docs/superpowers/specs/2026-10-25-sealed-report-recovery-design.md` and matching plan.

The executed study is fixed-writer CPU64, known one-hot keys, Jet4 versus Bank8 at equal actual persistent bytes (9345 B for K16/V8;1665 B for K12/V1), query-conditioned coordinate-shared ridge readers, finite development search, hard-window observed-event means and adjacent contrasts. The inference estimand is conditional on the actual frozen fits/corpus/preprocessing/selection and excludes retraining variation. All methods receive equal causal events/public query information; bounded readers get snapshots and queries, no raw history/cache off-budget. Count static weights and actual resources separately from state. Primary-valid queries retain losses/fallbacks; invalid labels are explicit, never silently zeroed or used as independent replications.

Both independent synthetic panels contain3072histories,12strata×256, plus192pilot. The only entered eight methods are Jet,Bank,exact,recent,latest-LRU,reservoir,buckets,Laguerre numerical control. Seven have deployment timings; Laguerre latency is unmeasured/null. Modern/HiPPO mechanisms have historical smoke/implementation evidence, not current all-family competitiveness evidence. Learned-writer/dense-key/generic-full-state superiority, probing/interpolation/language/agent and multi-budget frontier claims remain unentered. Gamma equivalence defeats broad architectural novelty, not the narrow empirical question.

Beijing uses observed scalar PM2.5,12stations,training-only normalization,chronological splits,56nonoverlapping14daytestblocks,120queries/block,allstationsclusteredtogether. Both shape-matched calibrated synthetic-frozen and real-trained modes execute. Native contrast inversion must scale without adding a mean.28-/56day resampling uses28/14finite-periodclusters and is not future-population significance.

## Actual execution and report recovery

Original run06 source f886e3c41517fd935a642cb83233dd72faf083b0; all116publicfits,timing/stress,36syntheticcells,16realmethodstages,releases and inference completed. OriginalCLIexit1 is preserved: report reader rejected the same288unique run IDs because Bank/Jet ordering differed. Original wall25786.649029s, sampled owner+owned-groupRSSpeak1212088320B,no externalcap violation; original clocks/raw files untouched.

Original full74-file execution identity b994b3ef7b770fb50db7adba3a9125f75c7c5dc1a4cd3dc3d85843d3177e1260 is archived at `docs/research/e2e-run06-execution-source/`. Full original inventory/failed ledger/witness is `docs/research/e2e-run06-execution-record/`; bulk4813files2.062GB+fourprepfiles10.16MB remain ignored/local. Complete285608419-byte tarball is locally retained with recorded SHA.

R7 changes only report_inputs among the74existing executable/lock paths. General protected/run policy/execution APIs remain strict; no original hash rewrite or scientific resume. Fixed migration pins old/new complete maps, all original artifacts/clocks/failure/index and independently pins the external launcher. Old execution and corrected reporter provenance are separate. R7 source review/repaired98-test evidence is `docs/research/e2e-report-recovery-acceptance/` and source-evidence directory.

Actual recovery and clean portable replay both passed at code/source Head4e073f86, unchanged current executable1bd8aca2d561f7412995c87dd183f908918c5f0ad0aef2006c75f3362f3c0703. Proof: `docs/research/e2e-report-recovery-actual/index.json`. Recovery68.615s/1057259520BRSS; clean replay70.188s/1083965440BRSS, both exit0/no externalguard. Original run,prep and archived-source locations were unavailable during replay then restored.4813+4+74originalfiles remained byte-identical. All seven deterministic MD/JSON/chart-data/SVG/renderer-receipt files matched exactly; only separate recovery receipts are volatile. No fitting or data generation happened in recovery.

## Result and current deliverables

- `reports/famjet-poc/final.md` (full human report), `final.json` (45MB; extract fields), chart data/threeSVGs/renderer receipt, bundle README.
- `docs/research/e2e-completed-core-result.md`, main README, AUDIT, PROGRESS, DECISIONS.
- Main H1 result: confirmation Bank−Jet D+.03535376646 interval[-.019711263,.090418796];replication D+.03968307886 interval[-.012747851,.092114009]. Both point estimates favor Jet; both intervals includezero =>superioritynotdemonstrated/inconclusive.
- Mean losses confirm Jet.15649/Bank.19184/buckets.12862;rep Jet.16638/Bank.20607/buckets.14074. Do not turn observed bucket means into an unregistered all-family significance test.
- Sensor frozen-transfer JetRMSE130.49 vsBank1069.5, both worse than simple summaries; real-trained Jet68.642 vsBank21.36µg/m3(RMSE), MAE15.354vs12.705. Interpret only this fixed reader/task/finite period.

Review the main claims, numerical/data/statistical correctness, causal/budget contracts, resource/provenance and recovery, source licenses and reproduction/docs expectations. Include ordinary use problems that matter to a reasonable user, even if a spec does not enumerate them. Make no findings about code not actually read. Keep oldfailedgradient/MLP/extreme-cancellation/binding/bootstrap/calibrationattempt1 and priorabortedruns failed; current ridge/conditional path does not repair them.

## Read-only contract and output

No source/index/HEAD/branch edits, no subagents, no worktree/checkout/reset, no experiment reruns or paid/remote assets. Use git show/read-only comparisons if an old revision is needed. Do not unblind excluded old04 private scores; its metadata and hashes are enough. Current completed run06 results are fully released.

Write `.superpowers/sdd/2026-10-16-famjet/e2e-final-whole-branch-review.md` with strengths, Critical/Important/Minor findings(file:line/why/fix), explicit declined-to-judge list and risk-based coverage, requirements alignment, and clear ready-for-handoff verdict. Exactly one final fix wave is available afterward; present all actionable findings together.
