# Task18 learned CPU64 evidence review — 2026-10-17

**Spec-compliance: approved within the declared exploratory and reader-diagnostic scopes. Evidence quality: approved; no blocking findings.** This is not Task18 scientific acceptance, convergence certification, or approval of the separate prospective width128 source change.

Historical candidate identity is `6bf10f311480293154a6793ba2c582cdd2677bc7`, package `b898bef145c0edbd2298240a022f6458fa6724f0b8ba0b1144488fe1a1b51bbc`. I used that pinned revision for the few relevant production-source reads. Verification consisted of saved-artifact hashes, checkpoint envelope decoding, row/accounting checks, helper inspection and saved-fixture tensor inspection. No models, suites, oracle campaigns or training were rerun; no source/index/Git mutation occurred.

## Provenance and 8192-step evidence

`docs/research/task18-cpu64-learning-closure.json:1` maps 35 promoted records/helpers to their original files. I verified every promoted and original SHA256 against that mapping, plus all 14 links in `docs/research/task18-cpu64-learning8192-summary.json:1`. The durable narrative is `docs/research/task18-cpu64-learning-report.md:3`.

Both saved checkpoints have the declared source and completed step 8192; their envelopes and checkpoint hashes match the summary and numerical/reader procedures. Both retain the same 768-history fit identity `5f1fe6cb…` and target-statistics hash `0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21`. The resumed draw logs are identical across families: all 18,432 positions 6144–24575 match the ordered raw-cache manifest's history IDs and raw hashes, with offsets/passes consistent with four cumulative passes over 6144 histories. The configured horizon remains 32768, not an executed-horizon claim.

I checked each family's 768 final query rows: 96 unique histories, unique history/query keys, identical evaluation inventory, all payloads 9345 B, and common statistics. Reaggregating these balanced rows gives Jet **0.3926415916562571**, Bank **0.38709692292594683**, with zero failure/nonfinite/fallback counts. The small difference is exploratory on exposed development data; it does not identify a converged winner. The summary preserves continuing improvements and the single-initialization/shared-corpus limitations.

The frozen empirical-training-risk helper (`docs/research/task18-procedures/task18_learned_frozen_risk8192.py:19`) loads the exact checkpoint, recomputes raw states without a feature cache, and evaluates existing training loss. Its loop writes a row for every history; failed objectives prevent a successful aggregate instead of dropping histories. All 6144 saved rows per family match cache IDs/hashes, with 512 histories in every length/regime cell and no fallback substitution. Recomputed means are Jet **0.4549925604176848**, Bank **0.46506786570244757**. These are training objectives, not independent development scores.

Without repeating the Decimal formula review, I checked all 24 endpoint summary/reference/candidate/procedure mappings and pointwise tolerances. They map to the exact step8192 checkpoints and raw fixtures, with all corrected metrics passing `atol=rtol=1e-12`; the fitted task/reader checks also pass. The original Bank binary64 key-gradient failure remains recorded. The prior limitations remain: no separately captured candidate raw `dL/dr`, and no independently implemented shared `query_inputs` oracle.

## Simple-memory comparison fairness

`docs/research/task18-procedures/task18_cpu64_simple_r2.py:16` selects the exact common 768-fit statistics. Lines 27–30 check the shared 96-history inventory, public 16-key space and joint observation mask. Every simple method retains all 768 matching query rows and common target-statistics hash. Reaggregated losses and failure/fallback/nonfinite counts agree with `docs/research/task18-cpu64-simple9345-summary.json:1`.

| Method | Full development loss | Actual maximum persistent bytes | Fallback queries |
|---|---:|---:|---:|
| Shared-count FP64 buckets | 0.136494775500 | 9,247 | 0 |
| Independent-count FP64 buckets | 0.176224655814 | 9,165 | 0 |
| Reservoir | 0.281476759356 | 9,297 | 286 |
| Hybrid | 0.400186361898 | 9,307 | 388 |
| Recent | 0.661916647495 | 9,345 | 441 |
| Latest, capacity124 / capacity16 | 0.709932763125 | 9,339 / 1,347 | 740 |
| Training prior | 0.712199884974 | 0 | 0 |
| Exact growing oracle | 0 | 200,867 | 0 |

The growing oracle is explicitly unbounded. Fallback rows remain in each full loss; unsupported raw outputs are not silently removed. The static prior is explicitly scored without a causal-ingestion/state claim.

In pinned `famjet/memory/buckets.py:53`, shared normalization rejects coordinate-specific observation masks and stores one count only when every coordinate has the same mask. The helper checks that applicability before execution. FP32 presented input values and FP64 sums are explicit. Bucket updates use event-only data; queries affect readout, not writing or retention. `simple_memories` uses actual persistent snapshots to choose capacity; it does not retain an uncounted raw history. The public 16-key bound explains latest16 equivalence, and I verified exact equality of all declared prediction/target/loss/flag fields across its 768 rows and the maximal-capacity variant. No general claim beyond this key/mask population follows.

## Known-sufficient reader control

`docs/research/task18-procedures/task18_reader_control.py:25` writes the criterion and fixed 4096-update schedule before constructing/training the controls. It requires every mean/contrast task-coordinate MSE on both train and heldout data to be at most 1% of the corresponding training-only prior MSE, with no failure/invalid queries. There is no heldout-based stopping or best-checkpoint selection.

Lines 27–33 generate independent standard-normal 8D old/new values with distinct per-split/ordinal seeds and FP32 presentation. A different-key zero-valued sentinel at time1 precedes queried-key writes at times2/3. Query time3 and windows recover the older value, recent value, and their contrast. This supplies eight independently varying coordinates rather than a repeated scalar. The event stream is constructed independently of candidate memory writes; the writer remains fixed.

The analytic decoders at lines 43–50 are sufficient for this fixture: Jet has `Z=exp(-r)*old+new`, `H=r*exp(-r)*old`, while two distinct Bank rates provide an invertible two-equation system. The sentinel is on another key and does not enter these queried contractions. Actual saved rates are used. Tiny and full-fixture analytic checks pass their saved `1e-12` criteria.

Lines 52–67 load the actual step8192 kernel into a fresh production reader, explicitly freeze all upstream parameters, fit statistics on the 1024 training histories only, and materialize external features. The pinned model's parameter hash covers the kernel when the writer is absent; pre/post equality and unchanged saved rates substantiate frozen upstream state. Optimizer parameters are reader-only. Saved direct-versus-transport prediction, loss and all reader-gradient checks pass. This separate frozen-feature diagnostic does not authorize feature caching for learned-upstream benchmark training.

I verified both saved transports, final diagnostic records, fixture identities, rates and order hashes. Training/heldout history IDs are disjoint; the helper asserts 1280 distinct seeds. Both families use exactly the same fixtures and order. Each of 128 independently shuffled passes contains all 1024 training indices once; saved training logs contain every update 1–4096. Saved event arrays confirm timestamps1/2/3, distinct sentinel key, all observed coordinates and the intended independent vector layout. Direct inspection of the saved old/new arrays reconstructs every exact target hash and every FP32 label bit. Training-only coordinate prior variances and every reported MSE ratio also agree.

Both controls pass: worst task-coordinate ratios across train/heldout are Jet **0.0038821112**, Bank **0.0039399300**, below 0.01. Their own training-only normalization uses 1024 diagnostic histories; it is deliberately separate from the benchmark's common768 statistics.

## Label and resource limitations retained

`docs/research/task18-procedures/task18_reader_control.py:33` omits `target_semantics` in Episode metadata. This produced schema1 control normalization. `docs/research/task18-procedures/task18_reader_label_audit.py:12` explicitly evaluates arithmetic_version2 on **every** saved train/heldout fixture, compares exact target hashes, FP32 label bits and event/query hashes, and records zero failed queries. I verified its helper/transport hashes and all reported counts: 1024×3 training and 256×3 heldout queries per family. `docs/research/task18-reader-label-audit.json:1` and the durable narrative disclose this accurately. The audit supports reader-diagnostic labels; it does not certify scientific scorer/schema2 execution or hard-window convergence. Original artifacts remain unchanged.

Saved reader feature values occupy 2,979,840 B per family; complete external transports occupy 9,347,629/9,022,119 B. Recorded peaks are 180,977,664/176,930,816 B, below 201,326,592 B. Reader execution intervals are 15.541974/15.190540 seconds and agree closely with their UTC intervals. These are diagnostic costs, not scientific training speed comparisons.

Jet8192 continuation training records **468.154659 perf-counter seconds versus 4289.197474 UTC seconds**; Bank records 368.601642/368.600274. The promoted clock accounting and narrative preserve sleep/darkwake disruption and explicitly distinguish execution-clock intervals from CPU or civil wall time. No speed ranking, exact sleep attribution or power-override claim is warranted. No new wake forcing or timing rerun was performed during this review.

The evidence supports the reported exploratory headroom and diagnostic reader competence. Optimization, architecture adequacy on the actual benchmark, scientific comparison and Task18 acceptance remain unresolved. Width128 infrastructure requires its own separate review.
