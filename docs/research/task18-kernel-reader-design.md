# Prospective kernel-reconstruction reader diagnostic — 18 October 2026

Status: **design reconnaissance only; no implementation or numerical probe executed or authorized.** The current structured Jet125/Bank122 run must finish and its evidence must be reviewed before deciding whether this diagnostic is useful. Source/package names in the design brief are historical setup identifiers, not a claim to have verified the current operator's HEAD. No source, tests, data, fits, simulations, Git state or active-run artifacts were changed for this report.

Recommendation: retain one later candidate, an explicitly query-conditioned, regularized projection of each window onto the retained kernels under a frozen exponential age prior. It could show that the existing state supports a better task read than the current learned reader achieved. Its failure cannot certify information loss, and even a successful result does not establish convergence, universal recovery, a Jet advantage, or an accepted modern-baseline comparison.

## Authority and evidence used

This report applies the binding [specification](../../../docs/superpowers/specs/2026-10-16-famjet-design.md), especially §§3–6, 8–12; the [Task18 brief](task-18-brief.md), [coverage map](task-18-requirements-coverage.md), [fixed8192 report](../../../docs/research/task18-fixed-basis-learning8192-report.md), [training horizon statistics](../../../docs/research/task18-training-horizon-statistics.json), and [structured allocation amendment](../../../docs/amendments/2026-10-18-structured-fixed-operational-and-learning.md). Formula/access checks used `famjet/memory/jet.py`, `famjet/readers/structured.py`, `famjet/analysis/development.py`, and `famjet/eval/oracle.py`.

The fixed8192 evidence is exploratory and unconverged: best reported raw-reader development losses are approximately .3919 Jet and .3914 Bank; shared buckets on the reused common panel are .1365. Long2048 trend/reset cells dominate errors. These observations motivate a reader diagnostic but do not decide whether optimization, function class, basis or population mismatch is responsible. No outcome from the current structured learning is assumed here. All derivations below are mathematical deductions, not external novelty or literature claims.

## 1. State, target and candidate estimator

Let `x_i=(T-t_i)/t_ref >= 0`, `alpha_j=lambda_j*t_ref`, and let the query-key contraction give event weight `w_i=g_i <p,phi(k_i)> >= 0`. Shared observation masks are included in `w_i`. Define the nonnegative event measure and signed value measures

```
mu = sum_i w_i delta_(x_i),       nu_v = sum_i w_i v_iv delta_(x_i).
```

For the primary one-hot, gate-one, shared-observation arm, these are exactly matching observed-event counts and sums. For general soft keys or nonunit gates they describe weighted/interfering events; the resulting ratio is not automatically the specification's exact-key arithmetic mean. The proposed diagnostic is restricted to the current primary fixed writer.

Index the `m=8` available kernels by `(alpha,q)`:

```
phi_(alpha,q)(x) = (alpha*x)^q exp(-alpha*x),
Jet4: q in {0,1} at each of four rates;
Bank8: q=0 at eight distinct rates.
N_r = integral phi_r dmu,        U_rv = integral phi_r dnu_v.
```

`N` is assembled from the retained normalization columns `z,b`; `U` from the retained numerator columns `u,h`. Use raw contractions, not the smoothed ratios alone. At the query time, these are sufficient inputs for this particular reader. Delay from snapshot time is handled by the existing causal `advance_copy` equations, including the Jet cross-term. A read must not reverse a snapshot or mutate its resume state.

For a half-open dimensionless window `W=[a,b)`, let `f_W(x)=1{a<=x<b}`. Choose a global, history-independent probability density `pi(x)` and coefficients `c(W)` approximating this indicator. Define

```
G_rs = integral phi_r(x) phi_s(x) pi(x) dx,
b_r(W) = integral_W phi_r(x) pi(x) dx,
d_r = sqrt(G_rr),   D=diag(d),   R=D^(-1) G D^(-1),
h(W)=D^(-1)b(W),
theta(W) = (R + rho I)^(-1) h(W),
c(W) = D^(-1) theta(W),                  rho > 0.
```

This minimizes `E_pi[(f_W-c^T phi)^2] + rho ||D c||_2^2`. Regularization is in the explicitly declared canonical scaled-kernel coordinates. No explicit inverse need be formed. One fixed factorization serves all windows for a family/prior/rho.

Apply **the same coefficients** to numerator and normalization:

```
fhat_W(x) = c(W)^T phi(x),
Chat_W = c(W)^T N,              Uhat_Wv = c(W)^T U_:v,
mhat_Wv = Uhat_Wv / (Chat_W + eps)       when numerical guards pass.
```

The proposed first diagnostic retains the current `eps=1e-8` and numerical floor `1e-8`; it does not relabel `Chat` as an observed count. Mean uses `[a,b)`. Contrast uses the difference of the separately normalized estimates for `[a,b)` and `[b,2b-a)`, in that order. A single reconstruction of a signed difference of indicators divided by one count does **not** implement difference of means. Sign may later be derived from numeric contrast as in the specification, but is outside this minimal mean/contrast allocation.

These formulas operate on event measures. The continuous integral defining `G,b` is only an approximation-design measure, not a replacement target or an assertion that events are uniformly spaced. A ZOH signal would instead require time-weighted integrals over held intervals, with different write/input semantics. The present impulse state has not retained those interval contributions; this proposal cannot quietly reinterpret it as a ZOH signal memory.

### Exact integrals, including repeated-pole moments

For nonnegative integer `n`, define

```
I_n(s;l,u) = integral_l^u x^n exp(-s*x) dx,  s>0.
I_0 = [exp(-s*l)-exp(-s*u)]/s,
I_1 = [(s*l+1)exp(-s*l)-(s*u+1)exp(-s*u)]/s^2,
I_2 = [((s*l)^2+2s*l+2)exp(-s*l)
       -((s*u)^2+2s*u+2)exp(-s*u)]/s^3.
```

At `u=infinity`, the upper exponential-polynomial term is zero. More generally, `I_n = n!/s^(n+1) [exp(-sl) sum_(k=0)^n (sl)^k/k! - exp(-su) sum_(k=0)^n (su)^k/k!]`. An empty intersection has integral zero.

Two priors suffice for comparison:

* **Finite uniform domain:** `pi_A=1/A` on `[0,A]`. For `r=(alpha,q)`, `s=(beta,p)`, `G_rs=alpha^q beta^p I_(q+p)(alpha+beta;0,A)/A` and `b_r=alpha^q I_q(alpha;max(0,a),min(A,b))/A`, with empty windows handled explicitly.
* **Exponential tail prior:** `pi_eta(x)=eta exp(-eta x)` on `[0,infinity)`. Here `G_rs=eta alpha^q beta^p (q+p)!/(alpha+beta+eta)^(q+p+1)` and `b_r=eta alpha^q I_q(alpha+eta;max(0,a),b)` for valid nonnegative endpoints.

Thus Jet `G00,G01,G11` use `I0,I1,I2`; repeated rates do not need a distinct-pole limit or division by a rate difference. The q=1 factors are `alpha*x`, not `x`, and must match stored `H` exactly. Bank uses only `I0`. Window endpoints have no effect on the continuous integral when a single endpoint is included or excluded; the exact event oracle nevertheless must enforce half-open membership at atoms.

### Stable evaluation and units

Do not implement the displayed endpoint differences naively for a narrow window. With `Delta=u-l`, use

```
I_n(s;l,u) = exp(-s*l) sum_(r=0)^n binom(n,r) l^(n-r)
                                      Delta^(r+1) F_r(s*Delta),
F_r(z)=integral_0^1 t^r exp(-z*t) dt
     = sum_(k=0)^infinity (-z)^k / [k! (r+k+1)].
```

Use a convergence-controlled small-z series, `F0=-expm1(-z)/z`, and stable positive-z evaluation of `F1,F2` away from cancellation; validate switching rules independently before adoption. At very large products use exponential-polynomial/log-domain limits without `0*infinity`. Complete-decay branches and nonrepresentable results remain explicit. All n here are at most two. No quadrature or history-dependent age grid is necessary in production.

FP64 construction, diagonal scaling, a symmetric eigendecomposition of `R`, and positive ridge give `theta=Q diag(1/(sigma+rho)) Q^T h`. Check symmetry, eigenvalues, factorization/solve residuals and a condition estimate. Material negative eigenvalues indicate a numerical/construction failure; do not silently clamp them to rescue a candidate. A tiny negative attributable to rounding must be covered by a predeclared error policy and independent reference. Ridge candidates which cannot pass original pointwise gates fail; ill conditioning does not authorize looser tolerance. Cholesky solves are an alternative implementation of the same mathematical estimator, not another statistical variant.

The existing statistics report a maximum training age span 5224 over the fixed6144 histories; this is an observed training summary, not a universal bound. Freeze a physical scale `L=5224` in the current time units, then `A=L/t_ref` or `eta=t_ref/L`. `x,alpha,A,eta,a,b,G,b,c` are dimensionless; `N,Chat` have write-mass units and `U,Uhat` have mass-times-value units. Under a time-unit change by factor k, multiply timestamps, endpoints, `t_ref` and `L` by k, and divide physical rates by k. Every dimensionless formula is unchanged. Absolute timestamp shifts must also leave it unchanged. Arithmetic at extreme represented timestamps remains subject to the existing precise difference rules.

## 2. Access limits, failures and checks

**Allowed inputs:** the read-only retained snapshot at its recorded time, public query key/task/endpoints/T, existing validity/status, frozen rates and static training-only constants (prior scale, rho, epsilon, floors, fallback task means, factors). No history length/span, earliest time, event counts, ID-conditioned coefficients, regime label, generator state, per-history age histogram or training-event dictionary enters the reader. Ownership IDs may be checked for schema consistency, never used to retrieve coefficients/history. No raw-data or disk-history handle is available in the clean read worker.

In particular `T-last_time` supplies an allowed delay, but `last_time` alone does not supply the total history span. A global maximum training span cannot be replaced with each history's actual span during inference. Adding a separate earliest-time field and validity byte would cost9 logical bytes per history for an8-byte timestamp (and change the matched9345B allocation); per-key spans cost more. None is proposed. Global training-derived summaries count as static model data, cannot contain reconstructive per-history tables, and must be frozen before development selection. Generator support-based query sampling is already part of the population; it must not expose its rejection counts or factual support to this reader.

**Domain and tail mismatch:** finite uniform projection ignores approximation error beyond A even though old events still contribute to the snapshot. Clipping a query's integral does not remove their state contributions or make the clipped target correct. Any uniform-domain candidate would require an explicit out-of-domain policy for required query endpoints, while undisclosed older-event leakage remains possible even when endpoints lie inside A. The tail prior avoids a hard cutoff, but only downweights old ages; narrow windows, short-history concentration, delayed queries and heavy-gap robustness can still be poorly represented. No per-history adaptation using hidden spans is permitted. For the recommended tail prior, keep the same function for finite public windows and report query-endpoint/prior-scale diagnostics; reject nonrepresentable arithmetic, not difficult examples. The initial probe covers existing primary queries plus deterministic tail/delay cases, not an expanded robustness claim.

**Reconstructed mass is signed and may cancel:** positive `N_r` does not imply `Chat>0`, since `c` may change sign. `Chat` can be negative, tiny, large or apparently positive for an actually empty window. Moment channels alone can vanish for age-zero events. An unbounded ratio may lie outside the observed value range; do not clip it without a separately declared estimator change.

Proposed explicit numerical eligibility is finite inputs/results, nonnegative canonical normalization channels, existing nonquarantined state, `Chat>1e-8`, and `Chat>64*u_fp64*sum_r |c_r|N_r`, where `u_fp64=2^-53`. This last fixed, dimensionless safety factor is a prospective rounding-cancellation guard, not a probability or an error certificate; independent source-state error still matters. It must be frozen and tested under the amendment. Apply both window guards for contrast. Use compensated reductions if required by the original tolerance. Nonfinite state triggers the existing quarantine policy; a failed query/denominator triggers training-only unconditional task-mean fallback, an explicit failure category and the full resulting loss. There is no rescue refit, history inspection or dropped query. Retain counts of negative, near-zero, cancellation and overflow failures separately.

Passing these guards means only that the arithmetic is eligible. It cannot set an output named factual interval support, nor calibrate support confidence. Positive reconstructed mass can result entirely from out-of-window leakage. Record numerical eligibility separately and declare factual support estimation unavailable; any future calibrated abstention would require the distinct development calibration subset and a further protocol specification.

**Bias:** write `Uhat=U+delta_U`, `Chat=C+delta_C`, with true `U=m C`. Then, on an eligible query,

```
mhat-m = (delta_U - m*delta_C - m*eps)/(C+delta_C+eps).
```

Numerator and denominator errors are dependent; a small kernel L2 residual does not bound this ratio when true/reconstructed mass is small. Ridge changes both errors, epsilon shrinks toward zero, and fallback replaces the result by a separate training task mean. Report all effects without interpreting a guard-passing ratio as unbiased. A count correction fitted from labels would be a different reader and is not proposed.

Required algebraic/fixture checks for a later probe:

* Constant vectors: `Uhat=c0*Chat` exactly in real arithmetic; the implemented smoothed result is `c0*Chat/(Chat+eps)`, not c0. A constant contrast may have nonzero epsilon bias if the two masses differ. Verify the stated formula; do not require or claim exact constant recovery.
* Single impulse and boundaries: for mass w at age x, `Chat=w*fhat_W(x)` and `Uhat=w*v*fhat_W(x)`. Check age zero, both boundaries, immediate neighboring represented ages and outside-window leakage. With one impulse outside the window the ratio can still resemble v; this is a direct counterexample to factual support. These are analytic decoder fixtures, not a rerun of the trained tiny sufficient-reader controls.
* Mass rescaling/duplicated observations: multiplying all writes by s>0 multiplies numerator and normalization by s. The unsmoothed eligible ratio would be invariant; the proposed `eps` ratio becomes `Uhat/(Chat+eps/s)`, and the fixed floor can change eligibility. Verify and report that declared noninvariance rather than hiding it. This does not alter primary gate-one targets.
* Time units, global time shifts, delayed copies and query permutations: preserve dimensionless outputs within original applicable tolerances and leave saved snapshot bytes/resumption unchanged. Unit changes must include the prior scale. Delays use the exact moment cross-term.
* Coordinate equivalence: for `y'=A y` representing `L0=Z, L1=Z-2H`, either recover canonical Z,H then apply this reader, or transform coefficients as `c'=A^(-T)c`. Transform the ridge metric with the coordinates as well. Re-normalizing and independently imposing an identity ridge in Laguerre coordinates generally changes the estimator and cannot be called an equivalence test. Apply the cancellation guard in canonical coordinates (or its mathematically transformed equivalent).
* Empty/absent, extremely old/decayed and cancellation cases: no invented support, no overflow rescue using raw events, explicit fallback, original failure-complete scoring. All deterministic cases remain visible even when mathematically unrepresentable or unsupported.

## 3. Why this is a diagnostic, not optimal recovery

The finite uniform prior is simple and gives a direct approximation on a declared training-derived domain, but its unpenalized tail is a substantial concern for a state which still contains older events. The exponential prior is the recommended single prospective variant: its support covers every nonnegative age, its Gram entries have elementary positive formulas, and it adds no history metadata. Its choice of eta is still a modeling assumption. Do not run both as an unbounded prior/domain sweep; reject the idea if the current structured result already makes this additional diagnostic uninformative relative to outstanding required controls.

A finite linear combination of these smooth kernels is continuous and cannot equal a nontrivial hard-window indicator at every age. Uniform continuous L2 error also does not control error against arbitrary atomic event measures: events can concentrate at a boundary or at a point with large error. For bounded values, a pointwise error bound over known event support would bound sum error by total event mass times that bound, but neither that total mass nor the history's support is generally known here. A universal small bound across the jump cannot be inferred from these integrals.

More generally, for sufficiently many fixed event ages the m-by-n kernel matrix has a nontrivial nullspace. Keeping ages and positive normalization weights unchanged while perturbing signed values along a null vector preserves every numerator state and the normalization state. When a window-indicator vector is outside that matrix's row span, such a perturbation changes its exact window sum. This proves that universal exact recovery over unrestricted signed event histories is unavailable; it does not quantify attainable average error on the specified stochastic population, choose Jet over Bank, or explain an observed loss near .39. Existing nullspace/information controls need not be repeated for this report.

Interpret a later result as follows:

* If this same-state legal read substantially lowers the common development loss, including the problematic long trend cells with failures included, then the earlier reader's achieved loss was not forced by information loss alone. It establishes a concrete achievable read from these states. Because the kernel reader introduces query-dependent solves/ratios and a prior, it does **not** isolate SGD optimization from the MLP's finite architecture, conditioning, feature scaling or inductive bias. A strict optimization-only conclusion would require demonstrating adequate representation/fit in the exact MLP class under controlled training.
* If it fails while its numerical checks pass, only this projection/prior/ridge/ratio construction failed. Basis information loss, inadequate linear indicator approximation, poor prior weighting, normalization instability and training-distribution assumptions remain confounded. It gives no lower bound for generic nonlinear readers or the Bayes risk from the state.
* A Jet/Bank difference under this fixed decoder is conditional on each basis and the declared reader/prior/tuning budget. It is neither uniform basis dominance nor a completed equal-tuning-cost comparison. Both have m=8, but coefficients/conditioning can differ substantially.

The proposed access is the same queried-key raw contraction already available to generic contracted readers. Full-state readers can exploit additional cross-key information/statistical correlations; this reconstruction does not settle their adequacy or replace the required full-state development attribution. Rank9 factorization is not proof of unrestricted full-state sufficiency. A gamma/Laguerre state has exactly the same information as Jet; only coordinate/numerical differences can remain under the identical transformed estimator.

Simple bucket results remain the existing practical reference, not a benchmark rerun invitation. Polynomial/log-timescale and modern delta/learned-writer families still require their own task-appropriate tuning, numerical gates, cost accounting and convergence evidence. The exponential positive-mass decoder is not automatically an appropriate matched reader for sign-changing polynomial coefficients or a nonlinear delta state. Its low trainable parameter count cannot be used to declare those families inefficient or defeated. This proposal supplies no missing required control or broad associative-memory/load claim.

## 4. Bounded prospective probe and costs — not executed

After the structured pair finishes, root should first decide whether its results leave a specific reader-conditioning uncertainty worth this cost. If yes, the proposed later scope is **only the exponential prior** with `eta=t_ref/5224`, the existing fixed Jet4/Bank8 states and at most three predetermined ridge values `rho in {1e-10,1e-6,1e-2}`. These values are design choices for a bounded diagnostic, not measured optimal settings. No learned weights, new rate grid, state size, metadata or target normalization are proposed.

1. Validate analytic integrals, factorizations, coefficient/state contractions and the complete prediction/fallback formula against an independently calculated high-precision reference on at most32 base deterministic query/history fixtures. Cover the cases above, including ordinary and long time scales, sharp windows and cancellation. Permit at most four predefined transformed realizations of each fixture: at most128 fixture predictions per family/rho, or768 total. The reference may see fixture histories to calculate state and labels; the production read worker receives only snapshot/query/static inputs. Reconstruction error against the hard-window oracle is a measured modeling error, **not** a reason to fail a correct formula check or widen pointwise numerical tolerances. Preserve original applicable CPU64 pointwise tolerance1e-12 and accepted memory/coordinate tolerances; retain failing candidates without adaptation.
2. Run a tiny native cost profile for the exact candidate implementation before authorizing the panel: at most three warmup blocks and five timed blocks of32 queries per candidate, plus one cold end-to-end32-query pass per candidate. Reuse a predefined fixture schedule and fixed paired family order; no adaptive timing loop. Report setup and per-query p50/p95 plus end-to-end preparation/ingestion/read/output and peak memory. Batched operation-block timing is separate from interactive single-query latency; if these blocks are too short for reliable timing, label that measurement inconclusive rather than expand this allocation. Set an execution cap from the initial measured throughput before panel release; this report supplies no invented laptop speed. New-source cache applicability remains strict: profile/re-encoding costs must be charged, and a required full-source corpus refresh is a separate allocation, not implicit permission to regenerate6144 histories.
3. At most one common exposed96-history, eight-query development pass for each of the six candidates: at most4608 scored predictions, with the existing task/length/regime/history weights, training-only task scales and fallbacks. No fresh pilot/protected/replication histories and no repeated TRAIN6144 fit/risk pass are needed for this narrow diagnostic. Reuse exact compatible snapshots if the current provenance rules permit; otherwise explicitly budget source-bound re-encoding of this small panel. Neither reading cached raw events inside inference nor silently re-signing old manifests is allowed.
4. Select rho per family by the original failure-complete development objective among numerically passing candidates, with deterministic ties choosing lower measured total cost then canonical config hash under the existing declared tie policy. Publish all six outcomes, all slice errors/fallbacks, reconstruction residuals, coefficient norms/conditioning and all preparation/failed expenditure. This is development selection with no fresh generalization estimate, and does not enter the accepted learned-baseline inventory by bypassing its convergence/acceptance schema. No adaptive extra rho, domain, learned count correction or continuation follows automatically.

Existing tiny sufficient-reader controls, full simple-headroom suite and bootstrap/variance reconnaissance are not repeated. The deterministic cases above validate this new formula and access path only. Broader tail/delay distribution performance is out of scope until separately declared.

### Analytic resource ledger

For both candidates `m=8,K=16,V=8`. Retain exactly the current9345B per-history snapshot. Its numerical kernel payload is `8*m*K*(V+1)=9216B`; the existing129B metadata account for the remainder. Additional persistent history state is zero if coefficients, contractions and advanced copies are discarded after each read. Any retained query cache would change that statement and must be counted. No trainable parameters or optimizer state are allocated; static fitted statistics and factors still count.

* Setup: at most m(m+1)/2 Gram evaluations; O(m^3) eigendecomposition/factorization for each candidate, separately charged. Rates, prior, numerical policy and any training-statistics preparation are not free.
* Per query window: O(m) elementary integral evaluations, O(m^2) factor solve or two spectral matrix-vector products, then `m*(V+1)` multiply-accumulate contractions. An explicit spectral implementation has `2m^2 + m(V+1)=200` MACs/window before scaling, guard reductions, divisions and special functions. Contrast has two windows, so400 such MACs plus the two divisions per output and subtraction. This is an algebraic count, not an end-to-end FLOP or latency match to the MLP's reported MACs.
* One-hot key gathering reads `m*(V+1)=72` scalars without a dense key contraction. A common dense nonnegative query implementation instead charges `K*m*(V+1)=1152` MACs once per query. Public delay advancement adds the actual exponential/Jet-cross-term work; if it advances the full snapshot, its state-sized work and temporary must be charged. Commuting key contraction with linear advancement is valid only if deliberately implemented and verified; no such optimization is assumed in this report's runtime forecast.
* A compact spectral core per retained candidate can hold `Q` (64 FP64), inverse shifted eigenvalues (8) and `d` (8):640B. An explicit audit-friendly inference export may additionally retain full G (512B) and unshifted eigenvalues (64B), making1216B for those arrays. Existing rates are already static model data; additional copies count if made. Prior scale/rho/eps/floor/cancellation constant, task fallback vectors, reference time, schema/config/hash/Python ownership and serialized overhead are additional and must be enumerated from the actual export. There is no claim that1216B is the total module size. Keeping all six candidates multiplies their owned static allocation; final inference needs only its selected candidate.
* A straightforward one-window streaming workspace can use `m*(V+1)` contracted state, five m-vectors (`b,h`, spectral product/solution, c), and two `(V+1)` result/accumulator vectors:130 FP64 scalars,1040B, excluding library workspace and scalar temporaries. If the wrapper creates a full advanced numerical snapshot, add9216B plus copied metadata. Two simultaneous windows or batched queries increase workspace; serial window evaluation avoids a query-growing history cache. A dense solve library, serialization, tensor/Python objects and OS resident memory require actual measurement, not these logical lower-level formulas.

State-update/ingestion costs are unchanged mathematically but remain part of the full cost boundary. Static factor preparation, source-bound preprocessing, numerical reference work, all candidate queries and failed work belong in the family ledger. No break-even or speed/accuracy number is asserted before measurement, and no dummy weights are added to match MLP parameter counts.

## 5. Required methodological amendment and decision boundary

The broad Task18 brief permits investigation of reader adequacy, but the current explicit amendments authorize a particular structured-reader program. `fixed_basis_cpu64` currently recognizes specified MLP reader shapes; this proposed estimator is not silently admitted by that predicate. This ignored report is neither an amendment nor an allocation, and must not modify the frozen package or interrupt the current structured run.

Before implementation, require a separately reviewed dated amendment, proposed location **`docs/amendments/2026-10-18-kernel-reconstruction-diagnostic.md`** if adopted on this date (use the actual later adoption date otherwise). It must cite the completed structured evidence and state the exact prospective question; authorize the new deterministic reader architecture; freeze its allowed inputs, exponential prior/scale provenance, ridge grid, canonical regularization metric, eps/floor/cancellation and fallback semantics, truthful support status, original numerical tolerances, fixture/panel bounds, source/cache applicability, resource cap/timing boundary, selection/ties, accounting and limited interpretation. It must preserve all preceding negative/failed results and the required generic/full-state/gamma/modern/control obligations. Only then may root release an exact implementation and bounded operational/scientific allocation.

No hypotheses, primary population, metrics or protected outcomes are changed by writing this proposal. This development-only probe needs no opening of protected data. Any eventual use in a selected confirmatory pair requires its own accepted status, complete frozen manifest and appropriate protected-data treatment; changed interpretation or compromised independence can require fresh protected data under §12. A successful diagnostic would justify further reader work, not complete Task18 or authorize the next arm automatically.
