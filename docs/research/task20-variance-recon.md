# Task20 stratified variance and allocation reconnaissance

2026-10-17. Design only; no tests, simulations, training, pilot/protected draws, downloads, or production changes. Sources: [Task20 brief](task-20-brief.md), [Task20 handoff](task-20-handoff.md), [Task19 handoff](task-19-handoff.md), [spec §§9–10](../../../docs/superpowers/specs/2026-10-16-famjet-design.md). This independently derives a nuisance/planning contract; [Task19 inference design](task-19-design-recon.md) remains authoritative for its separate calibration and Monte Carlo questions. Recommendations below require root rulings, not automatic adoption.

## 1. Estimand and second-moment assumptions

For frozen regime/length strata g=1,…,G, use positive frozen weights w_g summing to one and independent histories h=1,…,H_g. Every history has the SAME ordered S paired training replicates. Work on already aggregated paired effects, never query rows:

`d_ghs = μ_g + a_gh + b_gs + e_ghs`,
`T = Σ_g w_g mean_h,s(d_ghs)`, `E[T] = Σ_g w_g μ_g`.

The μ_g are fixed and all random effects have mean zero. History effects have variance A_g and are independent across histories and strata. Seed vectors `b_s=(b_1s,…,b_Gs)` are independent across s with covariance matrix B; their components may be strongly correlated. Residual interaction has variance E_g and is uncorrelated across distinct cells, with zero covariance with history/seed effects. Independence of these components is sufficient; zero cross-covariances suffice for the variance identity. Finite second moments and a stable training/evaluation population are required. Gaussianity is NOT required here. A centered history×seed interaction may satisfy these covariance conditions without being independent; the stronger Gaussian bounds below then need separate justification.

One training replicate means the predeclared complete random training procedure. Independent initialization on a common fixed training stream supports conditional-on-that-stream variation only. Varying training data/order must be declared and retain the common frozen training-only scales, t_ref and priors; it cannot silently inherit Task18's initialization-only interpretation. Shared evaluation histories across strata, shared temporal shocks across nominal clusters, correlated replicates, or incomplete crossing invalidate this simple contract unless separately modeled. Within-cluster observations must first aggregate to the declared independent history/cluster unit.

Expanding T and removing zero cross-covariances gives exactly, under these assumptions:

`V({H_g},S) = Σ_g w_g² A_g/H_g + τ/S + Σ_g w_g² E_g/(H_g S)`,
`τ = wᵀ B w = Var(Σ_g w_g b_gs) ≥ 0`.

Fixed μ_g differences contribute NOTHING. Independent panels make history/residual terms diagonal across strata; shared seeds make the seed term a full covariance quadratic form. Replacing τ by `Σ w_g² B_gg` is wrong in general. If `H_g=p_g H` for a fixed allocation p, then the spec shorthand holds with `σ_history²=Σ w_g² A_g/p_g`, `σ_residual²=Σ w_g² E_g/p_g`, `σ_seed²=τ`. Integer rounding changes actual p; evaluate using actual H_g. No fixed scalar history component can describe arbitrary reallocations.

## 2. Practical moment estimator for unequal H_g

Require a complete finite H_total×S matrix, declared row strata, matched unique history IDs and common ordered seed IDs; each H_g≥2 and S≥2 for nuisance estimation. Let r_gh be a row mean, c_gs a column mean and m_g the cell grand mean. Define:

`Q_g = Σ_h (r_gh−m_g)²/(H_g−1)`,
`R_g = Σ_h,s (d_ghs−r_gh−c_gs+m_g)²/[(H_g−1)(S−1)]`,
`C_gk = Σ_s (c_gs−m_g)(c_ks−m_k)/(S−1)`.

Row centering removes the seed average; double centering removes both main effects; column centering removes the history average. Consequently:

`E[Q_g]=A_g+E_g/S`, `E[R_g]=E_g`,
`E[C]=B+diag(E_g/H_g)`.

Thus retain raw moment estimates:

`Â_g=Q_g−R_g/S`, `Ê_g=R_g`,
`B̂=C−diag(R_g/H_g)`,
`τ̂=wᵀ C w−Σ_g w_g² R_g/H_g`.

These estimates are unbiased under the stated second moments; they are not guaranteed nonnegative in a particular pilot. Unequal H_g only change the diagonal residual correction. C has rank at most S−1, so S4 does not identify a stable general covariance structure across many strata, even though the single frozen-weight τ remains a valid estimand.

For this one frozen weight vector, estimate `wᵀ C w` directly as sample variance across s of `z_s=Σ_g w_g(c_gs−m_g)`. This avoids an unnecessary ill-conditioned covariance projection; retain B̂ for diagnostics if useful. Proposed plug-in planning values: `A_g^+=max(Â_g,0)`, `E_g^+=R_g`, `τ^+=max(τ̂,0)`. Keep these separate from all raw values and flag every truncation. Do not clip B̂ entrywise: legitimate negative covariances matter. A PSD projection would be another explicitly recorded planning approximation, unnecessary for a fixed w and not a confidence bound. Changed weights require recomputation and a new frozen estimand.

The plug-in V is nonnegative and useful for candidate comparison. Truncation raises negative estimates to zero but provides no upper-confidence guarantee. Near-zero estimates can reflect cancellation, sampling noise, or insufficient independent variation. A zero pilot seed component is not proof that additional seeds are useless.

## 3. Scarce-seed uncertainty: three distinct claims

**Analytical variance:** the V identity above follows from assumptions and is exact for the mean, not for percentile interval coverage or power.

**Planning approximation:** clipped moments, a declared safety multiplier, component sensitivity ranges, leave-one-seed-out diagnostics, or nuisance-bootstrap quantiles can support transparent robustness exploration. They must be labeled approximations, not conservative confidence bounds. S4 has only three seed variance degrees of freedom; splitting/deleting seeds can expose fragility but cannot certify missing tails. More H, queries or bootstrap draws cannot establish the unseen seed distribution. No finite distribution-free upper bound on seed variance follows from four draws and finite variance alone: distributions with a rare, arbitrarily large centered seed effect can produce the same benign-looking sample with high probability while having arbitrarily large variance. A known support or an explicit tail restriction could change this conclusion; none is established here.

**Optional model-conditional upper bound:** if root expressly adopts mutually independent Gaussian history/seed/residual components, jointly Gaussian seed vectors independent across s, and iid Gaussian residual cells within each stratum, simple deliberately loose bounds avoid subtracting noisy components. Let fixed pilot sizes be H_g0,S0, `q_ν(α)` the lower α quantile of χ²_ν, and preallocate positive errors α_Ag, α_Eg, α_τ whose sum is at most α. Define:

`U_Ag = (H_g0−1) Q_g / q_(H_g0−1)(α_Ag)`,
`U_Eg = (H_g0−1)(S0−1) R_g / q_((H_g0−1)(S0−1))(α_Eg)`,
`U_τ = (S0−1) sample_var(z_s) / q_(S0−1)(α_τ)`.

Derivation: Gaussian centered row-mean contrasts have H_g0−1 independent normal coordinates with variance A_g+E_g/S0; centered residual contrasts have (H_g0−1)(S0−1) independent coordinates with variance E_g; centered weighted column contrasts have S0−1 coordinates with variance τ+Σw_g²E_g/H_g0. Their normalized squared lengths are sums of squares of independent standard normals. Lower-tail inversion gives each upper bound for the corresponding nonnegative sum, hence also for A_g or τ individually. A union bound needs no independence among these three groups of statistics. With probability at least 1−α, all components are bounded simultaneously, so

`U_V({H_g},S)=Σw_g² U_Ag/H_g + U_τ/S + Σw_g² U_Eg/(H_g S)`

bounds all candidate variances simultaneously, even if one candidate is selected from this same bound surface. Deliberate double counting of pilot residual uncertainty makes this loose. It is a finite-sample bound ONLY inside the declared Gaussian model, not a bound for arbitrary history×seed interactions, skewed training outcomes, percentile coverage, or scientific model misspecification. S0=4 uses ν=3 for U_τ and can produce very wide bounds; no numerical threshold or confidence budget is authorized here. An S4 normality diagnostic cannot validate the Gaussian assumption. The observed skew-fixture failures in the Task19 handoff make an unqualified Gaussian guarantee particularly inappropriate.

These fixed-sample confidence claims do not survive repeatedly expanding the pilot until the bounds look favorable without an explicit simultaneous-over-looks error allocation or a fresh fixed-size estimation panel. Candidate selection on one simultaneous surface is distinct from optional sampling of that surface. If root declines the Gaussian assumptions, report component scenarios and `uncertainty_status=unresolved/model_approximation`; expand independently trained nuisance replicates under the authorized exploratory budget. Do not invent a universal sufficient S or substitute a parametric interval into Task19 inference.

## 4. Precision and H/S allocation

Return `sqrt(V)`, mandated `MDE_approx=2.80 sqrt(V)`, and optionally normal-reference total width `3.92 sqrt(V)`. These are planning scales; neither normal-reference number predicts actual crossed-percentile width/power at scarce S without the separate Task19 validation. Use a predeclared scientifically relevant precision/effect target, not the observed favorable T. Report component contributions as well as raw variances; τ/S can dominate despite a small raw τ.

A minimal separable measured cost model is

`Cost = C_fixed + S C_train_pair + Σ_g H_g [c_g,delivery + S c_g,paired_eval]`.

Train each paired replicate once for the whole panel, not once per stratum. Delivery/preprocessing shared across seeds is charged once where actually reusable; ingest/query/reader and serialization costs enter the measured appropriate term. Include validation/checkpoints in training. Cache construction and delivery are distinct; disclose amortization. Enforce measured memory/chunk/thermal/latency limits separately. Nonlinear batching and fixed startup costs require measured candidate forecasts, not this formula forced onto unsuitable data.

For fixed S set `K_g=w_g²(A_g+E_g/S)` and `c_g=c_g,delivery+S c_g,paired_eval`. With residual budget `B'=budget−C_fixed−S C_train_pair>0` and positive K_g,c_g, minimizing `ΣK_g/H_g` subject to `Σc_g H_g=B'` gives

`H_g = B' sqrt(K_g/c_g) / Σ_j sqrt(K_j c_j)`.

This follows by setting `−K_g/H_g²+λc_g=0`; minimum history/residual variance is `(Σsqrt(K_g c_g))²/B'`, plus τ/S. Apply the same formula to a declared upper-bound/scenario surface when appropriate. For fixed total H instead of budget, allocation is proportional to sqrt(K_g). These are continuous optimization aids, not final designs. Respect every frozen stratum's positive minimum quota even when K_g estimates zero, round to integers, then recompute exact cost and V. Enumerate feasible S and nearby integer allocations; report the precision/cost frontier and why a fixed candidate meets the declared target. If τ/S alone exceeds the variance target, increasing histories cannot rescue that candidate S. No candidate chosen by effect sign, no adaptive confirmation sample expansion.

## 5. Minimal API and meaningful future fixture checks

Preserve required positional interfaces; proposed additions:

`estimate_variance(d, *, strata=None, weights=None) -> dict`

Here d is rows×shared-seeds, strata labels rows, and weights maps exact declared labels to frozen weights. No strata means one stratum; omitted weights with strata means equal recognized strata only under Task19's declared convention. Never infer weights from row frequencies. Missing/extra/duplicate scientific units are rejected by paired inventory validation before this call; the ndarray alone cannot detect duplicate histories or mismatched seed identities. Return actual counts, weights, estimator version, Q/R/C or weighted seed scatter, raw A/E/B/τ, distinct planning components, degrees of freedom, truncation flags, and assumption/uncertainty status. No hidden Gaussian default.

`plan_precision(variance, costs, candidates, *, allocations=None, uncertainty=None) -> list[dict]`

Preserve `(H,S)` candidates with H explicitly TOTAL independent histories. For multiple strata, require an explicit H→{g:H_g} allocation mapping (or a versioned frozen allocation rule); verify sums and labels, and evaluate actual denominators. Compare alternative allocations in separate calls or later extend the candidate schema explicitly. uncertainty selects plug-in, disclosed scenarios, or an independently specified model-conditional bound with its error budget and assumptions; unrecognized/missing required evidence blocks qualification. Each result includes H_g,S, component contributions, variance basis, approximate MDE/width, measured cost provenance/feasibility, and separate precision versus inference-eligibility status. This planner cannot unlock confirmation.

Meaningful deterministic fixture specifications for later implementation, not tests executed here:

1. **Additive, unequal panels:** centered row/seed arrays, H_1≠H_2, nonuniform w, residual zero. Hand-compute sample row variances/seed covariance, candidate V and 2.80√V. Adding any fixed constant to each entire stratum changes T as prescribed and leaves every variance component unchanged. Relabeling histories or jointly permuting seed columns leaves estimates unchanged.
2. **Correlated shared seeds:** w=(1/4,3/4), b_1=z,b_2=2z gives τ estimate `(7/4)² sample_var(z)`, not `(1/16+9/4) sample_var(z)`. With b_2=−z/3 it cancels exactly. Independently permuting one stratum's seed labels breaks pairing and is an inventory error, not an allowed invariance.
3. **Residual correction/negative moments:** nonzero matrices with zero row and column sums yield Q=C=0 but R>0, hence negative raw Â and τ̂. Verify raw retention and separate clipping, finite nonnegative planning output, and absence of a conservative-confidence label. This also tests the unequal-H diagonal corrections.
4. **Allocation:** a hand-specified component dictionary verifies separate H_g denominators, the fixed-p shorthand only where applicable, seed variance unchanged when only H grows, monotone plug-in variance with larger H_g/S, integer quotas and training charged S times, not G×S times. Query duplication leaves the independent-unit inventory and H unchanged.
5. **Limits:** nonfinite/missing cells, one-seed or one-history nuisance estimation, wrong weights/counts, and absent allocation are explicit failures. All-zero and tiny components retain unresolved sampling uncertainty; zero estimated variance does not authorize a new degeneracy/inference rule. Large location shifts and small centered effects exercise stable arithmetic without claiming population calibration from fixtures.

## 6. Numerical discipline and root decisions

Compute moments from centered, suitably scaled values in float64; avoid unscaled raw sums/squares and covariance subtraction of huge uncentered stratum means. Weighted centered column combinations avoid mixing enormous fixed μ_g into seed scatter. Record scale handling, use nonnegative sum-of-squares calculations for Q/R, and preserve small signed MoM differences. A small rounding tolerance may flag cancellation but must not silently erase a scientifically real near-zero component. If a raw variance is unrepresentable while a mean-variance contribution is representable, retain an explicit scaled representation or block unsupported output honestly; do not turn overflow into zero/NaN-skipping. Planning square roots/contributions also need scaling. Extreme-offset information already lost in input float precision cannot be reconstructed.

Root must rule before implementation/freeze on: (1) exact regime×length labels, weights, total-H meaning and candidate allocation/minimum quotas; (2) what independent training replicates vary and the conditional population/frozen fit panel; (3) this complete-crossed second-moment scope versus any actual shared-history/cluster dependence; (4) scalar clipped moments as a labeled planning approximation, and the permitted uncertainty family, confidence budget/scenario ranges and bounded nuisance expansion policy; (5) declared precision target and cost/amortization/feasibility policy. Root must not call S4 clipping, resampling percentiles, arbitrary inflation, zero effects, or a Gaussian formula without its assumptions a conservative bound. Existing sequencing amendment/calibration decisions remain separate: nuisance-only permission precedes any pilot, and a frozen proposal still requires Task19's relevant fresh production qualification before protected execution. No estimator or inference-protocol change is authorized by this report.
