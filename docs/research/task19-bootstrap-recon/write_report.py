"""Render the bounded reconnaissance results without importing project code."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
main = json.loads((HERE / "coverage.json").read_text())
controls = json.loads((HERE / "controls.json").read_text())
endpoints = json.loads((HERE / "endpoints.json").read_text())
cells = main["scenarios"] + controls["scenarios"]


def event(x):
    lo, hi = x["wilson95"]
    return f'{x["count"]}/{x["n"]} = {100*x["rate"]:.1f}% [{100*lo:.1f}, {100*hi:.1f}]'


text = r"""# Crossed-bootstrap reconnaissance for Tasks 19/20

Date: 2026-10-16. This is prospective protocol validation on independent statistical fixtures, not scientific data or protected output. No production code, tests, configuration, manifests, git state, or frozen method was changed. Source authority: design spec §10 and task-19/task-20 briefs, read locally. No external factual attribution is needed; formulas below are deductions from the declared model.

## Finding and scope

H128/S4 is suitable as a **starting nuisance-estimation pilot**, not evidence of calibrated confirmation inference. In the Gaussian seed-dominated fixture, nominal 95% percentile coverage was 213/256 = 83.2% (pointwise Wilson 95% Monte Carlo interval 78.1–87.3%); primary type-I error was 43/256 = 16.8% [12.7, 21.9%]. The declared skewed fixture gave coverage 181/256 = 70.7% [64.9, 75.9%]. S16 improved these particular results, but skewed coverage remained 226/256 = 88.3% [83.8, 91.7%]. No universal sufficient seed count follows.

Endpoint Monte Carlo precision addresses a different source of error. All 16 independent endpoint-rule runs on four prespecified fixed matrices passed the specified four-batch criterion at 2,000–16,000 resamples. This says how accurately those empirical-bootstrap quantiles were computed; it does not establish 95% coverage across new histories/training replicates. Pure-residual controls were conservative, so there is no uniform claim that the method always undercovers.

The outer coverage runs intentionally use fixed B=2,000, the protocol's starting draw total. They estimate the finite-resample percentile procedure at that total, **not the full adaptive endpoint-stopping procedure**. Separate endpoint diagnostics implement the frozen doubling rule. This reconnaissance is not the Task19 acceptance gate: the production implementation and complete adaptive procedure still require their own predeclared independent simulation validation. No coverage acceptance bounds were chosen after observing these results, and no pass claim is made.

## Declared fixtures, estimands, and exact math

One stratum, H=128, S∈{4,8,16}, independent crossed observations:

```text
d[h,s] = μ + a[h] + b[s] + e[h,s]
a[h] ~ Normal(0, σh²), e[h,s] ~ Normal(0, σe²), mutually independent.
Gaussian fixtures: b[s] ~ Normal(0, σs²).
Skewed fixture: b[s] = sqrt(σs²) * (exp(Z[s]) - exp(1/2)) / sqrt(e*(e-1)),
                Z[s] ~ Normal(0,1), so E[b]=0 and Var(b)=σs² exactly.
θhat = mean(d), θ = μ = 0.
V(H,S) = σh²/H + σs²/S + σe²/(H*S).
```

All main fixtures were declared before executing coverage: raw component variances `(σh²,σs²,σe²)` are `gaussian_history=(.90,.05,.05)`, `gaussian_balanced=(.45,.45,.10)`, `gaussian_seed=(.05,.90,.05)`, `gaussian_residual=(.05,.05,.90)`, and `skewed_seed=(.05,.90,.05)` with only the seed distribution skewed as above. Names denote **raw component allocations**, not contributions to V. In particular, “balanced” means raw history/seed variances are equal; their grand-mean contributions differ by H/S. Pure controls `(1,0,0)` and `(0,0,1)` were added based on that algebra before their runs, to separate actual history and residual dominance; they were not selected based on favorable control outcomes. All executed cells are retained.

Histories and paired-seed indices are resampled independently with replacement. If W and U are independent multinomial counts with H and S trials and uniform probabilities, each bootstrap mean is `Wᵀ d U/(H*S)`. This is exactly averaging the resampled Cartesian product, including duplicates. It neither independently resamples cells nor treats queries as independent histories. Quantiles use NumPy `method="linear"` at `.025,.975`. Primary null rejection is `lo>0 or hi<0`.

For fixed observed d, put `m=mean(d)`, `A[h]=rowmean[h]-m`, `B[s]=colmean[s]-m`, and `C[h,s]=d[h,s]-m-A[h]-B[s]`. All corresponding margins of C vanish. Independence of the two multinomial axes gives the **exact conditional bootstrap variance**

```text
Var*(θhat* | d) = mean(A²)/H + mean(B²)/S + mean(C²)/(H*S).
```

Averaging over the declared independent additive population gives

```text
E_d[Var*(θhat* | d)]
 = (1-1/H)*σh²/H + (1-1/S)*σs²/S
   + (3-2/H-2/S+1/(H*S))*σe²/(H*S).
```

For example, `E[mean(A²)] = (1-1/H)*(σh²+σe²/S)`, the column expression is analogous, and `E[mean(C²)] = (1-1/H)*(1-1/S)*σe²`; substituting gives the formula. This requires finite second moments and independence, not Gaussianity. It is a variance deduction, **not a theorem giving percentile-interval coverage**. At H128/S4 the seed term has factor .75, the history term .9921875, and the residual term 2.486328125. Raising H alone cannot remove `σs²/S`. Residual inflation can counteract seed shrinkage in one population and fail in another.

The secondary empirical-null resample is exactly `θhat* - θhat`. Its unadjusted p-value is `(1+sum(abs(null)>=abs(θhat)))/(B+1)`. No simulated multiplicity family or Holm FWER claim is made here. Power uses a **prespecified positive location shift** `δ=2.80*sqrt(V)` with identical centered noise. Translation equivariance lets the null and shifted population share a realization; those null/power event indicators are paired, not independent. This checks the frozen normal-approximation planning target; it does not assume it has exact 80% power in a skewed population. Inflated rejection under a missized test is not a power advantage.

## Executed coverage and variance allocations

Every cell below has 256 independent outer datasets and B=2,000 resamples per dataset. Brackets are pointwise 95% Wilson intervals for outer Bernoulli Monte Carlo error; they are not simultaneous confidence bands and do not account for model misspecification. Primary type-I rate is exactly `1−coverage`, and its Wilson interval is obtained by reversing/complementing coverage's endpoints. Additional event counts and intervals are retained in JSON. Approximate SE near .95 is 1.36 percentage points, and near .80 it is 2.50 points, so a coarse near-.95 cell cannot certify a tight coverage tolerance. Comparisons between different S use independent simulated datasets, not paired Monte Carlo.

| Fixture | S | Grand-mean V shares: history / seed / residual (%) | E[bootstrap V]/true V | Coverage count/n = % [Wilson95] |
|---|---:|---:|---:|---|
"""

for c in cells:
    vh, vs, ve = c["variances"]
    s, v = c["s"], c["true_variance"]
    shares = " / ".join(f"{100*a/v:.2f}" for a in (vh/128, vs/s, ve/(128*s)))
    text += f'| {c["fixture"]} | {s} | {shares} | {c["expected_variance_ratio"]:.4f} | {event(c["coverage"])} |\n'

text += """
Raw `.05/.90/.05` gives 99.78% seed contribution to V at S4; `.45/.45/.10` gives 96.81%; even raw `.05/.05/.90` gives 85.33%. The last case has 12.0% residual contribution at S4, enough to partially offset seed variance shrinkage but not to establish calibration. Pure-history S4/S8/S16 are the same population distribution with independent random draws; apparent nonmonotonic coverage across these coarse cells is not a seed-count effect. All are shown, including the lower pure-history S16 result. No cell is selected as the population for the scientific experiment.

## Secondary type-I sensitivity and shifted rejection rates

All secondary entries below are **unadjusted** empirical-null tests. Power is rejection at the declared δ, not an accepted inferential claim. The skewed seed fixture's near-100% shifted rejection accompanies inflated type-I error and reflects its distribution/shift, not a valid superiority conclusion. JSON also retains the known-variance normal-reference rejection results; those are reference computations, not exact oracle intervals for the skewed fixture.

| Fixture | S | Secondary type-I count/n = % [Wilson95] | Primary shifted rejection count/n = % [Wilson95] |
|---|---:|---|---|
"""
for c in cells:
    text += f'| {c["fixture"]} | {c["s"]} | {event(c["secondary_type_i"])} | {event(c["primary_power"])} |\n'

text += """
## Endpoint Monte Carlo diagnostic

Four fixed matrices were selected by fixture and outer replicate index 0 before the coverage run: raw-history/S4, raw-seed/S4, raw-seed/S16, skewed-seed/S4. Each received four independent endpoint-control repetitions. Each repetition maintains four independent generator streams, initially 500 draws each; extending each stream doubles the total to 4,000, …, 128,000. At each stage the pooled interval uses all draws, the two endpoint SE estimates are the across-batch sample SD (`ddof=1`) divided by 2, and both must be strictly below 1% of pooled width. Exact-zero handling was separately checked by the script's all-zero resampling assertion; these selected matrices were nondegenerate. Failed stages and endpoint estimates are retained in `endpoints.json`.

| Fixture | S | Repeat | Final total draws | Endpoint SE / pooled width (%) lower / upper | Cap failure |
|---|---:|---:|---:|---:|---|
"""
for run in endpoints["runs"]:
    final = run["trail"][-1]
    ratios = " / ".join(f"{100*a:.3f}" for a in final["se_over_width"])
    text += f'| {run["fixture"]} | {run["s"]} | {run["repeat"]} | {final["draws"]} | {ratios} | {run["cap_failure"]} |\n'

text += r"""

No run reached the cap. This small diagnostic does not certify a general initial draw count or cap-failure probability. Four endpoint estimates give a noisy SE estimate; a pass is the specified algorithmic criterion, not an independently proven high-probability error bound. Reusing independent streams within a repetition preserves the declared four batches while appending new draws. Repeating on the same d isolates resampling randomness; it does not add histories/seeds or improve sampling coverage.

## Reproduction and workload

Run from the repository root. These scripts import NumPy and the Python standard library only; they do not import `famjet`, load data/manifests, train a model, or access protected output.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python .superpowers/sdd/2026-10-16-famjet/bootstrap-recon/simulate.py coverage --outer 256 --draws 2000 --max-seconds 120 --output .superpowers/sdd/2026-10-16-famjet/bootstrap-recon/coverage.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python .superpowers/sdd/2026-10-16-famjet/bootstrap-recon/simulate.py coverage --fixture gaussian_pure_history --fixture gaussian_pure_residual --outer 256 --draws 2000 --max-seconds 30 --output .superpowers/sdd/2026-10-16-famjet/bootstrap-recon/controls.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python .superpowers/sdd/2026-10-16-famjet/bootstrap-recon/simulate.py endpoint --max-seconds 30 --output .superpowers/sdd/2026-10-16-famjet/bootstrap-recon/endpoints.json
.venv/bin/python .superpowers/sdd/2026-10-16-famjet/bootstrap-recon/write_report.py
```

Seed root is 2026101619. Each generator uses NumPy `default_rng(SeedSequence([root,*key]))`. Fixture indices are fixed by the source list, including when selecting controls. Dataset key `(10,fixture_index,S,outer_rep)` and bootstrap key `(20,fixture_index,S,outer_rep)` are separate. Endpoint key is `(30,fixture_index,S,repeat,batch)`. Histories are one stratum with uniform weights. Quantile method, chunk size (1,000), RNG calls, and count-matrix implementation are in `simulate.py`; changing chunk size changes RNG order and finite-B draws. Result JSON records every outer observed mean, both endpoints, p-values, conditional variance, simulated bootstrap variance, and rejection indicators. Exact fixtures are reproducible from keys; no scientific raw data are involved.

The script self-checks exact Cartesian/count equivalence, all-zero output, translation equivariance, and the conditional-variance identity against enumeration of all 16 independent H2/S2 resamples. These checks ran before every invocation. This establishes basic simulator consistency, not correctness of any future production implementation. The compute cap is checked between outer replicates/endpoint repetitions, so it can overrun by at most a single bounded unit. Reproduction on slower machines can stop early and record smaller denominators; it does not silently fill a complete result.

"""
total_outer = sum(c["coverage"]["n"] for c in cells)
total_draws = sum(c["coverage"]["n"] * main["draws"] for c in cells)
endpoint_draws = sum(r["trail"][-1]["draws"] for r in endpoints["runs"])
text += (f'Executed environment: Python {main["python"]}, NumPy {main["numpy"]}. '
         f'Executed {len(cells)} cells, {total_outer:,} outer datasets, {total_draws:,} coverage resamples and '
         f'{endpoint_draws:,} endpoint-diagnostic resamples. Recorded wall times: '
         f'{main["elapsed_seconds"]:.2f}s main, {controls["elapsed_seconds"]:.2f}s controls, '
         f'{endpoints["elapsed_seconds"]:.2f}s endpoint diagnostics. No compute cap truncated a run. '
         'One thread was requested through the four environment variables before NumPy import; no parallel jobs were used. '
         'Memory is bounded by 1,000-draw count matrices (the largest history count matrix is about 1 MiB), '
         'small H×S arrays, endpoint vectors, and JSON records; process peak RSS was not measured.\n\n')

text += r"""## Concrete handoff

For **Task19**, retain the frozen method and implement the specified crossed/stratified resampling, centering, +1 empirical-null p-value, Holm, missing-inventory checks, paired axes, four-batch endpoint rule, exact-zero case and cap reporting. Before pilot/freeze, independently test both axis sensitivity and row/seed sampling, and run a predeclared coverage/type-I gate against the **actual production adaptive procedure**. Use known Gaussian/null/effect and declared skewed fixtures across meaningful allocations of grand-mean variance, recording outer Monte Carlo bounds; a B-only endpoint check cannot substitute. Include the finite-cluster and few-seed limitations. This scratch script deliberately does not test the production API, strata, unequal frozen weights, correlated time clusters, missingness/fallback, query aggregation, secondary-family dependence or Holm FWER. The single-stratum case is an admissible special case exposing a seed-axis issue, not evidence that those other pathways work.

For **Task20**, treat H128/S4 as the initial inexpensive nuisance sample. Record raw components **and** their `σh²/H`, `σs²/S`, `σe²/(HS)` contributions. With only four independent Gaussian seed draws, even a direct seed sample variance has three degrees of freedom and coefficient of variation `sqrt(2/3)≈81.6%`; estimated components after separating residuals can be at least as difficult. The Gaussian formula follows from sample-variance variance `2σ⁴/(S−1)` and is a diagnostic, not a proposed replacement estimator. Expand nuisance estimation when unstable and propagate conservative component uncertainty into fixed H/S precision–cost planning. Where seed variation dominates, spending on additional H has little effect. The normal `2.80*sqrt(V)` planning quantity requires the already-required simulation validation; it cannot be assumed to give calibrated skewed small-S inference. No particular S is recommended by this coarse scan.

Select a fixed feasible H/S only from pre-confirmation variance/precision, coverage diagnostics, conservative uncertainty and measured cost/fairness evidence, not observed favorable effect signs, best rejection rates or a convenient distribution. If adequate local coverage, precision or fair baseline acceptance cannot be demonstrated, produce an inconclusive scoped report or make a dated development amendment **before confirmation is opened**. Do not amend silently, proceed with an unsupported positive claim, change the frozen bootstrap solely to improve these synthetic results, or use extra resample draws to imply more independent training replicates. Fresh-history/new-seed replication remains separately required.

## Limits

The coarse cell denominators can expose large failures; they cannot certify a narrow nominal-coverage band, a universal seed minimum, a robust tail model or scientific power. Twenty-one pointwise intervals invite occasional fluctuations; there was no multiple-testing-adjusted search, cell dropping, favorable-distribution selection or exhaustive allocation scan. Variance allocations are diagnostic synthetic populations, not fitted scientific nuisance estimates. The one lognormal seed fixture is explicitly declared and analytically standardized, not a claim about actual effects. No temporal-cluster limit, real-regime weighting, history dependence, heavy-tailed residual process or full secondary Holm family was simulated. No recommendation here overrides the frozen protocol, pre-confirmation gate, or legitimate unblinding requirements.

## Artifact integrity

SHA-256 values below identify the exact source/result bytes used to render this report (report hash is intentionally omitted).

"""
for name in ("simulate.py", "coverage.json", "controls.json", "endpoints.json"):
    text += f'- `{name}`: `{hashlib.sha256((HERE/name).read_bytes()).hexdigest()}`\n'

(HERE / "report.md").write_text(text)
print(f"Wrote {HERE / 'report.md'}; {len(cells)} cells, {total_outer} outer datasets")
