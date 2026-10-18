# Crossed-bootstrap reconnaissance for Tasks 19/20

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
| gaussian_history | 4 | 35.82 / 63.68 / 0.50 | 0.8454 | 234/256 = 91.4% [87.3, 94.3] |
| gaussian_history | 8 | 52.75 / 46.89 / 0.37 | 0.9436 | 249/256 = 97.3% [94.5, 98.7] |
| gaussian_history | 16 | 69.06 / 30.70 / 0.24 | 0.9799 | 244/256 = 95.3% [92.0, 97.3] |
| gaussian_balanced | 4 | 3.03 / 96.81 / 0.17 | 0.7602 | 204/256 = 79.7% [74.3, 84.2] |
| gaussian_balanced | 8 | 5.87 / 93.96 / 0.16 | 0.8849 | 233/256 = 91.0% [86.9, 93.9] |
| gaussian_balanced | 16 | 11.09 / 88.75 / 0.15 | 0.9465 | 236/256 = 92.2% [88.2, 94.9] |
| gaussian_seed | 4 | 0.17 / 99.78 / 0.04 | 0.7512 | 213/256 = 83.2% [78.1, 87.3] |
| gaussian_seed | 8 | 0.35 / 99.61 / 0.04 | 0.8762 | 232/256 = 90.6% [86.4, 93.6] |
| gaussian_seed | 16 | 0.69 / 99.27 / 0.04 | 0.9387 | 242/256 = 94.5% [91.0, 96.7] |
| gaussian_residual | 4 | 2.67 / 85.33 / 12.00 | 0.9648 | 233/256 = 91.0% [86.9, 93.9] |
| gaussian_residual | 8 | 5.19 / 83.12 / 11.69 | 1.0985 | 247/256 = 96.5% [93.5, 98.1] |
| gaussian_residual | 16 | 9.88 / 79.01 / 11.11 | 1.1565 | 249/256 = 97.3% [94.5, 98.7] |
| skewed_seed | 4 | 0.17 / 99.78 / 0.04 | 0.7512 | 181/256 = 70.7% [64.9, 75.9] |
| skewed_seed | 8 | 0.35 / 99.61 / 0.04 | 0.8762 | 199/256 = 77.7% [72.2, 82.4] |
| skewed_seed | 16 | 0.69 / 99.27 / 0.04 | 0.9387 | 226/256 = 88.3% [83.8, 91.7] |
| gaussian_pure_history | 4 | 100.00 / 0.00 / 0.00 | 0.9922 | 244/256 = 95.3% [92.0, 97.3] |
| gaussian_pure_history | 8 | 100.00 / 0.00 / 0.00 | 0.9922 | 243/256 = 94.9% [91.5, 97.0] |
| gaussian_pure_history | 16 | 100.00 / 0.00 / 0.00 | 0.9922 | 235/256 = 91.8% [87.8, 94.6] |
| gaussian_pure_residual | 4 | 0.00 / 0.00 / 100.00 | 2.4863 | 255/256 = 99.6% [97.8, 99.9] |
| gaussian_pure_residual | 8 | 0.00 / 0.00 / 100.00 | 2.7354 | 256/256 = 100.0% [98.5, 100.0] |
| gaussian_pure_residual | 16 | 0.00 / 0.00 / 100.00 | 2.8599 | 256/256 = 100.0% [98.5, 100.0] |

Raw `.05/.90/.05` gives 99.78% seed contribution to V at S4; `.45/.45/.10` gives 96.81%; even raw `.05/.05/.90` gives 85.33%. The last case has 12.0% residual contribution at S4, enough to partially offset seed variance shrinkage but not to establish calibration. Pure-history S4/S8/S16 are the same population distribution with independent random draws; apparent nonmonotonic coverage across these coarse cells is not a seed-count effect. All are shown, including the lower pure-history S16 result. No cell is selected as the population for the scientific experiment.

## Secondary type-I sensitivity and shifted rejection rates

All secondary entries below are **unadjusted** empirical-null tests. Power is rejection at the declared δ, not an accepted inferential claim. The skewed seed fixture's near-100% shifted rejection accompanies inflated type-I error and reflects its distribution/shift, not a valid superiority conclusion. JSON also retains the known-variance normal-reference rejection results; those are reference computations, not exact oracle intervals for the skewed fixture.

| Fixture | S | Secondary type-I count/n = % [Wilson95] | Primary shifted rejection count/n = % [Wilson95] |
|---|---:|---|---|
| gaussian_history | 4 | 24/256 = 9.4% [6.4, 13.6] | 207/256 = 80.9% [75.6, 85.2] |
| gaussian_history | 8 | 8/256 = 3.1% [1.6, 6.0] | 211/256 = 82.4% [77.3, 86.6] |
| gaussian_history | 16 | 12/256 = 4.7% [2.7, 8.0] | 204/256 = 79.7% [74.3, 84.2] |
| gaussian_balanced | 4 | 49/256 = 19.1% [14.8, 24.4] | 225/256 = 87.9% [83.3, 91.3] |
| gaussian_balanced | 8 | 22/256 = 8.6% [5.7, 12.7] | 203/256 = 79.3% [73.9, 83.8] |
| gaussian_balanced | 16 | 20/256 = 7.8% [5.1, 11.8] | 203/256 = 79.3% [73.9, 83.8] |
| gaussian_seed | 4 | 42/256 = 16.4% [12.4, 21.4] | 227/256 = 88.7% [84.2, 92.0] |
| gaussian_seed | 8 | 24/256 = 9.4% [6.4, 13.6] | 216/256 = 84.4% [79.4, 88.3] |
| gaussian_seed | 16 | 15/256 = 5.9% [3.6, 9.4] | 209/256 = 81.6% [76.4, 85.9] |
| gaussian_residual | 4 | 22/256 = 8.6% [5.7, 12.7] | 207/256 = 80.9% [75.6, 85.2] |
| gaussian_residual | 8 | 8/256 = 3.1% [1.6, 6.0] | 200/256 = 78.1% [72.7, 82.8] |
| gaussian_residual | 16 | 6/256 = 2.3% [1.1, 5.0] | 194/256 = 75.8% [70.2, 80.6] |
| skewed_seed | 4 | 76/256 = 29.7% [24.4, 35.6] | 256/256 = 100.0% [98.5, 100.0] |
| skewed_seed | 8 | 61/256 = 23.8% [19.0, 29.4] | 256/256 = 100.0% [98.5, 100.0] |
| skewed_seed | 16 | 33/256 = 12.9% [9.3, 17.6] | 256/256 = 100.0% [98.5, 100.0] |
| gaussian_pure_history | 4 | 11/256 = 4.3% [2.4, 7.5] | 196/256 = 76.6% [71.0, 81.3] |
| gaussian_pure_history | 8 | 12/256 = 4.7% [2.7, 8.0] | 198/256 = 77.3% [71.8, 82.0] |
| gaussian_pure_history | 16 | 20/256 = 7.8% [5.1, 11.8] | 197/256 = 77.0% [71.4, 81.7] |
| gaussian_pure_residual | 4 | 1/256 = 0.4% [0.1, 2.2] | 104/256 = 40.6% [34.8, 46.7] |
| gaussian_pure_residual | 8 | 0/256 = 0.0% [0.0, 1.5] | 90/256 = 35.2% [29.6, 41.2] |
| gaussian_pure_residual | 16 | 0/256 = 0.0% [0.0, 1.5] | 91/256 = 35.5% [29.9, 41.6] |

## Endpoint Monte Carlo diagnostic

Four fixed matrices were selected by fixture and outer replicate index 0 before the coverage run: raw-history/S4, raw-seed/S4, raw-seed/S16, skewed-seed/S4. Each received four independent endpoint-control repetitions. Each repetition maintains four independent generator streams, initially 500 draws each; extending each stream doubles the total to 4,000, …, 128,000. At each stage the pooled interval uses all draws, the two endpoint SE estimates are the across-batch sample SD (`ddof=1`) divided by 2, and both must be strictly below 1% of pooled width. Exact-zero handling was separately checked by the script's all-zero resampling assertion; these selected matrices were nondegenerate. Failed stages and endpoint estimates are retained in `endpoints.json`.

| Fixture | S | Repeat | Final total draws | Endpoint SE / pooled width (%) lower / upper | Cap failure |
|---|---:|---:|---:|---:|---|
| gaussian_history | 4 | 0 | 4000 | 0.612 / 0.600 | False |
| gaussian_history | 4 | 1 | 8000 | 0.984 / 0.389 | False |
| gaussian_history | 4 | 2 | 16000 | 0.332 / 0.381 | False |
| gaussian_history | 4 | 3 | 8000 | 0.234 / 0.912 | False |
| gaussian_seed | 4 | 0 | 8000 | 0.639 / 0.878 | False |
| gaussian_seed | 4 | 1 | 2000 | 0.610 / 0.919 | False |
| gaussian_seed | 4 | 2 | 8000 | 0.231 / 0.241 | False |
| gaussian_seed | 4 | 3 | 8000 | 0.796 / 0.439 | False |
| gaussian_seed | 16 | 0 | 4000 | 0.921 / 0.857 | False |
| gaussian_seed | 16 | 1 | 4000 | 0.236 / 0.688 | False |
| gaussian_seed | 16 | 2 | 4000 | 0.479 / 0.663 | False |
| gaussian_seed | 16 | 3 | 8000 | 0.469 / 0.455 | False |
| skewed_seed | 4 | 0 | 2000 | 0.288 / 0.847 | False |
| skewed_seed | 4 | 1 | 8000 | 0.155 / 0.698 | False |
| skewed_seed | 4 | 2 | 8000 | 0.249 / 0.752 | False |
| skewed_seed | 4 | 3 | 4000 | 0.371 / 0.915 | False |


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

Executed environment: Python 3.13.5, NumPy 2.5.4. Executed 21 cells, 5,376 outer datasets, 10,752,000 coverage resamples and 104,000 endpoint-diagnostic resamples. Recorded wall times: 39.13s main, 15.66s controls, 0.53s endpoint diagnostics. No compute cap truncated a run. One thread was requested through the four environment variables before NumPy import; no parallel jobs were used. Memory is bounded by 1,000-draw count matrices (the largest history count matrix is about 1 MiB), small H×S arrays, endpoint vectors, and JSON records; process peak RSS was not measured.

## Concrete handoff

For **Task19**, retain the frozen method and implement the specified crossed/stratified resampling, centering, +1 empirical-null p-value, Holm, missing-inventory checks, paired axes, four-batch endpoint rule, exact-zero case and cap reporting. Before pilot/freeze, independently test both axis sensitivity and row/seed sampling, and run a predeclared coverage/type-I gate against the **actual production adaptive procedure**. Use known Gaussian/null/effect and declared skewed fixtures across meaningful allocations of grand-mean variance, recording outer Monte Carlo bounds; a B-only endpoint check cannot substitute. Include the finite-cluster and few-seed limitations. This scratch script deliberately does not test the production API, strata, unequal frozen weights, correlated time clusters, missingness/fallback, query aggregation, secondary-family dependence or Holm FWER. The single-stratum case is an admissible special case exposing a seed-axis issue, not evidence that those other pathways work.

For **Task20**, treat H128/S4 as the initial inexpensive nuisance sample. Record raw components **and** their `σh²/H`, `σs²/S`, `σe²/(HS)` contributions. With only four independent Gaussian seed draws, even a direct seed sample variance has three degrees of freedom and coefficient of variation `sqrt(2/3)≈81.6%`; estimated components after separating residuals can be at least as difficult. The Gaussian formula follows from sample-variance variance `2σ⁴/(S−1)` and is a diagnostic, not a proposed replacement estimator. Expand nuisance estimation when unstable and propagate conservative component uncertainty into fixed H/S precision–cost planning. Where seed variation dominates, spending on additional H has little effect. The normal `2.80*sqrt(V)` planning quantity requires the already-required simulation validation; it cannot be assumed to give calibrated skewed small-S inference. No particular S is recommended by this coarse scan.

Select a fixed feasible H/S only from pre-confirmation variance/precision, coverage diagnostics, conservative uncertainty and measured cost/fairness evidence, not observed favorable effect signs, best rejection rates or a convenient distribution. If adequate local coverage, precision or fair baseline acceptance cannot be demonstrated, produce an inconclusive scoped report or make a dated development amendment **before confirmation is opened**. Do not amend silently, proceed with an unsupported positive claim, change the frozen bootstrap solely to improve these synthetic results, or use extra resample draws to imply more independent training replicates. Fresh-history/new-seed replication remains separately required.

## Limits

The coarse cell denominators can expose large failures; they cannot certify a narrow nominal-coverage band, a universal seed minimum, a robust tail model or scientific power. Twenty-one pointwise intervals invite occasional fluctuations; there was no multiple-testing-adjusted search, cell dropping, favorable-distribution selection or exhaustive allocation scan. Variance allocations are diagnostic synthetic populations, not fitted scientific nuisance estimates. The one lognormal seed fixture is explicitly declared and analytically standardized, not a claim about actual effects. No temporal-cluster limit, real-regime weighting, history dependence, heavy-tailed residual process or full secondary Holm family was simulated. No recommendation here overrides the frozen protocol, pre-confirmation gate, or legitimate unblinding requirements.

## Artifact integrity

SHA-256 values below identify the exact source/result bytes used to render this report (report hash is intentionally omitted).

- `simulate.py`: `337309c91e49be426ac4cc6dc135a40e44e566efe3592a9fa7313dacf938fa81`
- `coverage.json`: `520ea1dd3672d333861f900cc8a2e90c365113f6483a9c22f9c04ebf1f8bc571`
- `controls.json`: `01ddac62de7f610479824341a7af800d95bee1a6c38cb9207b94ad03bf12d692`
- `endpoints.json`: `560577a2a101c32c77b46193d9724ef1f0cf5d11bd9ed16a5ff165df23ff197d`
