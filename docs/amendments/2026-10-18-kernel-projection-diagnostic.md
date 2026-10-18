# DRAFT — kernel-projection diagnostic, 18 October 2026

**Pending independent amendment review and explicit root adoption. UNADOPTED.** This document proposes a source-only Stage A component. It authorizes no implementation, fixture generation, numerical/reference work, performance probe, model evaluation, training, corpus/cache preparation or protected access. Stage A execution requires a later independent source review and sealed, separately released allocation. Stage B remains outside this proposal's allocation.

## Evidence and question

The completed [epsilon 1e−6 structured pair](../research/task18-epsilon1em6-learning-results.md), executed at `76e5f8cea0c4bfc763ecefcd35184950562caeb3` / package `57c0920f360e47f2c3978f056437143c4262b8ab9653b753df1321402ade9717`, passed both fresh8192 runs, all24 trained endpoint cases at original1e−12 bounds, and both complete6144-history frozen TRAIN-risk passes. Final development loss was Jet0.394466304318 / Bank0.388818437531; TRAIN risk0.418266511484 /0.468650240247. Jet worsened0.355% over its last doubling; Bank improved1.941%. The unchanged shared-bucket control scores0.1364947755 on the same common768-scale/96-history panel. Long2048 trend/reset cells dominate. One initialization, an empirical reused corpus and exposed development data cannot establish convergence or inferential advantage.

The [original epsilon1e−8 structured stage](../research/task18-structured-stopped8192-report.md) remains FAILED at its trained input-gradient gate. Its Bank run did not execute. New epsilon1e−6 results neither repair that gate nor authorize a forward-only reinterpretation of it. The accepted current pair is a separate result, with all historical failures and costs retained.

These observations justify considering a legal alternative read from the same state before more blind SGD. The question is whether a deterministic query-conditioned projection can use information already retained more effectively than the achieved MLP readers. A better result would demonstrate achievable use on the evaluated panel; it would not distinguish optimization from finite function class, conditioning or inductive bias. A failure gives no information-loss bound, optimal-recovery certificate or family defeat.

The [design](../research/task18-kernel-reader-design.md) and [independent design review](../research/task18-kernel-reader-independent-design-review.md) remain design evidence. The corrected [fixture manifest](../research/task18-kernel-reader-fixture-manifest-draft.md), SHA `bef00e8ff086e7b902956550c0e0bde5173b46acc49d50994f9b57cd8973310b`, is the proposed exact Stage A contract. Its [original review](../research/task18-kernel-reader-fixture-manifest-review.md), [F1 response](../research/task18-kernel-reader-fixture-manifest-fix1.md) and [follow-up review](../research/task18-kernel-reader-fixture-manifest-fix1-review.md) are preserved. Contract/technical approval is not adoption or execution permission. This draft incorporates the corrected three-way acceptance policy and narrower timing inventory; older optional repeated timing blocks are not included.

## Proposed source-only scope

After amendment review and adoption, the first possible release is source-only:

1. A dedicated `famjet/readers/kernel_projection.py` implementing closed FP64 stable Gram/window integrals, canonical diagonal-scaled ridge factors, contractions, eligibility and diagnostics. No learned weights, parameter padding or per-history coefficient/factor cache.
2. A small fixed-kernel MemoryMethod wrapper, for example `famjet/models/kernel_read_model.py`, delegating existing Jet/Bank initialization, writing, advance-copy and snapshot accounting. It owns the declared immutable factors and frozen fallback vectors and accepts only snapshot/public query/static inputs. It does not override NumericReader or introduce a second trainer.
3. Explicit closed numeric export/reconstruction registration in `famjet/eval/isolation.py`, using the existing clean worker and snapshot/query transport. Unknown fields, extra attributes, executable handles, hidden state and undeclared retained arrays must fail closed.

Focused TDD must cover independent small analytic controls, strict schema/precision/static reconstruction, source/parameter/state identity, preserved snapshot hashes under query order and delayed copy, invalid inputs and truthful failure/support behavior. Isolation tests must prove reference histories/labels/metadata cannot enter the production worker. Account actual Python/NumPy/tensor/config/static ownership, serialized bytes and transient copies; tensor-only accounting is insufficient. No broad factory refactor, training/config whitelist, trainer, learned MLP, raw/feature-cache identity or compatibility-policy change is proposed. If this requires another production behavioral area, stop and present the concrete dependency before expanding scope.

## Frozen mathematical and information contract

Use only current fixed-writer CPU64 Jet4 and Bank8, one head, one-hotK16/V8, full fixed log grids `[1/5224,1]`, eight canonical kernel channels and9345B persistent history state. No additional history fields, state channels, writer learning, rate change, precision change or new prior fitting.

Jet channels are `exp(-alpha*x)` and `(alpha*x)exp(-alpha*x)` at four rates; Bank channels are eight exponentials. Recover canonical coordinates before applying the canonical diagonal Gram scaling and ridge metric. Gamma/Laguerre transformed checks transport that same metric; they do not introduce a new identity ridge or reader.

The only design prior is exponential with physical scale `L=5224`, dimensionless inverse scale `eta=t_ref/L`. L is a global training-derived scale, not the actual history span or a factual bound. Preserve its training provenance. Ridge values are exactly `{1e-10,1e-6,1e-2}` per family. Apply identical window coefficients to retained numerator and normalization channels. Mean retains half-open observed-event semantics; contrast is recent mean minus adjacent older mean, normalizing each window separately. No ZOH reinterpretation or single shared contrast denominator.

The reconstructed denominator uses epsilon1e−8 and numerical mass floor1e−8, distinct from the trained structured feature epsilon1e−6. An eligible window requires finite inputs/results, nonnegative canonical normalization channels, nonquarantined state, `Chat>1e-8`, and `Chat>64*2^-53*sum_r(abs(c_r)*N_r)`. Both windows must pass for contrast. No mass/ratio clipping, positivity repair, epsilon search or history-assisted rescue. Mass scaling can change epsilon shrinkage and eligibility; it is not asserted invariant.

Production receives only the read-only snapshot, public key/task/window/T, existing snapshot time/validity and frozen public static model data. Allowed static ownership includes rates, t_ref, prior/ridge/policy constants, factors, schemas/hashes and already frozen training-only scales/fallback means. No raw events, reference handles, actual history length/span/first time/ages/counts, factual support, regime, oracle labels, generator metadata, hidden dictionaries, per-history tables, disk-history access or ID-conditioned routing. Ownership IDs validate schemas only. Queries follow writing; T before snapshot time is rejected. Later reads use existing causal advance-copy, including Jet's cross-term, without mutating the resumable snapshot.

Reconstructed mass is neither an observed count nor factual support/probability. Support calibration remains unavailable. Failed reads retain failure categories and the existing frozen unconditional task-mean fallback; subsequent nonfinite-state quarantine remains effective. Empty and unsupported fixtures retain the existing target-validity convention, not fabricated labels. Hard-window reconstruction error is a modeling error distinct from correctness of the declared formula.

## Stage A execution is separately gated

No Stage A run is released by this draft. After source review, a concrete seal must bind the adopted amendment, source/package/lock/runtime, implementation and independent reference, exact corrected fixture manifest and represented rates, factors/fallback provenance, numeric schemas, ownership ledger, resource boundary, fresh outputs, host observations, whole-group timeout and root execution ruling. Null fields block execution. No runtime dependencies may be installed implicitly.

The fixed inventory is32 deterministic base fixtures and at most four predefined realizations each across two families and three ridges: at most768 total production reads **including timing**. Use exactly the manifest's represented values, row IDs, transform definitions, skips, fixed family/ridge order and row order. No candidate-dependent search, replacement slot, adaptive extra ridge/prior, repeated scientific history generator or sufficient-reader retraining.

The corrected manifest supplies exact event lists, query arguments and transforms. Construct at most one canonical gate-one snapshot per row/family; copy/scale/corrupt only declared variants. Reference event handles remain outside the worker. Exactly six production static factor constructions are permitted; reference setup at each required precision is charged independently. Keep all setup/serialization/copy counts as actual executions rather than multiplying descriptors.

An independent80/160-digit reference implements the defining integrals and solve without importing production coefficient, factorization, contraction or decoder helpers. Validate precision agreement, residuals and exact represented input bits. Compare meaningful matrices/coefficients/contractions/predictions and decisions, not eigenvector sign/order. Keep original pointwise atol=rtol1e−12, applicable existing memory/coordinate tolerances and exact semantic decisions. No gradient or fitted-MLP certification follows from a new deterministic forward diagnostic, and no old gradient gate is weakened.

### Three-way attribution and stopping

Let P be the production decoder, A the independent reference applied to the **actual supplied snapshot**, and B the independent event-level reference. Preserve all planned comparisons and original tolerances.

| Comparison | Meaning and consequence |
|---|---|
| P versus A | Reader arithmetic and eligibility/failure decisions. A direct mismatch fails and stops that candidate after retaining the current slot's planned evidence. |
| A versus B | Source-state fidelity. A stable mismatch remains a source failure; identical decisions do not excuse an excessive finite-output error. |
| P versus B | End-to-end result. Source-attributable failure remains FAILED; a reader-only pass cannot erase it or yield a global Stage A PASS. |
| Reference precision/residual/engine, unresolved decisions, common provenance/isolation or resource failure | Stop the whole stage; dependent comparisons remain unverified. |

Source-only failure may leave the remaining original reader-diagnostic slots available under the same caps, as the reviewed F1 policy states. It permits no replacement, retry or cap expansion. Other candidates proceed only while common prerequisites remain valid. Transform discrepancies use the same attribution. No isolated-reader PASS automatically releases Stage B or accepts a family; root must review all failed source/end-to-end evidence and ordinary source applicability separately.

### Proposed resource and timing contract

These limits require explicit later adoption/release and are **stop budgets, not measured forecasts**:600s outer elapsed including preparation/reference/serialization/reporting;90s per candidate (timeout stops the whole stage);201326592B incremental peak per worker with absolute/process-tree memory also recorded;64MiB new outputs including temporaries; at least4GiB free at launch. CPU64 only, at most four numerical-library threads, sequential deterministic reference, no performance concurrency, accelerator, power override, retries or artifact deletion.

Canonical I is the cold construction/encoding/read/output group. O/U/R are the manifest's three transformed groups, not identical-workload repetitions. No extra warmup or dedicated timing predictions are added. Report actual per-call/group timing, transform/fallback mix and timer resolution; sparse heterogeneous calls do not establish stable p95, equivalent throughput or speed advantage. Charge all failures, factor setup, scalar reference, fixture copies, fallback/static ownership and serialization. Source-only continuation consumes only existing slots/caps. Stage A ends with a complete report and root ruling, even if all eligible checks pass.

## Source provenance, later work and unchanged obligations

The new package files will change whole-package identity. Freeze the actual independently reviewed new source and construct only the bounded current-source fixture snapshots. Compose prior memory evidence only through exact unchanged component, represented-kernel, state, fixture and probe proof. Do not re-sign current learned caches/checkpoints, claim full-HEAD equality, broaden source compatibility, or trigger another6144 refresh merely for this source-only diagnostic. The current learned campaign remains historical and is closed without automatic16384 continuation.

Stage B is not allocated: no common96 panel, fitting,6144 corpus/cache, frozen TRAIN pass, SGD, new seed or protected/statistical work. Any later panel comparison requires its own measured resource/source-bound snapshot preparation, existing common training statistics and central failure-complete scoring, exact prospective selection/tie policy and root release. Stage A arithmetic success alone does not justify panel access.

The [design specification](../superpowers/specs/2026-10-16-famjet-design.md) and accepted Task18 rulings remain binding. Generic/full-state attribution, gamma equivalence, independently learned writers/time-input fairness, credible modern-family task adaptations, load/state/reader/latency frontiers, support calibration, optimizer/convergence and equal-tuning/best-credible comparisons remain open wherever previously open. No excluded/unconverged family is called defeated. Task19 scientific calibration and protected pilot/confirmation/replication remain closed to this amendment. This diagnostic neither replaces those obligations nor completes Task18.

**Next decision:** independent review of this dated draft, then explicit root adoption and at most the narrow source-only release. Implementation and numerical execution remain unallocated until their respective gates are satisfied.
