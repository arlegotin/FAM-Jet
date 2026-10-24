# E1 independent SPEC + QUALITY review — 24 October 2026

**SPEC: NO. QUALITY: NEEDS FIXES. HOLD.**

Scope: E1 source and evidence only, BASE `9d278c703b4f086b745a73000838e04b6b87768f` → `9fff82a98bacfb29b95f8fff5ca3e2229749022f`. I read the supplied full diff once, the E1 brief/report, exact model/data contract, and adopted completion-design rulings. Targeted frozen-core reads were limited to named validation, writer, target-statistics, and Beijing interfaces used by this change. No source, tests, models, data, Git state, or experiments were changed; this report is the only review output.

## Strengths

The implementation expresses the specified 33-component feature map and q8/q16 outer products with one 264/528-entry coefficient vector shared across coordinates. Jet4/Bank8 use native CPU64 fixed writers. Snapshot identity excludes reader updates; reads advance copies and consume snapshot/public queries without retained histories. Fit weights account for regime, individual history, task, eligible query and coordinate, including batched histories. Replay passes bind ordered event/query/label digests and verify training statistics before committing reader updates.

The qualification helper specifies all eight shape/family/width cases, fit and fresh per-task/key MSE gates, independent augmented least squares and two-age reconstruction. Its fixed `t_ref=1` exception is explicitly documented despite the fixture's positive-gap median being 2. The source does not claim measured qualification. Golden exploratory parity, guarded synthetic generation, current-v2 Beijing replay, contrast unit inversion, numeric NPZ storage, and lightweight imports are useful coverage.

## Critical

None found in this scoped source review.

## Important

1. **Loaded fit provenance is not strictly validated or reconciled with the model.** `famjet_poc/models.py:519`–527 checks the outer `FitArtifact` field set, nested source/writer hashes, numeric arrays and target-statistics equality. It does not validate the exact field set of `fit.manifest`, nor reconcile its reader configuration, shape, `t_ref`, statistics hash, lock hash, data/row digest relationships, or history inventory. For example, changing only `fit.manifest.reader.ridge`, adding an unknown nested manifest field, or replacing `row_sha256` while leaving arrays unchanged passes the implemented checks when the caller supplies the new manifest SHA. This is a schema/provenance consistency failure, not a claim that hashes can be bypassed. `fit_reader` rejects these inconsistencies, but `load_model` admits them and presents the artifact as verified. The task explicitly requires strict statics/unknown-field rejection and binding row inventory/scalers/priors/writer/config/source/shape. Factor the applicable manifest validation into loading, reconcile duplicated commitments, and validate finite, successful fit diagnostics and their types. Add focused malformed-artifact checks without rerunning scientific qualification.

2. **The fit memory ledger does not account for actual logical allocations required by the contract.** `famjet_poc/models.py:425`–428 records Gram, RHS, one nominal design chunk and static arrays only. `models.py:410` additionally allocates the full normal matrix and an identity temporary; `models.py:388`–389 stacks buffered feature vectors into another X and creates a weighted X temporary. `models.py:318` materializes per-episode raw query features, and `models.py:421` retains duplicate coefficient/scaler values in the fitted artifact. These are absent from the ledger, as are solver workspace and query-buffer categories. Thus `max_design_chunk_bytes` is not a peak chunk-working allocation and the ledger cannot support the promised all-bytes accounting. Record separately the bounded buffers and simultaneous copies actually used, distinguish logical payload from Python overhead, and mark opaque solver workspace explicitly unknown pending measurement. RSS may remain explicitly unmeasured at this source stage; do not substitute this ledger for later measured admission.

## Minor

The qualification helper aborts on a fit/read/reference exception before writing `qualification.json` (`famjet_poc/models.py:635`, `models.py:644`, `models.py:668`). Earlier completed cases exist only as model files, without the consolidated result or an explicit failed-case record. Persist progress and exception status when the later qualification runner enters this helper, so a numerical failure remains auditable. This observation does not establish that any case fails.

## Verification and limits

The supplied final evidence records 15 passing focused tests, successful compilation and a Torch-free contracts import. Root reports independently validating the three byte-preserved invocations, all 14 new Git paths, 75 inventory entries, and frozen-core/Stage-A/lock/B88 custody in `e2e-task-1-root-proof.json`. Early invocation/failure metadata is explicitly recovered/transcript-only; original early output bytes are not independently reproducible evidence. I did not rerun tests to reconstruct them.

I cannot verify actual eight-case qualification, resource peaks, real training availability, or protected/statistical outcomes: none was entered here. Real training's requirement for both eligible tasks per history is correctly enforced; availability must be checked before actual fitting. No inference about real-data eligibility follows from the tiny loader fixture. Findings above arise from the submitted source, not speculative qualification results.
