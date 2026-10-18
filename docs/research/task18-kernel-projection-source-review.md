# Independent kernel-projection source review

**SPEC: APPROVED.**

**QUALITY: APPROVED.**

No Critical or Important source defect was found in the reviewed component. No corrective changes are requested. This is source acceptance only; it establishes no Stage A numerical applicability, performance result, Stage B release or completion of Task18.

## Review scope

- Reviewed BASE `53c20803d5cbeca8f40da8d6b59b19f1d4b4a0c7` to HEAD `ff05c9ed2081e2e47ce25988fdcca74841d7e4fe` through the supplied `review-53c2080..ff05c9e.diff`, together with the source brief/report and adopted source-only authority. Read the diff in sequential chunks; recovered a truncated metadata/log excerpt. No changed production file was separately reread in full.
- The production diff is confined to `famjet/readers/kernel_projection.py`, `famjet/models/kernel_read_model.py` and the narrow registration/input-boundary changes in `famjet/eval/isolation.py`. No trainer, cache policy, source-compatibility rule, dependency or existing memory-kernel modification appears in the diff. Exact whole-package/lock/memory hash verification was supplied by root; this review did not independently rerun it.
- Used the supplied task-reviewer template. No subagents, Git operations, source edits, scripts, tests, calculations, models, data, protected access or Stage A execution were performed. This ignored review is the only edit.

## Spec compliance and strengths

1. **Canonical mathematics is implemented faithfully.** `famjet/readers/kernel_projection.py:30` and `:55` implement lower-endpoint shifted positive integrals, a convergent small-product series and a bounded-tail branch. `:94` constructs diagonal-scaled Gram factors and a positive-ridge spectral solve; the Gram expression includes both dimensionless Jet moment factors. `:137` validates layouts, finite values, canonical channel pairing, factor relationships, orthogonality and residuals. Negative computed eigenvalues are rejected without clamping; the rejection retains sign/residual/condition diagnostics through `FactorApplicabilityError` at `:78`. `:178` solves in the prescribed scaled coordinates and checks the solve residual. These checks do not claim the deferred independent pointwise campaign has passed.

2. **Counts, ratios and failures retain their intended meaning.** `famjet/readers/kernel_projection.py:188` applies the same coefficients to canonical numerator and normalization channels, with compensated reductions, the fixed floor and cancellation guard, epsilon shrinkage and finite-result checks. It does not clip mass or predictions. `famjet/models/kernel_read_model.py:118` preserves Jet channel interleaving and computes recent and older windows separately before subtracting their ratios. `:113` initializes active queries with the frozen task fallback; `:137` retains failure flags. `:138` exposes unavailable factual support as NaN with an explicit availability flag, separately from numerical eligibility. Nonfinite saved state is identified across the numerical payload at `:103`; it stays unmodified and therefore remains quarantined on subsequent reads.

3. **The wrapper preserves the fixed state and read boundary.** `famjet/models/kernel_read_model.py:31` restricts the production wrapper to fixed CPU64 Jet4/Bank8, K16/V8, the prescribed full-grid shape and prior/time-unit ratio. The more general small-basis arithmetic constructor is used for analytic controls rather than registered as an alternative production family. `:69` leaves snapshot identity as the writer/rate hash; `:72` delegates initialization, encoding, advance-copy and persistent bytes to the existing kernels. `:88` rejects hidden query fields, validates query/history identities and tasks, and uses independent temporary advanced payloads without updating the supplied snapshot. No history-conditioned factor, coefficient or query cache is retained.

4. **Closed static reconstruction is substantive.** `famjet/eval/isolation.py:100` reconstructs only the declared kernel-projection schema and arrays; `:190` exports exact array records and frozen policy/statistics. `KernelProjection.from_statics` at `famjet/readers/kernel_projection.py:161` imports the supplied array values rather than rerunning eigendecomposition. `KernelReadModel.from_statics` at `famjet/models/kernel_read_model.py:57` checks the reader/kernel relationship, while `:47` binds frozen fallback metadata to writer and reference time. Existing constructor-tree comparison, confirmed in the narrowly inspected continuation of `isolation.py:235`, rejects hidden fields, hooks and undeclared buffers. Whole-method identity includes the exported reader and policy; writer identity remains separate.

5. **Ownership accounting distinguishes its limits.** `famjet/models/kernel_read_model.py:143` first validates the closed export, then accounts reachable Python objects and deduplicated full tensor stores separately from serialized bytes. The ledger explicitly excludes process/allocator/library memory and does not call its delay-copy figure a dynamic peak bound. The source report preserves temporary-copy overlap and output/workspace costs as unmeasured execution obligations. No dummy parameters or additional persistent history allocation is introduced.

6. **Tests exercise behavior and meaningful faults.** `tests/test_kernel_projection.py:15` and `:28` use simple independent closed-form controls; `:71` uses an independent Decimal defining solve for the canonical ridge metric. The tests cover adjacent represented endpoints, tail behavior, a reached cancellation failure, fixed-epsilon noninvariance and rejected-factor diagnostics. `tests/test_kernel_read_isolation.py:44` checks two separately normalized contrast windows, query order and saved-state immutability; `:85` checks exact static records and clean-worker results; `:98` and `:133` reject hidden model/query ownership. The retained Gram-factor and cancellation-guard mutation logs demonstrate substantive RED sensitivity beyond missing-import failures.

## Focused delegated checks

These were the only outside-diff investigations; they addressed named dependencies rather than broadening the review:

- **Risk: wrapper delegation might omit snapshot identity, dtype or layout checks.** Inspected `famjet/eval/state_io.py:82` and the relevant `SnapshotMemory` validation/persistent-byte sections in `famjet/memory/_fixed_writer.py:136` and `:247`. They reject extra snapshot attributes/payload fields and mismatched writer identity/layout while intentionally allowing numerical NaN/Inf payload evidence. The wrapper invokes both validation layers.
- **Risk: delayed reads might mutate or reverse the saved state.** Inspected `famjet/memory/_fixed_writer.py:213`. It checks causal gaps, clones payloads and returns propagated temporary data; the wrapper does not assign that payload back to the snapshot.
- **Risk: existing public-field validation might carry undeclared metadata or silently alter key/time semantics.** Inspected `famjet/data/schema.py:124` and the raw fixed-writer input adapter at `famjet/memory/_fixed_writer.py:66`. Public features are validated as finite nonnegative vectors; the existing writer remains generic. Exact one-hot/gate-one fixture content is a property of the separately sealed Stage A inputs, not inferred from a K16 tensor shape. No scientific input inventory was inspected or certified here.
- **Risk: new export could silently discard hidden state or fail to bind fallback buffers.** The diff cut off `export_method` before its shared constructor-tree audit. Inspected that necessary continuation and `_tree` at `famjet/eval/isolation.py:60`. Comparison includes instance fields and reconstructed buffers; unknown ownership cannot be stripped into an apparently equivalent export. Also checked the closed field names/deep-copy return of the delegated training metadata validator in `famjet/models/_schema.py:57` for the frozen-statistics ownership claim.

## Evidence and issues

- **Critical:** none found.
- **Important:** none found.
- **Minor:** no actionable code-quality finding is requested.
- The supplied covering log records **74 passed, 1 skipped in13.22s**; the later narrow rejected-factor follow-up records **28 passed in2.16s**. The covering result precedes that small follow-up and is not represented as a fresh full covering run of HEAD. The preserved single skip is the existing unavailable-MPS budget control. No unexplained warning was found in the final supplied logs.
- The interrupted overbroad selection is explicitly preserved as **45 passed followed by KeyboardInterrupt**, not an all-green suite result. Its disclosed scope/expenditure and raw pytest whitespace preservation remain part of the record; they are not evidence of scientific Stage A execution or a reason to rerun tests here.
- Static bytes remain exact in the round-trip tests. Changing only the direct/worker floating-result assertion from exact equality to the pre-existing1e-12 arithmetic gate does not relax static identity or the adopted numerical tolerance.

## Cannot verify from this source review

The actual production rate bits and fallback provenance/export, source-bound fixture inputs, full32-row/four-realization inventory, independent80/160 reference agreement, ordinary source fidelity and strict end-to-end applicability, branch coverage on the scientific fixtures, measured runtime/RSS/transient/serialization peaks, host/resource seals and bounded execution orchestration remain pending. Unit tests and internal residual checks do not fill those fields. The corrected F1 three-way result attribution belongs to the later reviewed reference/execution layer; no such campaign or driver is claimed in this source component.

Source acceptance therefore leaves all separately gated execution and interpretation requirements intact, including retention of source/end-to-end failures and prohibition of a global Stage A PASS or automatic panel access based only on reader checks.
