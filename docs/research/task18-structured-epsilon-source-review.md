# Task18 structured epsilon source review

Reviewed immutable BASE `8494fda1b336908e64ab7f966b0a247ebfaa9371` → HEAD `6bed0cd17e853c135a570682b5931a1e89d11f0d`, including source commit `562abb4` and the metadata-only log-hash clarification. Package `d8043d2eeb938980ca34eafb33286711e7d0609a5311ca454a5d9a0e975b2f29`. Authority: the scoped review/source briefs, including root's explicitly authorized dependency expansion after actual RED evidence. Unrelated concurrent Task19 work is outside this review.

**SPEC COMPLIANCE: APPROVED for the bounded source stage.**

**CODE QUALITY: APPROVED. No blocking or nonblocking findings.**

This is source eligibility only. The original epsilon1e−8 numerical gate remains FAILED; no external numerical, preparation, cold-profile or scientific execution is released, and wholeTask18 acceptance remains OPEN.

## Policy boundary

`fixed_basis_cpu64` computes the exact existing structured Jet125/Bank122 shape and allows epsilon1e−6 only inside that alternative. Epsilon1e−8 remains allowed. The shared CPU64/fixed-writer/terminal/one-hot16×8/head1/support-floor1e−8/no-abstention/two-layer/no-rank/no-budget-override conditions still surround both alternatives; later family checks retain Jet4/Bank8 and fixed full log bounds1/5224..1. Generic-contracted raw128 and multiscale remain limited to the old read epsilon; epsilon1e−10, other widths, learned parameters, FP32 and MPS64 gain no permission. Data/calibration/LR/resource conditions remain in unchanged policy code.

Reference: `famjet/analysis/development.py:114` at the pinned review HEAD.

## Demonstrated read-policy identity dependency

The second production change addresses the actual RED-reproduced omission. `feature_identity` first rejects a Jet/Bank model whose actual `kernel.eps` or `kernel.support_floor` differs from the supplied config. Version2 then records those actual values in `read_policy`, independently of writer/state hashes and fitted feature arrays. The existing source/lock/raw-manifest/schema/statistics/fit/dtype/device/encode fields remain. Multiscale records an empty normalization read policy; its distinct basis epsilon remains in its existing basis identity. There is no historical manifest migration or compatibility fallback.

The ordering is correct: preparation obtains this identity before creating/loading the raw cache; `TrainingFeatureCache` compares the complete manifest identity before constructing `TrainingDrawCache`, reading feature payloads or calling `torch.load`. Parsing the small manifest itself precedes that comparison, which is consistent with the requested boundary. Version1 identities cannot compare equal to version2 even if an old manifest's outer hash is supplied. The writer/state hash correctly remains epsilon-independent: epsilon changes read features, not stored recurrence state.

References: `famjet/data/feature_cache.py:28`, `:39`, `:53`, `:86`, `:130` at the pinned review HEAD.

The tests distinguish three important cases: actual kernel/config mismatch; different read maps with exactly the same fitted arrays and writer hash; and a real generated epsilon1e−8 feature manifest supplied to an epsilon1e−6 model/config. The latter mocks both raw-cache construction and tensor loading to fail if reached, so its expected identity rejection demonstrates the required ordering rather than merely a later shape failure. A support-floor mismatch is also rejected. The synthetic empty-manifest test is supplemented by this real-manifest test and is not the sole evidence.

References: `tests/test_fixed_structured_development.py:94`; `tests/test_fixed_basis_development.py:88`.

## Lifecycle and regression evidence

Both epsilon values are covered by the real FP64 fit/export/reconstruction/prediction/gradient-path tests. Reconstruction explicitly retains epsilon, predictions are exactly equal, state remains9345B, and literal resource checks retain Jet30134parameters/29875MAC and Bank30021/29768 with zero padding. Active-parameter counts remain upper bounds. A separate calibration test binds epsilon through `execution_shape` and rejects epsilon1e−8 evidence for epsilon1e−6 before model allocation.

The existing bounded two-pass raw/cache training test includes both new family/epsilon combinations. It compares actual model and AdamW state, predictions, sampler/draw identity and interrupted/resumed trajectory, with FP64 moments and FP32 counters; existing replay/dtype/upstream identity checks remain. This demonstrates the implementation's gradient path and lifecycle, not the later independent full numerical comparison at original1e−12 or scientifically fitted conditioning.

References: `tests/test_fixed_structured_development.py:53`, `:132`; `tests/test_fixed_basis_development.py:88`.

Read the retained actual log outcomes: RED6fail/8pass in5.78s, including the two `DID NOT RAISE` identity failures; focused GREEN27pass in26.62s; native covering89pass in26.99s, with no reported skips/failures. Independently verified the four source/test hashes from the pinned commit against the verification record and all raw/promoted log hashes. RED promotion equals precisely line-ending-preserving trailing-whitespace removal; raw bytes/hash remain retained. GREEN and covering logs are byte-identical. The6bed clarification changes provenance metadata only. No test rerun was necessary.

Reference: `docs/research/task18-structured-epsilon-source-verification.json:1` and its linked logs.

## Claim and execution limits

The dated amendment and source report correctly separate this candidate setting from numerical acceptance. The one-coordinate old-weight epsilon counterfactual does not repair the failed original checkpoint, justify reuse of its fitted feature statistics, establish a complete frontier, or authorize a reader-only waiver. Future work requires separately released fresh epsilon-specific feature fits/caches, source-bound raw provenance, unchanged common768 target/t_ref and96 development panel, applicable calibration and the original full numerical gates under201326592B. The cache identity tests' intentionally mutated models are adversarial fixtures, not a scientific reuse procedure.

References: `docs/research/task18-structured-epsilon-source-report.md:3`, `:21`; `docs/amendments/2026-10-18-structured-numerical-stop-and-epsilon-proposal.md` final source-only ruling.

The supplied diff was read once; truncated predicate context and the existing cache-construction ordering were inspected from the pinned HEAD. No models, experiments, suites, full cache scans, source edits, Git mutations or subagents were used. Only this requested review report was written.
