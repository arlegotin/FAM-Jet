# FAM-Jet technical specification

**Status:** implementation specification; no trained-model findings. **Prepared:** 16 October 2026. **Research cutoff:** 13 October 2026. **Authority:** user-supplied PoC, summarized with source IDs in the [evidence record](../../research/2026-10-13-source-record.md). Local observations are in the [environment snapshot](../../research/2026-10-16-local-environment.md). The user authorized specifications, planning, and commits on the current branch; implementation and experimental execution are a later activity.

## 1. Decision, scope, and success

Determine whether exact dimensionless first temporal moments improve deferred temporal retrieval relative to strong, equally informed alternatives under fully counted persistent state and measured system costs. The workflow is `observe → compress once → answer multiple later queries`. Historical writes never see eventual queries. H1 (basis utility) and H4 (cost) are primary; H5 is necessary for a real-stream utility claim.

The recurrence is a repeated-pole/gamma system. Function-of-rate representations, temporal differentiation, and continuum-queryable memories have prior art (R01–R07). Candidate contributions are empirical allocation, inductive bias, numerical conditioning, or systems implementation. Do not claim greater information capacity than arbitrary vectors, arbitrary exact recall, first invention, or state of the art from this PoC.

The minimum complete core includes a writer, fixed state, post-encoding reader, exact event targets, equal-byte exponential and equivalent-coordinate controls, generic readers, simple bounded storage, full-history arithmetic, training/evaluation, byte accounting, actual stream timing, and a protected decision. A broad competitiveness claim additionally requires accepted multiscale/polynomial HiPPO and a modern delta family. Real transfer is required for real-stream claims. Optional probing, interpolation, routed memories, and language are gated extensions; their omission does not invalidate an informative core negative result.

No remote GPU, paid model API, additional machine, custom GPU kernel, vector database, numerical ODE solver, or pretrained language model is required by the core. Do not install, download, scaffold executable packages, train, or benchmark as part of this documentation task.

Valid outcomes include positive, null, negative, narrow, and inconclusive findings. Broken invariants mean no scientific result yet. A simple cheaper winner must be reported. A low-sensitivity proxy or unresolved optimization is not evidence against an unexpressed mechanism.

## 2. Hypotheses and acceptance boundaries

| ID | Test | Required control / interpretation |
|---|---|---|
| H0-correct | Streaming moments, normalized derivative, and gradients agree with direct sums. | Ordinary finite-range failures block dependent experiments. |
| H1-basis | Jets reduce held-out hard-window/contrast loss versus strongest development-selected equal-byte distinct-pole bank. | Fixed writer, same public input, tuned anchors/readers; one-hot results are temporal-basis claims. |
| H2-reader | Structured derivative/age features improve learning or generalization. | Same-state generic contracted/full-state readers; parameter and compute frontiers. |
| H3-load | H1 persists across key interference/history stress. | Independently vary elapsed time, write count, and key load. |
| H4-cost | An advantage survives preprocessing, ingestion, repeated reads, and reader costs locally. | Actual CPU/MPS timing and full memory ledgers; no promised speed. |
| H5-transfer | Benefit persists on protected real sensor histories. | Shape-matched frozen transfer and equal task-adapted tuning; chronological clusters. |
| H6-probe | Two/three probes help at matched reader computation. | Same full retained information; no new-information claim. |
| H7-language | Memory benefit survives a common frozen decoder bridge. | Oracle bridge, query-only and exact/retrieval evidence controls; conditional extension. |

## 3. Event, time, and query contract

Events carry `(history_id, event_id, timestamp, key_id, key_features, value, observed_mask, auxiliary)`. Queries carry `(history_id, query_id, T, key_id, task, temporal_arguments)`. Tensor batches use explicit padding masks and lengths. Values and timestamps must be finite, gates/key features nonnegative, rates positive, and history timestamps monotone nondecreasing. Reject out-of-order live events. Offline stable sorting by `(timestamp,event_id)` is allowed only as a recorded preparation step.

All methods receive identical raw events, public time, and query fields; independently tuned causal writers are a separate comparison arm. The fixed writer uses raw numeric values and no trainable projection. Queries are generated after the entire history. No future query, label, oracle evidence, or benchmark rationale may influence encoding.

**Builder decision — snapshot time:** `encode` returns a snapshot at its last processed stream time. The public query wrapper rejects `T < snapshot.last_time`; it cannot answer by reversing a state containing later events. Earlier-query evaluation must first create a causal prefix snapshot containing only events at/before T. `advance_copy` permits `T >= last_time`, decays a temporary copy, and leaves the saved snapshot unchanged. A later query must not affect subsequent stream resumption. Empty snapshots have no last event time and remain unsupported at any finite T. No-write gaps advance stream time; masked padding has zero gap and no write. Simultaneous additive writes commute; overwrite methods use recorded stable order.

Timestamp differences are calculated as CPU float64 or checked integer ticks before FP32 conversion. Record dataset time units. Fit `t_ref` as the median positive training gap; a dataset with no positive gap requires an explicit positive configured reference duration, recorded as such. Rescale timestamps and `t_ref` by c and rates by 1/c; the complete predictor's dimensionless features and answers must agree within declared tolerance. Global timestamp shifts also preserve results.

## 4. Exact memory and reads

At anchor rate `lambda_j > 0`, for age `a_i=T-t_i` and rate-independent write `X_i=g_i phi(k_i)[v_i;1]^T`:

```text
Z_j = sum_i exp(-lambda_j*a_i) X_i
H_j = sum_i (lambda_j*a_i) exp(-lambda_j*a_i) X_i
H_j = -partial_log(lambda_j) Z_j
```

Shapes are `[B, heads, J, key_dim, value_dim+1]`. The last column independently carries normalization. For gap Delta, `d=lambda*Delta`, `a=exp(-d)`:

```text
old_z = Z
H_new = a*H + (a*d)*old_z
Z_new = a*old_z + X_new
```

This is the exact impulse update, including nonuniform gaps. Age-zero writes do not enter `H_new`. A real gap has no write; padded entries do neither. If a nonnegative product d overflows, use the complete-decay limits `a=0, a*d=0`, avoiding `inf*0`. Reject NaN/nonfinite input values, negative gaps and invalid rates before this core. Validate gradients away from overflow branches. Zero gaps are exact additions. A gate/key/value that depends on the probed rate needs product-rule terms and is outside the initial derivative contract.

For nonnegative query features p, define contractions `u=p^T Z_values`, `z=p^T Z_norm`, `h=p^T H_values`, `b=p^T H_norm`. With rate-independent epsilon:

```text
r = u/(z+eps)
dlog_rate_r = -h/(z+eps) + r*b/(z+eps)
```

Exact dimensionless mean age is `b/z`, physical mean age `b/(lambda*z)` only above a configured numerical support floor. Unsupported derived age features are zero-filled with an explicit support flag. `b/(z+eps)` is a smoothed feature, not an exact mean age. Derivatives measure temporal sensitivity; they are not uncertainty estimates. Signed values are allowed.

Structured per-anchor input: `[r, dlog_rate_r, log1p(z), b/(z+eps), log(lambda*t_ref), support]` plus query key/task and dimensionless endpoints. Generic contracted input is `[u,h,z,b]` plus query; generic full-state input is flattened state plus query, with a factorized first layer if needed. Preserve amplitude information in generic controls. Standardization uses training only. Initial FP32 epsilon is 1e-8 for order-one writes; development candidates are 1e-6, 1e-8, 1e-10. The numerical support floor and separate learned abstention threshold are explicit configuration fields. Calibrate the latter on a distinct development calibration subset.

The default numeric reader has two hidden SiLU layers and numeric output plus a separate support logit when needed; width 128 is a smoke starting point. Tune widths 64, 128, 256 and factorization under actual parameter/compute envelopes. Equal width is not equal parameter count. A fixed-scale read is only a diagnostic. Do not pad models with unused trainable parameters.

## 5. Equivalent states, training, and interfaces

Between writes, `dot Z=-lambda Z`, `dot H=-lambda H+lambda Z`. The invertible control `L0=Z`, `L1=Z-2H` has updates `L0'=a L0+X`, `L1'=a L1-2ad L0+X`. Recover `H=(L0-L1)/2` before the same reader; predictions must agree to coordinate-error tolerances. This gamma/Laguerre span has exactly the same information. Any difference is numerical/optimization behavior.

For state-independent writers and terminal queries, compute exact chunked contractions of `exp(-lambda*age)*key` and its dimensionless moment against augmented values. The largest temporary has shape `[B,J,chunk,K]`, not `[B,T,J,K,V+1]`. Both candidate and eligible linear baselines receive this optimization and full gradients. Recompute states after every writer/rate parameter update. Nonlinear recurrent/overwrite baselines need full backpropagation with verified checkpoint/recompute or a verified scan; silently truncated gradients are forbidden. Online timing always uses actual incremental ingestion.

**Builder decision — package location:** use `famjet/` and `tests/` directly in this repository, with `pyproject.toml` at the root, rather than a redundant nested `famjet-poc/` directory.

The common protocol is:

```python
class MemoryMethod:
    def init_state(self, batch_size: int, *, device: str, dtype: str) -> Snapshot: ...
    def encode(self, events: EventBatch, state: Snapshot | None = None,
               *, mode: str = "stream") -> Snapshot: ...
    def advance_copy(self, state: Snapshot, query_time: float) -> Snapshot: ...
    def read(self, state: Snapshot, queries: QueryBatch) -> ReadResult: ...
    def persistent_nbytes(self, state: Snapshot) -> int: ...
    def parameter_nbytes(self) -> int: ...
```

`Snapshot` owns method-specific state, per-history CPU float64/tick last time, validity, schema version, and writer/rate parameter hash. Logical bytes include these fields. `ReadResult` contains numeric prediction or categorical logits, support output, failure flags and diagnostics. A read wrapper passes only a snapshot, public static model parameters/schema, and queries to the reader; disk/raw-history access and hidden per-history encoder caches are forbidden. Run bounded-state reads in a clean evaluation worker with no raw-data handles and a read-only input snapshot. Serialization uses `save_state(path, snapshot)` and `load_state(path, expected_parameter_hash)` with checksums and schema validation. Exact-history methods are explicitly marked unbounded references.

## 6. Synthetic population and exact targets

The generator is pure: `(generator_version, split_seed, episode_id, config) -> Episode(events,queries,labels)`. Distinct namespaces cover training, development fit, development calibration, pilot, confirmation, and replication. Use explicit named seed derivation rather than Python's process-randomized hash. All methods share event/query manifests. Generate histories before queries, and oracle labels from raw events.

Primary fixed-writer population: 16 public one-hot keys, eight signed independent value coordinates, gate 1, uniform key frequency. Each history selects one of four regimes with equal population weight; per-key/coordinate initial levels are Normal(0,1).

| Regime | Initial generator definition |
|---|---|
| Piecewise stationary | Fresh Normal(0,1) level with probability 1/32 at each key observation; noise sd 0.1. |
| Trend/reset | Per-key slope Normal(0,0.01) per reference time; reset level/slope with probability 1/128 per observation; noise sd 0.1. |
| Periodic/impulses | Random phase, amplitude Uniform[0.5,1.5], period log-uniform[16,256], impulses probability 1/64 with Normal(0,2) amplitude; noise sd 0.1. |
| Irregular revisions | Piecewise levels plus excursions and reversals separated by 1–16 observations of that key; no future-reversal input flag. |

Builder decisions for unspecified distribution details: phase Uniform[0,2pi); excursion start probability 1/64 per key observation, excursion amplitude Normal(0,2), reversal delay discrete Uniform{1,...,16}; allow at most one outstanding excursion per key/coordinate and record its private generator schedule, never as an input feature. Time is measured relative to fixed generator reference duration 1 before fitting reader `t_ref`. Independent coordinate noise/regime processes preserve the brief's independence requirement. These choices are generator-versioned and frozen before confirmation.

Gaps `{0,1,2,4,16}` have probabilities `{0.05,0.55,0.25,0.10,0.05}`. Start pilot lengths at 128, 512, 2048. Select at least two confirmatory lengths from development headroom, including a materially longer challenge; 4096 is a candidate, not a guarantee. Keep methods' length distributions equal. **Builder decision — query time:** primary synthetic queries all use `T=t_last`. Delayed-read robustness reuses the same encoded history with no-write delays in `{0,A0/8,A0,10*A0}`, where `A0=t_last-t_first`; its windows are sampled from the resulting age span and support rules remain unchanged. Delay never affects the historical writer. Robustness also includes Zipf frequencies, continuous lognormal/heavy gaps, heavy-tailed noise, faster resets, broader periods and unseen reversal delays; freeze explicit configurations before evaluating them.

Dense-key arm: public uint64 IDs, disjoint train/test identities, stateless normalized squared Gaussian features, initial `Kdim=16`, loads 8/16/64. Builder decision: derive per-ID feature RNG from SHA-256 of a versioned seed and little-endian uint64 ID, use a recorded PCG64/Box–Muller float64 transform, square and L1-normalize, then cast FP32; save golden vectors and transform/version. No off-budget per-history dictionary. Learned key/query maps on raw features form a separate learned-writer arm, not reinterpretation of fixed-feature failures.

For history age span A, sample mean widths log-uniformly from `[max(1,A/128), A/2]`, then lower age endpoint uniformly over valid placement. Contrast uses adjacent windows `[a,a+w)` and `[a+w,a+2w)`, with w drawn over the same feasible width range and a in `[0,A-2w]`. Intervals are half-open age intervals; `[0,b)` includes current-time observations, and an event exactly at age b is excluded. Latest ties use `(timestamp,event_id)` order.

Builder decision for degenerate sampling: if A<2, do not create a primary numeric episode; emit an explicit `insufficient_span` status in generation diagnostics. Empty/same-time histories still appear in semantic/support fixtures. For primary labels, rejection-sample key/window pairs independently of values until every required window has at least one observation, with a configured finite maximum attempt count; exhaustion emits a recorded generation failure, never fabricated labels or silent exclusion during scoring. Absent/empty cases are a separately generated abstention suite. Eight initial queries/history balance mean and contrast; query count does not increase independent history count.

Means average matching observed events, not time-integrated signals. Contrast is recent-window mean minus the adjacent older-window mean. Equal weight goes to tasks and histories; regime weights are fixed. Exponential-weighted tasks are diagnostic only. Include hand-calculated boundaries, constant/all-equal signals, impulses, random values, adversarial sharp windows, and the full-history oracle.

The following secondary suites are required artifacts of the complete PoC, with their own frozen configurations and metrics; none changes the primary H1 population or counts as an extra primary test. Their absence must be an explicit incomplete scope, and no sparse/correction claim is allowed without the relevant suite. Builder decisions for previously unspecified labels are:

| Suite | Inputs, query, and exact label |
|---|---|
| Latest numeric | Same numeric histories; latest event for requested key at/before T by stable `(timestamp,event_id)` order. Return its entire observed value vector; unsupported if absent. Numeric error is separate from hard-window loss. |
| Presence/absence | Separate fixed-one-hot histories use 12 active keys sampled uniformly from the 16 valid public coordinates; the other four coordinates have no writes. Half queries request an observed active key, half a valid omitted key. Do not expose the active set, an OOV/zero feature, a reserved-ID bit, or any query-only absence cue. In dense-feature arms, absent IDs come from the same ID/feature distribution as written keys. Label is whether that key has any event at/before T. Empty-window support is separately whether every requested interval has an observation. Evaluate false positives and calibrated support without inventing numeric labels. |
| Change sign | Same adjacent-window queries with both windows supported; per-coordinate label is `sign(exact recent mean - exact older mean)` in {-1,0,+1}, with exact-zero ties. Initially derive predicted sign from numeric contrast output, avoiding an extra trained head. |
| Corrected categorical fact | Separate shape-matched V=32 one-hot-value stream: one category per key, initially Uniform{0,...,31}; at each key observation change to a uniformly chosen different category with probability 1/8, otherwise repeat. No future-revision flag. Target is the latest observed category at/before T, or unsupported if absent. Use categorical logits/cross-entropy and exact-match accuracy. |
| Random binding/capacity | Separate V=32 stream with iid Uniform{0,...,31} category on every event; ask for the latest category for a key. Same stable latest label and support rule. Vary key load independently of elapsed span; all method state/reader bytes are recomputed for this categorical shape. |

The categorical arms train/tune their own compatible readers/writers and never load an eight-value numeric checkpoint. Preserve the same public information and budget rule within each arm. Sharp-boundary recall is an adversarial hard-window suite, not an exponential target.

## 7. Real workload

Use UCI Beijing Multi-Site Air Quality, DOI 10.24432/C5RK5G, archive `PRSA2017_Data_20130301-20170228.zip` (R16). Verify actual schema/stations/timestamps/counts, hash archive and retain attribution/license. Stream extraction with path validation and declared disk bounds. If unavailable, finish synthetic work and mark real transfer untested; replacing the dataset requires a dated amendment and a new protected split.

Use PM2.5 only: one scalar observed event per station/hour, omit missing measurements without zero imputation, advance known elapsed time, retain all extreme values. Initial fixed shape is 12 one-hot station keys and V=1. No shared denominator across differently missing channels. Four/eight/sixteen jet anchors use 768/1536/3072 FP32 payload bytes plus metadata.

Treat hourly timestamps as dataset-local civil hours with a documented timezone convention; do not introduce a system-local DST shift. Training is `[2013-03-01,2014-09-01)`, development `[2014-09-01,2015-01-01)`, protected test `[2015-01-01,2017-03-01)`. No episode crosses a split. Builder decision: reserve November–December 2014 development histories for abstention calibration; tune on September–October. Use 14-day histories, query ages/windows of 1–168 hours, native observed-event means/contrasts and observed-count diagnostics. Fit normalization only on training.

Protected histories are fixed nonoverlapping 14-day blocks anchored at each split start; all stations stay together. Events belong to `[block_start,block_end)` and queries use `T=block_end`, with temporary no-write decay from the last observed event. The event at block_end belongs to the next block. Drop trailing incomplete blocks and report counts. Primary uncertainty clusters pairs into 28-day blocks; repeat with 56-day clusters. Extra station/question rows are not independent samples. Finite cluster counts can force an inconclusive result.

Transfer modes: (a) separately train a **12-key/scalar** synthetic model under the selected procedure, freeze learned weights, apply target-training-derived unit normalization, and call it calibrated shape-matched transfer; (b) equally tune each family on real training/development. A 16-key/eight-value checkpoint is incompatible. Report both modes, each with a predeclared primary metric; never choose the better mode after protected evaluation.

## 8. Required comparators and fidelity

| Family | Exact local obligation |
|---|---|
| Distinct poles | `2J` augmented FP32 states, same key/value writer and metadata as J jets; `Z'=exp(-lambda*Delta)Z+X`. All anchors visible. Tune log grids, bounded learned log-rates, range extensions, separated anchors, direct/normalized MLP reads and optional finite differences. Optional no-decay state counts. |
| Equivalent gamma/Laguerre | Invertible state transform from section 5 and identical recovered-state reader; cannot support an expressivity claim. |
| Simple packed storage | Recent ring, uniform reservoir, ring/reservoir split, mergeable temporal buckets, bounded per-key latest/LRU, and exact unbounded history. Count IDs/times/counts/occupancy/counters and policy metadata. |
| Polynomial HiPPO | Translated-Legendre impulse adaptation plus single/multiscale bank; query endpoints and all coefficients available, no positive-denominator requirement. |
| Log-timescale HiPPO Zoo | Reproduce R07's **log-rate script**, finite temporal/scale orders and input coefficients; verify diagonalized propagation against dense Kronecker system. |
| Modern delta | Native GDN-2 recurrence with exact KDA and gated-delta ties; full local mixer includes short causal convolution, projections/gates and FP32 state. Count convolution cache. Select tied/untied family on development. |
| Supplementary | Equation-based Gaver timeline with precision/input conventions verified; associative HiPPO port plus original short-task positive control; compact GRU/routing if justified. Record exclusions before confirmation and narrow claims. |

Temporal buckets store key, oldest/newest time, count, value sum, occupancy and merge/eviction metadata. Create singleton writes; when full, merge chronologically adjacent same-key buckets with minimum combined span and deterministic tie-breaking. Builder decision: if no merge is possible, evict all buckets for least-recently-observed key (tie by uint64 key ID); count recency metadata. Estimate contributions by temporal-overlap fraction, treating point buckets exactly. Compare the arithmetic decoder and a learned reader of the same buckets. No formal approximation guarantee is claimed. Ring/reservoir reads return a support result for zero matches. Reservoir counts and RNG/counter state count toward budget.

Polynomial order n uses zero-based `b_i=sqrt(2i+1)` and

```text
A_ij = -sqrt(2i+1)*sqrt(2j+1) * ((-1)**(i-j) if i<j else 1)
P' = expm(A*Delta/tau) @ P + (b/tau)*X
```

This is an event-measure adaptation; sampled-signal reproduction instead uses the exact ZOH input from an augmented matrix exponential. For log-timescale order m, `L=log(1/epsilon)`, Jacobi `Jx` has off-diagonal `r/sqrt((2r-1)(2r+1))` and zero diagonal:

```text
G = sqrt(epsilon)*expm((L/2)*Jx)
beta_r = sqrt(epsilon)*sqrt((2r+1)*L)*i_r(L/2)
B = b beta^T
dot P = A P G / tau0; impulse adds B*X/tau0
```

Validate modified spherical Bessel coefficients against converged quadrature. Diagonalize symmetric G once; store `P U`, propagate column j with `expm(A*gamma_j*Delta/tau0)`. `n*m` matches `2J` or lies on the reported frontier. Use bounded gap-alphabet caches; count arbitrary-gap preparation. Construct matrices in CPU FP64, validate FP32. Scale inverse-time features by `t_ref` for unit conversion. The finite Jacobi exponential is not an exact infinite-dimensional operator.

GDN-2 uses `Sbar=diag(alpha)S`, `S'=Sbar + k[(w*v)-Sbar^T(b*k)]^T`, external read `S^T q`, normalized keys/queries, decay before erase, separate erase/write gates. `b=w=beta` gives KDA; scalar/tied alpha then gives gated delta. Include causal depthwise convolution (initial size 4), SiLU, projections, published gate initialization/range variants, output normalization/gating and task reader. Public Delta enters the causal encoder; continuous-gap decay is separately named and not a verbatim paper reproduction. No Triton/FLA assumption on MPS. Respect R11 source restrictions; independently written equations still need attribution and do not establish legal clearance.

Gaver impulse adaptation retains rates `k*log(2)/tau_a`, k=1..N, even N, and fixed Stehfest reconstruction before a task reader. With m=N/2, use the supplied brief's equation:

```text
eta_k = log(2)*(-1)**(k+m) * sum over j=ceil(k/2)..min(k,m) of
        j**(m+1)*(2*j)! / ((m-j)!*(j!)**2*(k-j)!*(2*j-k)!)
f_hat(tau) = sum_k eta_k*F(k*log(2)/tau)/tau
```

Construct weights via CPU FP64 log-factorials; verify against an independent high-precision reference. N=2 yields `[2*log(2),-2*log(2)]`. R22's reported ZOH/exprel input and FP64 buffers require a separate reproduction. Every retained rate counts, and FP64 consumes twice FP32 bytes. Never vendor source with unresolved permission. Associative HiPPO must follow actual scalar-location Legendre/minimum-norm-delta code, count both history and associative state, and pass its short-task control before task-adapted interpretation.

## 9. Budgets, tuning, and costs

Persistent bytes include **all history-dependent information surviving between events or queries**: numerical state, normalization, keys/timestamps/status, conv caches, counters, occupancy, indices and hidden caches. Count logical packed/tensor bytes by dtype; physical resident/driver memory and serialized sizes are separate measures. Static parameters/buffers are separately listed and included in end-to-end totals. Compressed checkpoint size is not the capacity budget. No unused expanded values to inflate a scalar experiment's apparent budget.

Three comparisons are required: exact J-versus-2J payload/metadata match; actual used bytes under common persistent and active-parameter envelopes; quality–cost frontiers across state, precision, reader parameters and latency. Also compare parameter-matched and compute-matched readers, equal tuning expenditure and best credible development selections. All trials/failures/compute survive in the ledger. Learning curves and task-relevant positive controls establish baseline acceptance; equal epoch counts do not establish convergence.

Initial learned-component search: AdamW FP32, learning rates 1e-4/3e-4/1e-3/3e-3, weight decay 0/1e-2, widths 64/128/256. Select schedule/clipping/rate range/state allocation on development with logged continuation when optimization remains unresolved. Rates use bounded sigmoid log coordinates; save bounds, allow collapse and report it. Rate search starts at reciprocal training horizon endpoints and permits range extensions. Do not stop a baseline's tuning solely because it is beating jets.

Jet payload is `4*2*heads*J*K*(V+1)` bytes. H=1,J=4,K=16,V=8 is 4608 bytes; H=1,J=8,K=32,V=64 is 133120 bytes. Batch16/head4 at the latter dimensions is 8.125 MiB; retaining 2048 such states is 16.25 GiB before other training allocations. Approximate FP32 Adam training weights/gradients/moments as 16P bytes plus activations/workspaces/overhead. Chunk terminal contractions and use common verified recomputation before changing the scientific shape.

Headroom is measured on identical histories as `L_simple-L_oracle`, not forecast attainable gain. For Q queries, report `preprocessing + ingestion(T) + Q*query_cost + output_generation(Q)`. Break-even `(Cjet-Cbase)/(Rbase-Rjet)` exists only with positive denominator, appropriate numerator/domain, and satisfied accuracy constraint; otherwise state none. Encoder/embedding/output costs do not vanish with compression.

## 10. Evaluation and protected analysis

Primary H1 loss: coordinate-mean squared error divided by frozen training-only target scale squared, then average queries within task/history, tasks equally, histories with frozen regime weights. Builder decision: use one task-specific scale from pooled training target coordinate variance; report constant coordinates separately in absolute error. Also report native RMSE/MAE. Positive effect is `L_bank-L_jet`. Query count and training seeds never replace independent histories.

Every valid primary query receives loss. Unsupported/nonfinite predictions fall back to the training-only unconditional task mean, retain a failure flag and full resulting loss. Categorical arms use the training-only class distribution with deterministic argmax ties and full categorical loss. Quarantine a nonfinite episode state and use the same fallback for later queries; preserve triggering inputs. Abstention is a separate coverage/risk measure. Freeze support floors, eps, calibration, numerical-failure stability guard and fallback before confirmation; never silently drop or rerun unfavorable examples.

Split manifests reserve pilot, protected confirmation and replication before extensive tuning. A preflight rejects missing/null scientific fields, unknown split versions, development namespaces, unaccepted required baselines, mismatched source/dependency/data/weight hashes and incomplete paired run inventory. Freeze populations, task/regime weights, primary pair/budget, other families, training/stopping/seeds, metrics, resampling, failure policy, support behavior, tolerances, timing boundaries, H/S and multiple-testing procedure **before opening protected outputs**.

One development-selected primary pair/budget gets one primary two-sided 0.05 comparison. Additional budgets, load claims and family comparisons form a secondary Holm family at FWER 0.05, unless a different aggregate was registered beforehand. Compare required families separately. The runner seals per-model protected scores until every declared run completes or a documented failure is resolved; completeness is checked against the manifest rather than discovered output files. Keep raw predictions restricted from the exploratory interface until unblinding. Administrative sealing is an accidental-peeking guard, not protection against a malicious local administrator.

Use paired history/training-replicate effects d[h,s]. Independently resample histories (stratified by regime) and paired training replicates, evaluate their Cartesian product, and save seed/draw count and endpoint Monte Carlo diagnostics. Builder decision: use a two-sided 95% percentile crossed-bootstrap interval for the primary effect. For secondary two-sided p-values, center d by its observed weighted mean, perform the same crossed resampling under this empirical null, and compute `(1 + count(abs(null_mean) >= abs(observed_mean))) / (draws + 1)` before Holm. These bootstrap procedures are approximate, require pilot simulation checks, and do not claim exact small-sample coverage. Report every replicate effect. For real data use frozen temporal clusters, 28-day primary and 56-day sensitivity. Few seeds/clusters or wide intervals mean limited/inconclusive inference.

Predeclare Monte Carlo precision control: begin at 2000 total draws split equally into four independent batches, double total draws to at most 128000; compare each endpoint's four batch estimates and estimate its standard error as their sample standard deviation divided by sqrt(4). Require both endpoint standard errors below 1% of the pooled interval width. Exact all-zero A/A is handled as a degenerate zero-width interval. Select the initial confirmation draw count from pilot evidence; the same frozen doubling rule can add resamples, never histories, after confirmation. At the cap, report endpoint uncertainty and withhold a strong significance claim if the criterion is unmet.

Pilot starts at 128 independent histories and four independent training replicates on cheap settings; expand nuisance estimation if unstable. Plan `V(H,S)=sigma_history²/H+sigma_seed²/S+sigma_residual²/(H*S)`, sensitivity `2.80*sqrt(V)` at two-sided .05 / 80% power, and validate with simulated resampling. Do not size solely from a favorable effect. Select a fixed feasible H/S from precision-versus-measured-cost curves. Sequential stopping is forbidden without a separately specified valid method. Replicate supported frozen comparisons on fresh histories and new training replicates without retuning.

Harness controls: identical-method A/A, independent same-family retraining, known-better exact-history versus an insufficient ring, wrong moment sign, reversed temporal labels and forbidden query-leaking writer. Snapshot hashes remain unchanged under read/query permutations. SVD fixtures construct bounded signed histories in one kernel-bank nullspace but not the other's, and reverse; verify residuals/rank rather than asserting uniform dominance. Report finite-state/bit and learned-writer limitations correctly.

## 11. Local execution and numerical gates

WP00 reruns discovery, records power/pressure/disk, resolves a compatible native-arm64 Python/NumPy/SciPy/PyTorch/pytest/YAML stack, and creates a project-local environment and exact hash lock only after resolution. The observed Python 3.14.6 is not assumed compatible with a particular wheel. No system upgrade is authorized. Resolve installed-version official documentation instead of pretending the brief's PyTorch 2.14 documentation is an installed dependency. Optional plotting/pandas packages are justified separately. Preserve allocator protective limits.

Native MPS runs set `PYTORCH_ENABLE_MPS_FALLBACK=0` before torch import and keep reference fast-math off. Check built/available status and installed synchronization/memory APIs. Test CPU FP64 and CPU/MPS FP32 planned shapes for exp/arithmetic/reductions/matmul/einsum, activations, normalization, indexing/gather/masks, MLP forward/backward, differentiable rates, checkpointing, short convolution, serialization and RNG restore. Ordinary bounded FP32 fixtures start at rtol 1e-5/atol 1e-6; inspect violations and conditioning, do not widen automatically. FP64 CPU is the oracle. Lower-precision states are a separately registered frontier experiment.

Start batch1/head1/J4/K16/V8/length128 FP32. Measure warm peaks, driver recommendation and OS pressure; choose an envelope below available memory with observed reserve (initially leave at least a quarter of the derived envelope). Do not double-count resident and Metal allocations as independent unified-memory pools. Reduce microbatch with accumulation, exact chunks, and verified recomputation before scientifically changing length/shape, equally for all methods. Before assets/runs check raw+extract+temporary+checkpoint+log disk needs. Stream synthetic generation and bound caches/checkpoint retention.

Timing separates cold start, preprocessing, writer, state query, reader, serialization and total; training is separate. Use eval/no-grad, explicit batching, warmup policy, monotonic timer, synchronization immediately before/after device regions, randomized paired method order and multiple separated blocks. No hidden `.item()`/CPU transfer in a claimed asynchronous hot loop. Sub-ms operation-block timing is distinct from interactive latency. Report p50/p95, throughput, sustained power/thermal/pressure conditions and uncertainty at block level. Forecast training only from measured pilot throughput, including validation/checkpoint work.

## 12. Artifacts, reproducibility, and authority

Use strict versioned configuration and artifact schemas. Suggested file ownership and exact implementation task signatures are in the plan. The smoke configuration has schema_version=1, seed=20261013, initial_spec_v1 generator, one-hot16/V8/length128/eight queries, jet/head1/J4/K16/FP32/fixed rates [0.001,1.0], structured width128/two layers, eps1e-8, no interpolation, one probe, fixed writer, terminal encode, micro/effective batch1 and AdamW lr1e-3/wd0. Smoke optimizer steps must be explicit; confirmation scientific fields remain blocking nulls until pilot freeze. Confirmation has named comparator configurations and real used resource envelopes.

| Artifact | Required contents |
|---|---|
| `run.json` | ID/phase/status/failure category; UTC start/end; source commit+diff, plan/amendment, lock, machine, config, dataset/split and parameter hashes; seeds; expected/actual budgets; checkpoint paths. |
| `predictions.jsonl` | Run/replicate/history/cluster/query/split/regime/task/load IDs; event count/span/time units; window; target/prediction/support; normalized/native error; nonfinite/abstention flags; payload bytes/diagnostics. Missing results are explicit status/null, never zero. |
| `timing.jsonl` | Shape/device/precision/boundary/cold-warm/block/order/repetitions/time; sync policy; event/query counts; memory/pressure/power; status. |
| `assets.json` | URL/DOI/revision/hash/size, actual schema, license/intended permitted use, source versus derived expenditure, preparation commands/exclusions. |
| `manifests/confirm.json` | Immutable schema/code/dependency/data/metric/config/weight commitments, complete expected run matrix, protected namespaces, analysis/stopping/calibration/failure/timing policies and unblinding record. |
| `amendments/` | Dated reason/evidence, affected hypotheses/population/configs/hashes, whether fresh protected data are needed. |

Checkpoints include model/optimizer/scheduler/scaler if used, Python/NumPy/torch CPU and supported MPS RNG, sampler position, completed step and accumulation position, config/source/data hashes. Default saves at complete optimizer steps; restart unfinished accumulation if gradients were not serialized. Stream snapshots include event offset, last time and every method cache plus writer/rate hash. Use atomic temp+rename, checksums and previous valid checkpoint. Reject schema/parameter mismatch and stale caches. Deterministic CPU resume must match consumed examples/steps and trajectory exactly where supported; MPS needs an executed tolerance/determinism record, no assumed bitwise equality.

Durable `PROGRESS.md`, `DECISIONS.md`, and `AUDIT.md` name completed gates, evidence/artifact paths, failures, active blockers, next action and resource calibration. Agent authority covers routine reversible implementation and mathematically equivalent batching/chunk reductions. Changes to hypotheses, information access, population/splits/metrics, precision/state capacity, baseline architecture, stopping, or interpretation require a dated methodological amendment and fresh protected data when necessary. Preserve failed and invalidated runs.

## 13. Optional extensions and stop conditions

Interpolation remains off until direct-sum dense log-rate-grid development tests bound numerator/normalizer error, negativity, boundaries, cancellation and fallback frequency. Interpolate unnormalized Z and slope -H in log-rate, not normalized reads; no extrapolation. Floors/fallbacks change the function and incur bias/cost. Scalar monotonic normalization does not certify signed numerators.

Two/three probes may route mixtures over anchors with an updated controller; compare with full-state one-shot readers of equal total depth/FLOPs and include every contraction. Re-reading a finite state adds no information. Routing/overwrite/hybrids require evidence of interference or complementary residuals and count all banks/recent events for every method.

Enter language only after numerical/harness gates and either relevant H1/H4 evidence or oracle diagnostics indicating a missing bridge. Start with pinned official Qwen3-0.6B; 1.7B requires measured capacity and oracle need. Safe tensor weights, tokenizer/config/license/hash records, native eager-path check and no required remote-code execution. No weights downloaded during planning.

Templated held-out event QA first: independently encode history without eventual query, train writer/reader/prefix projections, freeze decoder weights. Prefix smoke length4; train through frozen decoder without `no_grad` on answer forward, mask prefix/query loss, no answer tokens at test. Compare query-only equal-budget, exact/oracle bridge, each compressed memory and time-filtered text/BM25 retrieval with all evidence/index/token costs. Test nonzero prefix gradients, unchanged decoder weights, oracle solvability, first-answer alignment, genuine adapter-off bypass with identical backbone logits, and active-adapter regressions. Frozen decoder weights do not imply unchanged active behavior. Cached training features never become hidden inference history. Real benchmark subsets need their own license/revision/protocol and fresh protected registration; local judges/subsets are labeled nonofficial/non-comparable unless validated.

## 14. Work-package gates and traceability

| WP | Required deliverable | Exit / claim limit |
|---|---|---|
| WP00 | Doctor, lock, op/gradient matrix, resource/asset provenance | Correct CPU path is sufficient; accelerated claims require native checks. |
| WP01 | Direct/recurrent/terminal algebra, derivative, coordinates, gradients, units, adversarial invariants | Broken ordinary arithmetic blocks dependent work; interpolation failure only disables extension. |
| WP02 | Deterministic data, exact labels, real manifests, isolation and harness controls | No training until labels/leakage/boundaries are correct. |
| WP03 | Strong simple and equal-byte controls, full bytes, development headroom | Simple winners remain visible; sufficient-reader positive controls pass. |
| WP04 | Complete candidate/readers/training/streaming/serialization | Working mechanism may have no advantage; no result inferred from checkpoint existence. |
| WP05 | Polynomial/log-scale HiPPO and native delta fidelity, accepted development learning | Required before broad competitiveness; unsupported kernels do not count as defeats. |
| WP06 | Pilot variance/optimization/cost/frontiers and fixed feasible confirmation | Proceed independent of favorable sign; unresolved sensitivity means narrower/inconclusive claim. |
| WP07 | Frozen manifest, all paired protected runs, crossed analysis/Holm | Complete fixed plan before unblinding; fresh data for changed claims. |
| WP08 | Both real transfer modes, native errors, temporal-cluster uncertainty | Synthetic-only or insufficient clusters limit conclusions. |
| WP09 | Separately gated interpolation/probe/language controls | Optional; record “not entered” with reason rather than fabricate completion. |
| WP10 | Frozen replication when supported, resume, clean rebuild/report/audit | Another engineer can reproduce a scoped decision without this chat. |

Final reports list all evaluated configurations, favorable/unfavorable/failed results, paired uncertainty, resource frontiers, training+tuning costs, numerical failures, assets/licenses/revisions, amendments and scope. Wording reports tested population, bytes, effect/interval/comparator and measured ingestion/query cost. If simple retrieval dominates, recommend it; if results are imprecise, report detectable effects and missing evidence. No optimistic relabeling of a null or negative result.
