# Task19 independent SPEC + CODEQUALITY review

18 October 2026. Reviewed immutable BASE `6bed0cd17e853c135a570682b5931a1e89d11f0d` → HEAD `e74b1971310189cb504f67534c6ed33d7684c81a`; implementation `3613d023547b8c406947c1353c786685ab52fa5f`; package source identity `d2b687aa6db4cff585044503cd200f3dfb2181f3da3803c9bf556b9156d3aa47`. HEAD was checked. No source, tests, git state or scientific artifacts were edited; this ignored report is the sole written artifact. No delegation, scientific simulation, model/corpus preparation, calibration allocation or suite rerun occurred.

**SPEC verdict: CHANGES REQUIRED for the analysis component.** The resampling and nominal inference implementation meets the reviewed mathematical requirements, but four concrete preflight/permission defects violate the fail-closed contract. These findings do not require changing the statistical method or choosing scientific thresholds.

**CODEQUALITY verdict: CHANGES REQUIRED.** The existing deterministic tests and retained RED/GREEN evidence are meaningful. However, the permission returned to a controller is inconsistent with test-only scope, and several known-invalid preanalysis configurations pass their intended boundary. Add focused regression coverage while repairing those paths; a scientific campaign is neither needed nor authorized for these fixes.

## Findings

### 1. P1 — Test-only analysis can export scientific confirmation permission

**Location:** `famjet/analysis/statistics.py:473–479`, particularly the assignment at 473 and the local-only test-mode restriction at 474. Related contract: `docs/statistical-protocol.md:56` and Task19's explicit test-only software boundary.

`report['gate']` is the unrestricted result of `evaluate_gate`. `not m['test_only']` is applied only to the local `allowed` variable, so it correctly suppresses final strong-claim booleans but does not suppress `report['gate']['confirmation_allowed']` or change `gate.eligibility`. A controller consuming the documented permission field can therefore receive authorization from a software-only fixture. Likewise, the returned nuisance permission has no test-only restriction.

**Focused reproduction:** combine the existing `analysis_case` software fixture and `artificial_gate_case` artificial count fixture. Preserve `test_only=True` and the test-only release. Rebind the artificial policy/records to the fixture's scope and actual package source, recompute their policy hashes, supply source-bound implementation/resource/baseline/domain acceptance and an explicit software-only p-MC budget `.1`, and run the existing analyzer. All fixture and output I/O was intercepted in memory using `Path` mocks and `BytesIO`; actual scorer, aggregation, crossed resampling and gate code executed. Observed:

```text
status = analyzed_test_only
gate.calibration = qualified
gate.endpoint_mc = ['met', 'met']
gate.secondary_p_mc = adequate
gate.eligibility = eligible
gate.confirmation_allowed = True
strong_primary_rejection = False
strong_secondary_rejections = {'secondary': False}
```

The invented counts remain software controls, not qualification evidence. The defect is the exported permission, not a claim that this invocation produced scientific significance. Enforce test-only scope in the returned permission object itself, including both confirmation and nuisance permissions, while retaining diagnostic calibration/MC results separately. Regression coverage must exercise an otherwise-passing test-only gate; the existing unfilled-policy test cannot detect this case.

### 2. P1 — Scientific preflight accepts an unchosen p-MC budget for a nonempty secondary family

**Location:** `famjet/analysis/statistics.py:372–373` and `403–407`, followed by score parsing at `426`. Binding requirement: spec §10's rejection of null scientific fields before opening protected output; the dated amendment's prospective freezing of the MC error budget.

The budget is validated only when non-null. The scientific preflight then checks calibration/source/resources/baselines/domain but does not require a conditional p-MC budget when secondary comparisons are declared. Consequently a manifest can reach protected score parsing with a nonempty Holm family and `p_mc_error_budget=None`. The later p guard correctly reports `not_assessed` and withholds strong claims, but this is too late to enforce the preobservable configuration requirement.

**Focused reproduction:** reuse the existing software fixture with one primary and one secondary comparison, source/scope-bound artificial qualified calibration counts and explicit design acceptance. Set the manifest's mode to `protected_confirmation`, provide matching `legitimate` release metadata with `task21_unblind_v1`, and retain `p_mc_error_budget=None`. Calling the actual `_contract` returned normally. The evidence supplied neither `endpoint_mc` nor `secondary_p_mc`; its output was:

```text
SCIENTIFIC_PREFLIGHT_ACCEPTS_NULL_P_BUDGET True secondary_count 1
ACTUAL_POSTANALYSIS_MC_NOT_SUPPLIED True
```

This was entirely in-memory administrative/software evidence, not actual protected data or a scientific release. Require an explicitly frozen valid budget before parsing scientific scores **when the secondary family is nonempty**. Do not invent a default or require future endpoint/p-MC outcomes. A primary-only manifest does not need a secondary p-MC budget merely to satisfy this finding.

### 3. P2 — Empty calibration provenance identifiers can qualify

**Location:** `famjet/analysis/statistics.py:210–220` and `245–248`. Related contract: `docs/statistical-protocol.md:60–62` and the review brief's explicit requirement that missing/empty required calibration fields cannot qualify.

The missing-field check rejects only `None`, and stream validation only compares selection and validation identifiers for inequality. An empty selection stream with a nonempty validation stream passes; an empty validation stream also passes when retained records carry the same empty `rng_stream`. This accepts evidence with no identifiable selection or fresh-validation stream. The standalone `evaluate_gate` also accepts empty scope/source identities when the policy and records agree; `_contract` independently protects those latter two identities, but does not repair the stream gap.

**Focused reproduction:** start from `artificial_gate_case()`. For each named field separately set `p[field]=''`; update the matching evidence field/record stream where applicable and recompute every record's `policy_hash`. Four direct gate calls returned:

```text
selection_stream qualified True []
validation_stream qualified True []
scope_id qualified True []
source_hash qualified True []
```

Columns are field, calibration, confirmation_allowed, unresolved_reasons. No datasets or resampling were generated. Validate nonempty, properly typed provenance identifiers before comparing them, preserve distinct selection/validation streams, and add matching-empty-evidence tests. Do not treat hash agreement over an empty identifier as the missing provenance itself.

### 4. P2 — A positive-weight regime with no declared units passes preparse inventory validation

**Location:** `famjet/analysis/statistics.py:336–351`; score parsing occurs at `426`. The existing later check is `famjet/eval/metrics.py:291` (`incomplete regime inventory`).

`_weights` is called using the keys of `regime_weights` as its own supplied stratum inventory, so it validates normalization but cannot detect a missing regime. Each expected cell is checked for membership in those keys, but the reverse condition is absent. A complete Cartesian matrix containing only regime `r`, paired with frozen positive weights `{'r': .5, 'absent': .5}`, passes `_contract`. The metrics validator rejects it only after parsing scores. This violates the stated complete-manifest preflight boundary even though final inference ultimately fails closed.

**Focused reproduction:** mutate only the existing software fixture's regime weights to the above two-regime mapping, reseal the manifest/release, replace score content with `invalid unopened score JSON`, and update the release's byte hash. The analyzer returned:

```text
status = blocked
errors = [{'type': 'JSONDecodeError',
           'message': 'Expecting value: line 1 column 1 (char 0)'}]
```

The JSON decoding error demonstrates that preflight accepted the incomplete declared regime inventory and attempted score parsing. The check should compare declared inventory/unit strata against frozen weight keys before reading scores. Preserve the downstream metric check as defense in depth. Add an invalid-score sentinel regression for this absent-regime case, alongside the existing missing-cell/query preflight controls.

## Mathematical and control review

No defect was found in the reviewed independently stratified history counts, single shared paired-seed count vector, Cartesian normalization, fixed equal-default/explicit weights, per-stratum centering and power-of-two scaling. The independent repeated-index oracle checks duplicate selections. Real stations are averaged within declared clusters before the one cluster resample; duplicated query controls preserve the independent-unit matrix.

The primary interval uses explicit linear .025/.975 quantiles. The centered absolute-null exceedance test uses the same resamples and the observed weighted mean, retains ties and the plus-one convention, and Holm retains point values/adjustments/step-down decisions. Endpoint stages begin at 2000 in four batches and double through 128000; endpoint SE uses sample SD divided by two, with the strict 1%-of-pooled-width condition. Exact all-zero A/A alone gets the automatic degenerate exception. Conditional p bounds spend across seven stages and the frozen family, without p-driven additional resampling. Missing/ambiguous p precision is kept separate from nominal decisions.

The specific suspected **circular dependence on future protected endpoint/p-MC outcomes is absent**. At lines 402–407, preflight reads the calibration component and explicit source/resource/baseline/domain acceptance, not preliminary `confirmation_allowed`. Actual endpoint/p precision is supplied after analysis at 471–472. Finding 2 concerns a known configuration parameter, not those future outcomes. Do not repair it by requiring future MC success before parsing.

Expected paired runs, successful release records, declared Cartesian/query inventory, source identity, frozen statistics content, file hashes and release byte/hash commitments otherwise have substantive preparse checks. The actual v2 scorer/aggregation/pairing validators are reused. All methods participate in a declared comparison, one primary is required, and secondary/exploratory roles remain distinct.

## Evidence and scope

Read the implementation release, original brief, handoff, design reconnaissance, root rulings, binding plan Task19/spec §10, implementation report, protocol, amendment and next-allocation proposal. Read the focused diff once in successive ranges; the first large tool response truncated some documentation prose, which was recovered from the corresponding source documents rather than rereading the diff. It includes all new source/tests/protocol and actual retained test logs. The nine omitted historical promotions were covered by the included exact SHA/byte inventory and root's independently verified byte equivalence; no historical reconnaissance was rerun or upgraded to production qualification.

Inspected the actual retained RED/GREEN, failed-expectation, audit, release-order, implementation-status and matrix-preflight logs, plus their source/log identity inventory. Final retained evidence is **77 passed in 1.53s**, statistics/metrics/harness. The earlier **103 passed, 1 MPS-unavailable skip in 53.23s** precedes the narrow administrative fixes and is not represented here as a final-source full-suite result. The meaningful prior RED cases and corrected mistaken Holm test expectation are retained transparently.

Reviewer execution was limited to three short focused Python invocations: direct artificial gate mutations; an in-memory test-only analyzer and absent-regime preflight probe; and an in-memory scientific-mode contract probe with wholly artificial evidence. `PYTHONDONTWRITEBYTECODE=1` was used. No fixture/output files were written to disk; no production code was mocked in the statistical/gate paths, only filesystem operations for these probes. No new tolerances were selected for science. Their exact observed outputs are recorded above.

**Scientific status remains unchanged:** Task19 scientific calibration OPEN/not run; thresholds, domain, outer N and scientific error budgets remain unchosen. Earlier scarce-seed undercoverage remains failed exploratory evidence. Task18 science remains OPEN with the original epsilon numerical gate FAILED. Protected confirmation/replication remain CLOSED. Source-component repair/review cannot accept a neural family, authorize the proposed resource profile, launch nuisance work or complete scientific Task19.
