# Task19/20 statistical gate design reconnaissance

2026-10-17. Design recommendation with the explicit root sequencing ruling below; no inference-procedure change or new simulation performed. Authority: [plan Tasks19–20](../../../docs/superpowers/plans/2026-10-16-famjet.md), [spec §10](../../../docs/superpowers/specs/2026-10-16-famjet-design.md), [handoff](task-19-handoff.md), and [existing reconnaissance](bootstrap-recon/report.md). Mathematical statements below are deductions from those definitions, not external coverage guarantees.

## 1. Preserve the method; distinguish what can pass

Implement the specified crossed percentile CI, centered absolute-statistic p-value, Holm, and adaptive endpoint rule faithfully. Do not repair finite-sample behavior silently with studentization, an alternative bootstrap, a minimum S invented from this scan, or favorable fixture selection.

Existing fixed-B reconnaissance found Gaussian seed-dominated S4 coverage 213/256 and skewed S4 coverage 181/256; skewed S16 was 226/256. These remain observed failures of those tested regimes, not production-adaptive acceptance results. Sixteen endpoint diagnostic runs passed despite some populations' poor coverage. B counts computational resamples from existing data; S counts independent training replicates. Raising B cannot reveal missing seed-population tails. Raising H cannot remove the seed variance contribution σs²/S. Queries add neither H nor S.

Use orthogonal machine-readable statuses, with evidence and scope attached:

| Dimension | Statuses and meaning |
|---|---|
| Implementation | `pass/fail/not_run`: exact formula, inventory, aggregation and deterministic controls |
| Endpoint precision | `met/cap_unmet/degenerate_zero`: literal four-batch criterion |
| Statistical cell | `qualified/rejected/unresolved/not_run`: predeclared rate bounds and outer Monte Carlo evidence |
| Secondary p precision | `adequate/unresolved/not_assessed`: conditional resampling uncertainty, separate from calibration |
| Design eligibility | `eligible/inconclusive/blocked`: combines required cells, nuisance domain, precision, cost and fairness |

An expected undercoverage diagnostic can make a software assertion pass (“failure was retained and classified”), while its statistical cell remains rejected. Never convert this into “coverage gate passed.” Qualification applies only to declared fixtures/allocations; it does not prove validity for arbitrary real populations. Conservative coverage may qualify a one-sided safety floor but still fail power/width requirements.

Task19 step4 originally requires simulation checks to pass **before the scientific pilot**. Root's explicit 2026-10-17 ruling authorizes a dated sequencing amendment: if implementation is correct but relevant sampling calibration is failed/unknown, Task20 may conduct only bounded exploratory nuisance/resource estimation, including initial H128/S4. Record the amendment before any pilot; keep confirmation and inferential-success gates closed. The pilot may expand candidate H/S and estimate conservative variance/cost/distribution diagnostics, without favorable-effect sizing or unsupported nominal significance, win or strong coverage claims. Before protected execution, the fixed proposal must pass relevant predeclared production calibration and Monte Carlo gates; otherwise it remains scoped/inconclusive and protected execution stays blocked. This changes sequencing only. Expected-failure tests do not satisfy calibration.

Rationale: nuisance evidence is needed to choose a plausible allocation, while small-S inference is already suspect. Cost if wrong: an unrepresentative nuisance pilot can waste training budget and mis-size the proposal; a bounded budget, conservative uncertainty, fresh validation and the closed confirmation gate contain that risk. They do not guarantee that the eventual fixture domain represents reality.

Minimal proposed gate API: `evaluate_gate(evidence, frozen_policy) -> GateDecision`, with `implementation`, `calibration_cells`, `endpoint_mc`, `secondary_p_mc`, `scope_id`, `policy_hash`, `unresolved_reasons`, `nuisance_only_allowed`, and `confirmation_allowed`. Require actual qualified evidence for every required confirmation field; unknown is not pass. Evidence retains counts/denominators, bounds, fixture/allocation IDs, source hashes and RNG provenance. The controller consumes this decision; it must not infer permission from pytest success or a CI excluding zero.

## 2. Predeclare a compact validation matrix

Freeze fixture definitions, seeds, independent outer replication count N, candidate H/S grid, family size, error tolerances, and required versus diagnostic roles before new simulations. Preserve all existing evidence. Required roles cannot be reassigned because a result is inconvenient.

Minimal families:

1. Additive Gaussian `μ+a[h]+b[s]+e[h,s]`: pure history, pure seed, pure residual and a mixed case. Set mixed allocations by contributions to the grand-mean variance, not misleading raw variance labels. Include H128/S4 and earlier failing allocations as explicit scarcity diagnostics; select larger candidates prospectively, without claiming any universal S threshold.
2. Analytically centered/standardized lognormal seed effects from the existing report, including positive and negative location shifts. This retains the known skew failure. Add other tails only with prospective justification, not a broad distribution search.
3. Unequal stratum sizes and unequal frozen weights, stratum-specific means/variances and one shared training-seed axis. A real-workload structural case shares temporal-cluster draws across stations and includes within-cluster dependence; its cluster counts must match the proposed real design. This checks structure, not universal adequacy of 28-day independence.
4. Joint secondary comparisons with complete-null and partial-null configurations; shared latent seed/history effects produce dependence. Include independent and strongly correlated configurations, fixed family size and fixed nonnull shifts. Measure marginal null rejection and FWER over true nulls. Use the production adaptive stopping rule and the intended cross-comparison RNG policy.

Each relevant null cell measures primary coverage, primary null rejection, secondary marginal rejection and Holm FWER separately. Known-effect cells measure rejection at both signed shifts and interval width; include `±2.80√V` as the mandated planning diagnostic and a scientifically chosen effect target if declared. Inflated null rejection invalidates a power interpretation. A/A and Cartesian enumeration are deterministic controls, not evidence of population coverage.

## 3. Executable Monte Carlo decisions

Root must approve explicit tolerances, not bounds fitted to observed results. A proposed contract takes `coverage_floor=0.95−εc`, `type1_ceiling=0.05+εt`, `fwer_ceiling=0.05+εf`, `power_floor=0.80−εp`, outer error budget γ and fixed N. Nonzero tolerances disclose accepted deviations from nominal; they do not establish exact 0.05 control. A stricter root choice may leave qualification infeasible, which is an honest result.

For every Bernoulli endpoint report k/N and a binomial-tail-inversion interval. Allocate γ across all predeclared gate cells/endpoints so the displayed decision intervals have simultaneous coverage by the union bound. Derivation: each outer dataset plus independent bootstrap randomness generates one independent Bernoulli event; invert its binomial tail probabilities, then sum the allocated interval-error probabilities. This is outer simulation uncertainty, not scientific uncertainty or a model-validity guarantee.

For minimum-rate requirements: qualify when L≥floor, reject when U<floor, otherwise unresolved. Reverse inequalities for maximum-rate requirements. All required conditions must qualify. Report raw primary noncoverage and operational rejection-with-failure-policy separately; suppressing claims after cap failures must not hide CI undercoverage. Include every outer dataset in denominators; report precision-cap/invalid outcomes and their predeclared consequences. An incomplete capped simulation is incomplete, never selectively rerun until it passes.

Choose N prospectively from the desired discrimination around thresholds; `sqrt(p(1−p)/N)` is a planning approximation, not the final bound. N=256 is useful for large failures but usually cannot establish narrow tolerances. Use fresh independent validation streams for allocation qualification after any exploratory selection; retain exploration results and specify selection/validation rules beforehand. Avoid repeated fixed-confidence checking with optional outer stopping.

Correct Holm code alone is insufficient. If each true-null p satisfies `Pr(p≤t)≤t`, Holm's first rejected true null must have p≤α/m0, where m0 is the number of true nulls; a union bound gives FWER≤α. Invalid marginal p-values break that argument. The centered bootstrap plus-one formula does not itself establish that marginal property. Under skewness, percentile endpoint exclusion and absolute centered-null tail rejection differ: validate the primary and secondary rules independently.

Endpoint precision also does not ensure adequate p precision near Holm thresholds. Proposed diagnostic: binomial bounds for the conditional exceedance probability, simultaneous across the seven possible B stages and secondary comparisons, transformed through the plus-one formula. This union-bound construction remains valid when the endpoint rule selects the final stage. Compare Holm decisions using lower versus upper p bounds; disagreement means Monte Carlo ambiguity. Root must predeclare its reporting/claim consequence. Do not add unapproved p-driven resampling or replace specified p-values with bounds.

## 4. Exact, efficient implementation of the specified resamples

For stratum g with Hg histories and frozen weight wg, independently draw multinomial history counts Wbg with Hg trials and seed counts Ub with S trials. Use one Ub across every stratum and paired method:

`T*b = Σg wg × Σh,s Wbgh dghs Ubs / (Hg S)`.

Counts exactly reproduce the Cartesian product including duplicate selections; this is an algebraic optimization, not another bootstrap. Process bounded chunks using `(Wg @ dg)` followed by rowwise multiplication/summation with U; avoid materializing B×H×S tensors. Cluster selection carries all stations together. Keep weights fixed, require every expected paired cell, and reject missing/nonfinite input rather than renormalizing survivors.

Center by the single observed weighted mean. Since weights sum to one, centered resample means equal `T*b−Tobserved`; reuse the same draws. Quantile interpolation, tie rules, and deterministic RNG mapping need explicit specification. Independently keyed history/seed/batch streams preserve axes; recording algorithm, chunk policy and seeds makes replay auditable.

Start four independent batches of 500 draws; append equal-sized independent increments when doubling B through 128000. At each stage compute pooled .025/.975 quantiles and four per-batch endpoints; use sample SD with ddof=1 divided by 2. Both SEs must be strictly below .01 times pooled width. Retain stage diagnostics and final draws. Exact all-zero d has interval [0,0], p=1 and a degenerate status. Other zero-width cases cannot automatically inherit the A/A exception; root must rule on their cap/status behavior. Four batch estimates provide the specified noisy diagnostic, not a proven confidence bound.

Tiny enumerated Cartesian fixtures, translation checks and unequal-weight hand calculations provide independent implementation oracles. Full validation must call production aggregation/resampling/stopping; copying the scratch simulator is not independent validation.

## 5. Decisions and Task20 evidence

Before code/gate execution, root must settle gate tolerances/confidence/N and required scope; p-ambiguity and non-A/A degeneracy policy; quantile/RNG conventions; and where the weight contract enters the proposed API, which currently exposes strata but no explicit weights. Record the authorized sequencing amendment durably before nuisance work. Any scientific-procedure change needs a separate dated authorization.

Task20 must measure nuisance-component uncertainty, independent-seed stability, cluster limitations, actual training/query/ingest cost, fair baseline acceptance and feasible memory/time. Record raw components and `σh²/H`, `σs²/S`, `σe²/(HS)`. Optimize precision/cost under conservative nuisance ranges, validate the resulting fixed allocation with the unchanged procedure and fresh simulation streams, and freeze H/S before protected execution. Initial H128/S4 is nuisance estimation only. More seeds may be necessary but sufficiency is measured, not asserted. If no feasible allocation qualifies, report scoped inconclusive; neither extra B nor favorable observed effects can unlock confirmation.
