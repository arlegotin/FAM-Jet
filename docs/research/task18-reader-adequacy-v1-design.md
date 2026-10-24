# Task18 reader adequacy v1 — proposed root decisions, 24 October 2026

DESIGN ONLY. These routine methodological choices are proposals for Root's independent builder check and dated adoption, not user-agreed choices or an execution release. Original Task18 execution remains authorized.

## Purpose and scope

Test whether generic readers exploit the same fixed retained information. Preserve CPU FP64 Jet4/Bank8, K16/V8, 9345B/history, original three lengths/four regimes/Q8, observed-event-v2 labels and common target scales. No new population, writer, precision, protected/statistical pilot, language arm or capacity claim. Panel04 achieved Jet .2804328338/Bank .1918295624, Bank leading every length; these kernel results are achievable references, not information bounds.

Existing `TaskModel.features` supplies 72 contracted or 1152 full floating coordinates plus 25 query fields; `NumericReader` supplies two SiLU layers, a numeric head and unused primary support head. `make_reader` can silently factor full input under ceilings. The historical .394466/.388818 results instead used FP64 structured widths125/122, epsilon1e−6, FP32-presented generator values promoted to FP64, and four passes over6144 histories. They are not this controlled comparison.

## Alternatives and chosen frontier

A 32k flat full reader forces premature low-rank compression across keys. A query-routed shared network avoids that restriction but inserts explicit contraction bias. Choose unfactorized flat full access at a larger declared frontier, with both small and budget-matched contracted controls. No residual/kernel shortcut enters a generic arm. Structured formulas and recovered gamma coordinates receive numerical controls only; further trained structured/routed/residual arms require another bounded proposal.

Use an external primary-only MLP: Linear(D,w), SiLU, Linear(w,w), SiLU, Linear(w,8), all biases, rank=None. No support head, padding, dropout or unused task columns. Every parameter participates in the objective; report actual gradient activity separately from nominal active counts.

| Arm, each family | D | w | Active parameters | Dense MAC/query |
|---|---:|---:|---:|---:|
| C128 |92|128|29448|29184|
| C558 |92|558|368288|367164|
| F256 |1172|256|368136|367616|

High-tier mismatch is152 parameters (0.042%) and452 MACs (0.124%), explicitly reported. Families match exactly within each arm. Count feature standardization, advancement, contractions, activation/bias work and full-state bandwidth separately; dense MACs are not total compute. No claim that width256 is an optimal decoder.

## Exact read contract

For each present query, copy-advance from saved last_time to T using existing exact timestamp differences: d=lambda*Delta, a=exp(−d), Z'=aZ, H'=aH+adZ, with existing complete-decay handling. Never alter the snapshot. C inputs use existing caller-anchor order `[u(8),h(8),z,b]` per Jet anchor or `[u(8),z]` per Bank anchor, where contractions use the public key p. F inputs concatenate flattened Z then H for Jet, Z for Bank, in existing tensor axis order; every floating coordinate appears once.

Append `[p(16),onehot(mean,contrast)(2),age_start/t_ref,age_end/t_ref]`. No absolute times, IDs, hashes, query ordinals, labels, regime or length metadata. Use frozen t_ref=1 from original training fit. Fit each input column's mean/population-SD on original768 training histories only; zero SD becomes1, no amplitude division/clipping. Thus all real inputs are dimensionless or training-standardized. Frozen target mean/scale invert the eight numeric outputs. Masks and signed values retain original semantics; invalid primary labels stop the data stage rather than resampling.

Return numeric `ReadResult`, deterministic numerical support only, explicit failure/prediction-valid diagnostics; no learned confidence. Central `score_predictions`/`aggregate_scores` v2 supplies unconditional training-mean fallback, quarantine, complete inventory and equal task/history/regime/length weighting. Every failed prediction remains scored; no abstention deletion. Inference receives only immutable snapshot, public queries and frozen statics in a fresh worker, never raw histories or training caches.

## Data and finite training

Copy exact represented rates/kernel settings from panel04's family statics (eps1e−8, kernel support_floor1e−12); only training chunk_size changes128→32, subject to equivalence gates. Preserve original768 training-only target hash `0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21`. Reproduce existing96 development identities/hash bindings from panel04, explicitly exposed. New optimization seed is `derive_seed(20261024,'task18_reader_adequacy_v1','training')`; generator namespace training, IDs `t18ra1-train-{i:012d}`. Length cycles128/512/2048; regime is REGIMES[(i//3)%4]. Draw i is never reduced modulo a corpus. All arms/families share draw/query/label hashes and batches i=3s..3s+2 at zero-based step s. Maximum49152 unique optimization histories. Keep original generator/config fields otherwise unchanged.

Initialization seed `derive_seed(20261024,'task18_reader_adequacy_v1','init')`, reset for every trial; direct FP64 default Linear initialization. AdamW betas(.9,.999), eps1e−8, wd0, constant LR{.001,.003}, global gradient-norm clipping1; CPU one thread, micro1/accumulate3. Objective equals frozen task-normalized MSE, averaging four queries/task then two tasks/history. No writer gradients/BPTT.

Screen both LRs through2048 updates for each arm/family. Select lower complete dev loss; tie lower measured total trial seconds then config hash. Continue its exact optimizer state to8192; observe0/128/512/2048/4096/8192. At milestones also score frozen first384 optimization histories (32/cell), labeled empirical TRAIN. Continue once to16384 only if either TRAIN or dev improves >1% over4096→8192; otherwise stop. Maximum110592 updates across12 initial trials plus six winners; no new seed/LR/restarts. Checkpoints retain initial, latest, previous and selected, optimizer/RNG/draw offset/statistics/source identities; interrupted attempts are charged, resume only exact identities, never reset budget clocks.

## Gates, resources and interpretation

1. Source/numerical: first-component brief; all field, FP64, mask, immutability, unit/shift, terminal/stream and gamma controls pass original1e−12 tolerances. No old StageA/native/statistical reruns.
2. Tiny fit: the multi-key two-age sufficient fixture below must fit every arm/family within its finite allowance, with finite nonzero reader gradients and query-selection sensitivity. Failure blocks development allocation and means reader/training failure.
3. Feasibility: separately release full768 preprocessing, existing96 dev, 384 fresh training histories and128 updates for each six-arm configuration at LR.001, including checkpoint/resume. Probe seed uses the training derivation with final tag `feasibility`, IDs `t18ra1-probe-{i:012d}`; retain the same cell cycle. These are charged discarded probes, not candidate screening. Measure generation, chunked terminal encoding, transport, reader forward/backward, validation and peak/output bytes. Forecast the complete schedule from measured blocks, not panel04's ~17.2s/16s streaming encodes or guarded-reader latency.
4. Development: release only after gates and measured forecast fit ceilings. Nonfinite loss/gradient/weights or resource exhaustion immediately fails that trial, retaining artifacts and fallback rows; common data/source failures stop all arms. Missing milestone is incomplete, never a selectable survivor. No failure retry; failed-arm tuning remains charged.

Proposed ceilings: numerical+tiny-fit1200s, feasibility1800s, development7200s total; 1GiB incremental RSS, 2GiB new output, minimum4GiB free+speculative RAM/4GiB disk and25% RAM reserve. Stop before exceeding; no invented throughput. Cache packed numeric terminal snapshots/query-label records, at most256 resident histories; bind data/query/label/source/writer/rate hashes. Reader updates do not invalidate fixed states. Charge all cache construction and repeated attempts; use terminal chunk32 equally, retain actual incremental ingestion timing separately.

Operational plateau requires both last two doubling relative changes ≤1% in absolute magnitude for TRAIN and dev, using max(previous_loss,1e−12) as denominator; otherwise mark unconverged. Reader adequacy against reference requires complete finite curves, fixture success, and selected dev loss ≤1.05× frozen family kernel loss overall and at every length. Use panel04's selected Jet rho.01 and Bank rho1e−10 for every length, never lengthwise ridge reselection. Failure rejects only this procedure. Report all tiers, costs, cells and failures; plateau is no optimality certificate.

## Source transition

Choose small versioned `validation/reader_adequacy_v1/` diagnostic, not core registration. Pin new source/manifest separately while preserving all53 famjet files (package15cf84…), all15 StageA files, lock and historical88-row material manifest d0669ad0…. Old one-use paths/results, A06 failures and Task19 failures remain immutable. This placement preserves existing strict source tests without permanent core freeze: future core changes require an explicit archival-source test migration, not weakened hashes. Every new study phase gets fresh run IDs/artifacts; no current CLI is promised.
