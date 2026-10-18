# Independent scoped fixture-manifest review — 18 October 2026

**Contract/spec compliance: APPROVED.**

**Technical quality: CHANGES_REQUIRED.**

One narrow, load-bearing acceptance/attribution ambiguity requires resolution before adopting the concrete manifest. No change to the reader mathematics, fixture values, numerical tolerances or experiment scope is requested. Neither verdict authorizes adoption, implementation or execution.

Reviewed only the new `.superpowers/sdd/2026-10-16-famjet/task-18-kernel-reader-fixture-manifest-draft.md` against the previously reviewed proposal and applicable specification. No scripts, calculations, tests, fixture generation, source edits, Git changes, data/model/protected access or performance work was performed. This ignored report is the only edit. The current structured learning pair is running according to the review brief; no result is inferred.

## Required correction

**F1 — Medium: explicitly separate stored-state reader correctness from source-state/end-to-end failure.**

**Path:** `.superpowers/sdd/2026-10-16-famjet/task-18-kernel-reader-fixture-manifest-draft.md`, row30; “Independent reference and decision gates,” especially “FP64-versus160 comparisons”; and “Fixed setup, execution/timing inventory,” especially “A candidate numerical mismatch stops that candidate.”

The two references are correctly distinguished in purpose, and their different eligibility decisions already have an explicit end-to-end classification. The corresponding acceptance rule for different *finite numerical values with matching eligibility decisions* is not explicit. It is unclear whether a mismatch against the direct-event reference constitutes reader-arithmetic failure, an upstream state discrepancy, or both. The generic candidate-mismatch stop rule does not resolve this attribution.

This matters for the fixed row30, independently of any measured outcome. Its chronological writes place a small `E(2,P)` before two equal-time writes with values `+2^500*S` and `-2^500*S`. A streaming FP64 addition can absorb the existing small numerator into the first large write; the second cancels the large contribution without restoring the absorbed value. The independently ordered event sum intentionally cancels the large pair before accumulating the small contribution. Moment propagation also depends on the intervening represented Z. Thus a correct decoder of the supplied snapshot need not agree with a decoder of independently summed event kernels. This is an anticipated source-state stress, not evidence by itself of faulty integral evaluation, factorization or contraction. No execution or quantitative claim about the six candidates is made here.

**Precise remedy:** add an acceptance matrix using the already planned comparisons and preserve every original tolerance:

- Production versus reference (a), on the exact represented supplied snapshot, determines reader-arithmetic correctness, including its independently derived failure decision.
- Reference (a) versus reference (b), with the named scale/delay/coordinate provenance, determines whether source-state representation/encoding changes the declared end-to-end decoder result or eligibility.
- Production versus reference (b) remains the strict end-to-end check. A source-state discrepancy must retain a distinct failure category and must not turn a passing stored-state reader check into a reported reader-arithmetic failure.
- State explicitly how each outcome gates the candidate and subsequent slots. Keeping a strict overall end-to-end rejection and the existing stop policy is acceptable; in that case preserve the passing isolated-reader result and the upstream failure cause. A reference-precision failure remains separate from either. The same classification must apply when finite outputs differ but eligibility decisions agree.

Do not repair row30, replace the sum order, clip values, relax tolerances, add trials or silently exempt it after observing results. This correction is about prospective diagnostic meaning and acceptance, not making a candidate pass.

## Checks that support approval of the remaining contract

- **Fixture semantics:** The declared included/excluded boundary neighbors and adjacent windows have consistent observed-event semantics. Rows21–24 separate long span, narrow-window, beyond-prior-scale and delayed-read behavior. The no-write marker adds no observed mass. Rows08/26/27 clearly identify algebraic mass injections rather than representing them as new gate-one population histories. Row32 is explicitly a nonfinite snapshot sentinel, not an event or finite-equivalence test.
- **Represented-time transforms:** The specified origin-shift exclusions address the boundary-neighbor ages that cannot survive that shift exactly. Remaining rational-difference checks correctly fail the manifest rather than search for another shift. Unit scaling includes physical rates, prior scale and reference time; reuse of unchanged dimensionless factors is mathematically valid. Canonical recovery for Jet and exact serialization for Bank are appropriate distinct representation checks. Preserving O/U numerical snapshots makes these reader/metadata checks, not independent transformed-writer certifications, as the draft states.
- **Reference independence and precision:** Exact represented-input conversion, separate Decimal80/160 integral evaluation, independent pivoted solve, deterministic magnitude-ordered sums, precision agreement and residual gates are coherent for these fixed fixtures. The paired huge values in row30 have identical ages and opposing values, so the prescribed summation rule directly addresses reference cancellation. The reference still requires implementation review and executed precision evidence; 80/160 is a proposed mechanism, not a proven certificate.
- **Guards and failures:** The ordered floor-before-cancellation decision prevents an irrelevant cancellation margin from making complete decay ambiguous. Known structural zero failures and nonfinite-policy handling are appropriately distinguished. Separate contrast-window guards, result finiteness, original tolerances and frozen fallbacks are preserved. Row29 is a predetermined cancellation stress; its definition does not guarantee that the cancellation rejection branch will execute. Reports must therefore state actual branch coverage without treating absence of that outcome as either proof of coverage or permission for an extra search.
- **Timing and counts:** Folding all production reads into the four realization slots resolves the previous ambiguity about profiling reads beyond the fixture ceiling. Nonapplicable or stopped slots are not replaced. Sparse heterogeneous groups cannot establish stable throughput or tail-latency comparisons, and the manifest explicitly limits those claims. Cost attribution must follow actual setup/encoding/reuse boundaries rather than imply that each candidate repeats identical cold construction.
- **Resource and authority boundaries:** The proposed finite wall-time, candidate, memory, disk and thread limits are stop budgets, not asserted measured feasibility. Candidate versus common prerequisite failures have explicit stopping rules. Null source/runtime/rate/fallback/resource seals properly block execution; they are not defects in a prospective design review. They must be resolved by the stated later reviews, not borrowed from the concurrent structured run.

## Verification limits

This review cannot establish actual rate bits, fixture construction, state-error magnitude, guard branch coverage, Decimal80/160 agreement, spectral stability, worker isolation, fallback/quarantine transport, transform round trips, ownership/resumption, total reads, source/cache compatibility, resource feasibility or any accuracy/speed result. Those require the explicitly gated implementation and evidence. In particular, the extreme finite fixture may legitimately reject candidates under a strict end-to-end policy; that possibility must remain visible and accurately attributed.

The unchanged broader design and outstanding reader/baseline/convergence obligations were not re-reviewed. No Stage B, protected access or additional experimental allocation is implied.
