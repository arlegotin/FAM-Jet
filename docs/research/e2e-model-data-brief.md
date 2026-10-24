# Model/data implementation contract — 24 October 2026

Root implementation proposal, requiring its dated adoption record. Preserve all historical source pins and failed MLP/statistical statuses. Implement only new `famjet_poc/{contracts,data,models}.py` and tests; independently author extensions, importing existing core APIs rather than vendoring external code. CPU float64 throughout. No experiments were performed for this brief.

## Public interfaces and schemas

Frozen dataclasses reject unknown fields and serialize to canonical finite JSON:

```python
ShapeSpec(key_dim: int, value_dim: int)  # admitted: (16,8), (12,1)
PopulationSpec(version, shape, namespace, seed, lengths,
               regimes, queries_per_history, max_query_attempts)
AccessGrant(manifest_path, manifest_sha256, phase, split)
ReaderSpec(version, family, query_width, ridge, alpha_min,
           alpha_max, epsilon, support_floor)

generate_episode(spec: PopulationSpec, episode_id: str,
                 *, grant: AccessGrant | None = None) -> Episode
iter_beijing(manifest: Path, split: str,
             *, grant: AccessGrant | None = None) -> Iterator[Episode]
build_model(shape: ShapeSpec, spec: ReaderSpec, t_ref: float,
            target_statistics: dict) -> RidgeMemoryModel
fit_reader(model, episodes: Iterable[Episode], fit_manifest: dict,
           *, chunk_rows: int = 1024) -> FitArtifact
load_model(artifact: Path, expected_sha256: str) -> RidgeMemoryModel
```

`RidgeMemoryModel` implements existing `init_state`, `encode`, `advance_copy`, `read`, `persistent_nbytes`, `parameter_nbytes`; exposes frozen `target_statistics`. Return existing `Snapshot`/`ReadResult` types, including prediction validity, numerical support and failure diagnostics expected by `score_episode`. Read receives only snapshot and public queries. Writer identity binds shape/rates/time units; artifact identity additionally binds reader/scalers.

`FitArtifact` records schema/source/lock/data/config hashes, ordered training-row digest/count, shapes, target statistics, t_ref, rates, coefficients, feature means/scales, objective/residual, solver diagnostics, training time, memory ledger and failure status. Save tensors without pickle-dependent executable reconstruction; JSON manifest hashes every array.

## Exact feature map and solve

Use existing fixed `JetMemory`/`ExpBankMemory`, same events, raw values, one-hot keys and gate1. Jet has four log-spaced positive rates; Bank eight over identical endpoints. At query T advance a copy, contract the requested key, and form numerator vector `u_v∈R8` and nonnegative mass `m∈R8`: Jet ordering `[Z0..Z3,H0..H3]`, Bank all eight Z coordinates. No history/elapsed-span side channel.

For each value coordinate v define33 components:

`f_v = [1, u_v, u_v/(m+eps), log1p(m), 1[m>floor]]`.

Use eps=1e−6 and floor=1e−12. Retain raw amplitudes. Negative/nonfinite masses trigger explicit failure, not clamping. Standardize the32 nonconstant components using training-only pooled query/coordinate means and population SD; zero SD maps to scale1 without deleting columns. Training constants may vary later, so preserve their transform.

Let `x=log1p(a/t_ref)`, `y=log1p((b−a)/t_ref)`, `c=1[task==contrast]`. The continuous endpoint/task basis is:

`q8=[1,x,y,x*y,x*x,y*y,c,c*x]`.

`q16=q8+[c*y,c*x*y,c*x*x,c*y*y,x**3,y**3,x*x*y,x*y*y]`.

No horizon-specific heads. Standardize nonconstant query columns on training only, preserving invertibility. Set `phi_v=flatten(q⊗f_v)`; P=264/528 regardless of K,V. One scalar coefficient vector is shared across value coordinates: `prediction_v=phi_v @ w`. This is a declared coordinate-symmetric inductive bias, not a multioutput model with hidden V-fold cost.

Fit weighted physical-unit squared loss plus `ridge*||w||²`; weights implement equal histories/tasks/coordinates, frozen regime weights and inverse training task-scale squared. Normalize weights to sum1. Stream sufficient statistics G and b, then solve `(G+ridge*I)w=b` in FP64. Record primal objective and scaled residual; verify qualification against an independently constructed QR/SVD augmented least-squares solution. Do not infer statistical generalization from convex optimality.

Finite development grid: query widths{8,16}, ridge{1e−10,1e−6,1e−2}, dimensionless rate endpoints `alpha_min=1/5224`, `alpha_max∈{0.5,1,2}`:18 candidates/family. Physical rates are alpha/t_ref. Fit t_ref only from training positive gaps. Training-only target-unit/time normalization transports frozen dimensionless weights to sensor data; record the physical rate conversion.

## Qualification and representational sufficiency

Reuse the exact original four-history two-age fixture, all16keys/eightvalues and four query templates. Fresh validation:32 independent histories from identical value law Uniform[−1,1], disjoint recorded seed2026102403, same ages/templates. Qualification config: q8, ridge1e−10, canonical alpha_max1, t_ref1; no candidate selection. Repeat scalar K12/V1 with disjoint seed2026102404 and four training/32 validation histories. Require every task/key normalized MSE≤1e−4 separately on fit and fresh validation, using fit-only task scales. Freeze seeds before execution; failed cells remain failed.

Proof: distinct Bank poles invert two age coefficients; Jet Z/H likewise recover arbitrary recent r and old o. For these templates, mean outputs are r at a0 and o at a2; contrast outputs r−o at a0 for either width. Hence `r + x*(o−r)/log(3) − c*o` is exact, linear in raw state times{1,x,c}, contained in both feature classes. Affine standardization preserves this span. Ridge shrinkage still requires measured qualification. This proves expressibility for the four templates and arbitrary fresh values, not arbitrary continuous hard-window boundaries or arbitrary histories.

## Data access and resources

Implement versioned shape-general generation from the documented process/seed laws and independent exact event oracle; golden-check K16/V8 against existing public exploratory `generate_episode`, including events, queries, labels and masks. Keep golden compatibility mode development-only. New namespaces use separately committed roots; never relabel protected generation as development or monkeypatch the old guard.

Protected loaders require verified manifest/source/data commitments, admitted phase, matching namespace/shape and declared episode inventory; no bare `authorized=True`. Beijing loader verifies existing archive/preparation hashes, current target semantics, train-only normalization and chronological block inventory before authorized test access. Preserve absent measurements and raw-unit targets.

Largest Gram occupies528²×8≈2.13MiB;1024-row feature chunk≈4.13MiB. Reuse bounded streaming passes for scalers and sufficient statistics; never retain all histories/features. Count coefficients, scalers, query buffers, solver workspace and actual RSS separately. Neither small Gram arithmetic nor historical≈400MiB process evidence substitutes for measured admission.
