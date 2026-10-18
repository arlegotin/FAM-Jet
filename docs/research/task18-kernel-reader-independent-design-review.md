# Independent kernel-reader design review — 18 October 2026

**Contract/spec compliance: APPROVED.**

**Technical quality: APPROVED.**

These verdicts approve the proposed diagnostic contract at the design-review boundary. They do not adopt the reader, approve an execution manifest, certify an implementation, or release either stage. No blocking mathematical or fairness defect was found. There are no severity-ranked change requests; the explicit prospective release fields remain mandatory.

## Scope and evidence

Read the amendment draft first, then the supporting design and the relevant specification requirements in §§3–6, 8–12. Narrow source inspection covered `famjet/memory/jet.py` and `famjet/eval/oracle.py`; the existing training-horizon JSON corroborates the declared training-only maximum 5224. No tests, scripts, calculations, fixture generation, probes, models, fitting, profiling or protected outputs were run or opened. This ignored report is the only edit.

Reviewed paths:

- `.superpowers/sdd/2026-10-16-famjet/task-18-kernel-reader-amendment-draft.md`
- `.superpowers/sdd/2026-10-16-famjet/task-18-kernel-reader-design.md`
- `docs/superpowers/specs/2026-10-16-famjet-design.md`

The review brief reports that the current structured epsilon1e-6 operational chain passed ALL7, including 48 fitted 0/2-step cases at the original 1e-12 tolerances; the fresh 8192-step pair is only being prepared and has no trained result. I did not independently certify those live artifacts or source seals. The draft's earlier pending-evidence paragraph is a historical drafting statement, not a current result. Its explicit requirement to update actual evidence before adoption is sufficient here and must be fulfilled in any dated amendment. The original epsilon1e-8 trained8192 input-gradient failure remains a failure; neither operational success nor this review establishes convergence or Jet utility.

## Findings supporting approval

1. **Information and query independence.** The proposed reader uses the saved state, public query, permitted existing time/validity and frozen static data. It prohibits raw-event handles, factual counts/support, first time, history span, regime and ID routing. A global training-only prior scale is permitted static information, rather than per-history metadata. Encoding precedes queries. Later queries use advance-copy, including the Jet cross-term; saved-state immutability and query-order checks are required. The independent fixture reference may use raw events, but those handles must stay outside the clean inference worker.

2. **Exact state mathematics and units.** With `x=(T-t)/t_ref` and `alpha=lambda*t_ref`, the moment kernel `(alpha*x)*exp(-alpha*x)` is exactly the retained dimensionless H kernel. Its sign satisfies `H=-partial_log(lambda) Z`; delay propagation is `H'=exp(-lambda*Delta)*(H+lambda*Delta*Z)`. The corresponding normalized derivative has the negative numerator-moment term and positive normalizer-moment term specified in §4. No derivative sign or missing lambda factor is introduced by the new reader. Scaling physical time, `t_ref` and L together and inverse-scaling rates preserves dimensionless formulas. Epsilon and the mass floor have write-mass units; rho and the cancellation factor are dimensionless.

3. **Projection and regularization.** The exponential-prior Gram entries and window integrals follow directly by integrating the product kernels against `eta*exp(-eta*x)`. The moment orders needed are zero, one and two; no distinct-pole denominator is required. The stated diagonal scaling yields the objective `E_pi[(f-c^T phi)^2]+rho*||D*c||^2` and the stated coefficient solve. Positive ridge defines a unique mathematical estimator. The stable small-window formulas, independent precision agreement and residual checks are appropriate prospective safeguards. Actual numerical stability, especially for small rho and narrow windows, is deliberately left to the original gates; failure is an allowed outcome.

4. **Targets, counts and failure handling.** Applying identical window coefficients to raw numerator and normalization is internally consistent. Recent-minus-older contrast uses two separately normalized half-open observed-event windows. Continuous projection cannot resolve atomic endpoint membership exactly; the contract correctly treats that discrepancy as approximation error and keeps the event oracle's semantics. Reconstructed mass is signed and can be positive on an empty window. Numerical eligibility therefore cannot stand in for factual support. Epsilon shrinkage, unequal-mass constant-contrast bias, mass-scaling noninvariance and unclipped ratios are disclosed. Every valid scored query retains its loss and frozen fallback on failure; nonfinite state quarantine is preserved.

5. **Resource and method fairness.** Both families retain the same fixed writer, full prescribed grids, eight channels, one-hot K16/V8 and CPU64 9345B allocation. The proposed static factors do not consume new history-dependent state. The analytic array and operation ledger is explicitly partial: copies, library/Python ownership, fallback statistics, setup, serialization, advanced snapshots, failures, reference work and end-to-end ingestion remain chargeable. Equal channel count or equal ridge-grid size is not presented as equal measured tuning cost or compute. The required generic/full-state attribution, gamma equivalence, reader frontiers, learned-writer and modern baseline work remains outstanding. Applying this positive-mass decoder indiscriminately to signed polynomial or nonlinear states is not proposed.

6. **Coordinate equivalence.** Recovering canonical Z/H before the reader preserves both its estimator and its guard. Transforming coefficients and the regularization metric is the equivalent alternative. Imposing a fresh identity ridge after a Laguerre transform would change the estimator, and the proposal expressly forbids claiming that as equivalence. Canonical nonnegative-normalization checks are correctly distinguished from potentially signed transformed channels.

7. **Bounded fixture and development stages.** The 32 declared fixture categories cover the new formula's principal semantic and numerical hazards: boundaries, constants, empty windows, out-of-window leakage, unequal contrast masses, long/tail ages, delay, scale, cancellation and quarantine. The fixed transforms address origin/unit/coordinate/serialization invariance without outcome-driven searching. Independent integral/solve code and direct fixture-event sums prevent a production-helper self-comparison. The 768-fixture and 4608-development prediction ceilings are consistent with the stated inventory. This is sufficient proposed coverage for a narrow forward diagnostic, not a gradient, learned-reader, arbitrary-input or fullstream certification. Reusing exact accepted component evidence is appropriate; repeating prior controls is unnecessary merely to obtain another approval.

8. **Provenance and interpretation.** The draft explicitly requires compatible source/config/data/schema/parameter/cache identities and separately released bounded re-encoding when needed. Epsilon-independent raw tensors do not certify feature-cache or fitted-gate applicability. The candidate's denominator epsilon1e-8 is correctly distinguished from structured epsilon1e-6. A better read would establish achievable same-state performance and constrain an information-loss explanation; it would not isolate MLP optimization, establish universal recovery or prove basis superiority. A failed decoder cannot supply an information-loss lower bound. Development selection remains exploratory and cannot bypass baseline acceptance or protected-data rules.

## Matters that remain unverified and must precede release

These are existing contract requirements, not new research scope or additional design change requests:

- The actual dated adoption decision must cite current structured evidence and justify any departure from waiting for completed structured learning. This review supplies neither that justification nor an adoption decision.
- Before implementation/release at the appropriate stated boundary, resolve the precise fixture values, represented endpoints, transformation constants, expected semantic categories, reference mechanism, numerical-policy details and resource limits. The category table alone is not an executable manifest. Hashes and source seals must bind the resulting reviewed implementation before execution.
- Source review and executed evidence must establish isolation from raw history, all-anchor consumption, snapshot immutability/resumption, schema handling, exact fallback/quarantine behavior, finite-result checks and coordinate recovery. A text contract cannot establish these implementation properties.
- The independent reference must demonstrate precision agreement and original pointwise/coordinate gates, including failure decisions. Any ambiguous threshold case remains unresolved, not a discretionary pass. No fitted or gradient applicability follows from this forward check.
- Actual static/working/resident/serialized bytes, setup and full latency costs remain unknown. Stage B needs a separate bounded release based on Stage A results and measured preparation costs. Compatibility of any reused panel snapshots and their source-bound training constants must be checked against the final candidate identity.

No implementation, additional experiment, protected access or adoption is authorized by these approvals.
