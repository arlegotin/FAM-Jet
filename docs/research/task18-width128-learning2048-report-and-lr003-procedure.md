# Width1282048 result and next recommendation —17 October2026

The approved pair/endpoint/frozen-risk scope is complete at ddb55b7/package3a54, with no further training. Exact aggregate: artifacts/task18/width128-learned-rate-cpu64-2048-summary.json. Both numerical paths pass original1e-12; both frozen6144 passes have zero failures/invalid/unsupported flags. All96 histories are exposeddevelopment, one initialization/shared corpus; no winner, convergence or information-ceiling claim.

| Metric | Jet | Bank |
|---|---:|---:|
| Width128 FULL96 dev | .421619334 | .408106751 |
| OLD48 / NEW48 dev | .414324003 / .428914664 | .420096036 / .396117467 |
| Matched width64 at2048 dev | .425496621 | .423832815 |
| Width128 frozen6144 TRAIN | .541685463 | .535698079 |
| Matched width64 TRAIN | .562385444 | .553570180 |
| Last1024→2048 dev improvement |12.4058%|14.0556%|
| N512 / N2048 dev |.136648217 /1.064701822|.127404039 /1.043812382|
| Full learning perf seconds |375.077861|354.897956|
| Full additional RSS bytes |166707200|166510592|
| Frozen-risk seconds |73.785939|76.840294|

Shared FP64 buckets remain .136494775 overall, .041983451 at512 and .364109108 at2048. N128 recent ring retains the entire128history and is essentially exact; keep it as a learning/pipeline control, not practical compression headroom. All3 equal weights remain unchanged, no favorable posthoc slice. Wider reader yields modest fitting benefit, larger for Bank's development score, while both last doublings still improve strongly. This does not support a decoder capacity ceiling or stored-information limit. Static reader/model cost is now30221/30225parameters (241768/241800B),MAC29952/query,9345B state; capacity increase is explicitly charged.

Executed learning+endpoint+frozenrisk component total946.718781perf seconds (~15.78min), within15.5–18 forecast. Endpoint66.116731s; rawcache/preparation/calibration/oldercampaigncosts remain separate and retained. Jet outer UTC/perf376.099201/376.098454 and Bank355.904021/355.903297 agree here; no guarantee about later civil elapsed/thermal stability, no power override.

**Recommendation: one matched constant-LR3e-3 probe at the SAME width128/state/data through2048, fresh initialization, not automatic continuation or another size increase.** Threefold step size is the next already planned learning-rate dimension; compare against the retained exact current1e-3 pair on full curves/cells and frozen training risk, preserving every outcome. Current empirical risks remain high and last-doubling slopes are12–14%; this directly probes whether step size improves optimization per unique history, at low setup cost. Logged trend/reset gradient medians4.47/4.30 versus~.09–.14 in otherregimes are descriptive motivation to inspect optimizer behavior, not evidence to invent a clipping threshold. The earlier FP32 fixed-rate3e-3 negative results remain relevant negative history but do not answer this CPU64 learned-rate/current-statistics procedure. No LR or effect claim is preselected by the Jet-v-Bank sign.

Keep768fit/currenthash/96dev/raw6144/one-pass2048/seed/order/bounds/fixedwriter/FP64/chunk32/batch3/wd0/constant schedule/net192MiB exactly. Same observations0/128/512/1024/2048, no new dev seeds/scales, no simple rerun. Run endpoint fitted+uniform24 reference and one6144 frozen-risk pass each. Forecast essentially current measured~15.8min, prospectively15.5–18 executionminutes, no newrawgeneration or candidate code. Resource execution_shape already binds fullmodel/data/cache/counts/threads but excludes LR; graphs/dtypes/buffers and allocation remain same. Request explicit root approval to use that measured resource applicability for this step-size probe, with unchanged per-update cap/finite checks and new endpoint rates numerical validation. Exact config/policy/optimizer hashes bind3e-3, new fresh runs only; never resume1e-3 checkpoints under changedpolicy. If root requires a new actual calibration for LR despite graphidentity, that is a separate measuredscope decision, not a guard bypass.

On approval, close this ddb lineage at2048 explicitly underfit, promote results and LRconfigs/procedure in one results/config-only commit, preserve package3a54/rawmanifest/calibrationorigin, verify actual guards before launch; then hold newfullGit. No source/API/schedule framework needed. If root instead prioritizes schedule tuning now, it requires a prospective narrow scheduler lifecycle change and strict source-dependent preparation; that extra setup is why the constant-step probe has better immediate information per cost.

This next probe would NOT complete optimizer credibility: schedule/clipping/continuation adequacy still need evidence-based allocation. Required next frontiers also remain state/basis capacity at actual bytes, adequate full-state reader controls, polynomial/logHiPPO/delta and learned-writer task adaptation under their applicable precision/numerical gates, support calibration and independent-data retrain A/A. Their absence is unresolved scope, not defeat. State/basis/family adaptations should follow a functioning optimization comparison rather than attributing current poor fit to missing information. No blanket exclusion or finalTask18 acceptance is requested.

## Dated root ruling
17 October2026: current2048 pair/endpoint/frozenrisks accepted as exploratory only; ddb55b7 lineage CLOSED explicitly unconverged. ONE fresh matchedwidth128 LR3e-3 stop2048 pair plus sameendpointfitted/uniform24 original1e-12 and frozen6144TRAINrisk each APPROVED. All other settings/statistics/order/cap unchanged; retain1e-3 outcomes. Root explicitly accepts same measured graph/dtypes/static/shape resource applicability despite LR excluded from execution_shape by existing design. No source/API/guard bypass, new fullcalibration/rawgeneration/passingtest repetition. First meaningfulresults/config-onlycommit, actualpolicy/cacheguards, then root reads concreteconfig/launchdelta and releases. No automatic4096+, width/state/schedule/clipping/grid/protectedphase. Fresh launch `run_development(load_config(config), run_directory, stop_at=2048)`; configured32768 is not fully allocated and no1e-3checkpoint resume.
