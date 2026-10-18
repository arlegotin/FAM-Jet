# Task18 experiment-policy design audit

2026-10-18. **Design only: no adoption, amendment, execution allocation or numerical acceptance.** Production inspection pinned to `6bed0cd17e853c135a570682b5931a1e89d11f0d`; Task19 remains the sole production implementer. Read binding design §§8–12, plan Task18, the requested policy/config/cache/train modules and fixed/learned/structured tests. No tests, models, scientific data, profiling or experiments were executed. No completed kernel-reader/bootstrap/variance investigation was repeated.

## Recommendation and alternatives

**Keep the existing policy for the next epsilon numerical gate. Consider a small exact declaration mechanism at the next planned source window, before repeated tuning under a stable package.** The old epsilon1e-8 numerical failure remains failed; epsilon1e-6 source eligibility is independently approved, but its numerical gate is pending. This audit supplies no reason to postpone that discriminating gate or interrupt Task19.

| Option | Benefit | Cost/risk | Judgment |
|---|---|---|---|
| Existing exact predicates | Already reviewed, deliberate bounded allocation; least immediate change | Every newly eligible width/LR/read configuration may require another source edit, review, cache refresh and feature preparation | Best immediate choice; still reasonable if few further variants survive numerics |
| Exact declaration plus existing guards | Changes to already implemented configurations become dated, hash-bound data records within one reviewed package; removes duplicated allocation literals | One source/review/test migration; strict evidence/authority interface required; provenance cycles and accidentally broad permits must be avoided | Preferred later design if repeated tuning proceeds |
| General experiment/search engine | Potential scheduling, search and family automation | Large new execution/authority surface and migration; still cannot establish numerical or scientific acceptance | Reject for this task |

The observed structured operational campaign charged 363.872493 s and 953,874,048 B for one strict raw refresh, plus separate fresh fits/caches. These are historical measurements, not a forecast for every future shape. A declaration can avoid **predicate-induced package changes**, not necessary feature refits, profiles, independent gates or changes to genuinely missing functionality. Current schedule/checkpoint semantics are constant-only; a declaration naming cosine decay cannot implement it. New scheduling needs a separate typed implementation and resume verification. New precision, writer or family support likewise requires actual source work where absent.

## Current boundaries to preserve

`fixed_basis_cpu64` admits exact CPU64 fixed-basis shapes and explicitly disclaims execution allocation. `resolve_policy` binds calibration shape/LR/horizon and measured calibration for learning; `make_model` repeats precision eligibility; `feature_identity` repeats cache eligibility and checks actual model/config agreement. This duplication explains the maintenance pressure. It is not evidence that the bounded policy was a bug.

Reuse `RunConfig`/strict parsing, `execution_shape`, `canonical_hash`, `reader_budget`, `parameter_accounting`, `model_ledger`, existing calibration artifacts and closed constructors. `execution_shape` alone is insufficient authorization: it omits learning rate, weight decay, complete horizon/milestones and some resource/stop choices. Exact authorization must also bind the complete resolved config, resolved execution policy and actual requested operation.

`source_identity()` hashes **every** `famjet/*.py`, including unrelated Task19 source changes. Raw identity additionally binds lock, full data config, data seed, length inventory, semantics, namespace/order/count. Keep this exact identity and every file/order/hash validation unchanged. Full development checkpoint continuation also compares `_source()` (commit, diff, untracked package files, package hash). Even a metadata-only Git change can therefore prevent continuation while leaving raw-cache identity unchanged. Do not weaken either guard to realize the proposal.

## Minimal declaration and authority interface

Use **one immutable exact entry per operation**, not a range, wildcard, Cartesian product, arbitrary predicate, import path, callback or plugin. Multiple entries may share existing evidence only where the evidence explicitly covers each entry. The following is a proposed closed schema, not a completed implementation or an executable authorization:

| Field | Required content |
|---|---|
| `version`, `entry_id`, `issued_utc` | One supported version; unique immutable ID; UTC issuance |
| `source`, `lock_hash` | Exact current `_source()` and dependency-lock digest; package hash matches `source_identity()` |
| `amendment_refs` | Dated methodological scope references and immutable hashes; explicit empty list only when no methodological change is involved |
| `config`, `config_hash` | Complete resolved `RunConfig`, including explicit nulls/defaults; hash recomputed after strict parsing |
| `execution_policy`, `shape_hash` | Exact supported policy, including constant schedule, clipping, namespaces, weights, chunk/recompute behavior; hash of existing `execution_shape(config)` |
| `operation` | Closed stage enum: numerical check, preparation, cold calibration, learning, or simple control; exact start/stop steps, bounded case/repetition inventory, output destination, resume-checkpoint digest or explicit null |
| `limits` | Explicit stage wall-time, RAM/net-allocation, disk/projection/reserve, persistent-state bytes, static parameter/buffer bytes, allocated/active-parameter envelope, reader input/MAC envelope, checkpoint/cache retention; no omitted or unlimited quantities |
| `evidence_refs` | Typed path+hash references to required source review, numerical evidence, resource discovery/calibration, raw/feature identities and procedure inventory; null allowed only for a prerequisite not yet produced at that stage |

Use the config as the sole model/data/training specification; repeated shape/policy/budget assertions are checked against it, never alternative sources of defaults. Explicitly bind optimizer implementation/options (including current AdamW defaults through the locked implementation), schedule, precision, all writer/rate/reader settings, epsilon/support/fallback policy, seeds, populations/load, preprocessing/statistics and stopping. A changed field means a new entry. Unknown fields, duplicate keys, nonfinite values, unknown enums and unsupported family/dtype/reader combinations fail closed.

Ownership: implementers may draft entries; root owns methodological decisions and execution allocation; reviewers/check procedures supply independently assessed evidence. Keep launch-bound declarations in immutable external operation artifacts outside `famjet`, under the existing ignored artifact area, after freezing the actual Git source. A tracked uncommitted declaration containing its own `_source().diff` would be circular. Later documentation promotion changes Git identity normally; it must not silently rewrite an active run's source or make its checkpoint resumable across that change.

Keep **four separate decisions**:

1. **Eligibility:** the reviewed closed implementation supports the config and its serialization/gradient/cache path.
2. **Root allocation:** a separate dated root execution record references this entry's canonical digest, exact operation/caps and evidence. Caller-supplied `approved: true`, a digest copied into the same file, or a self-issued root label is not authority. Root supplies the expected allocation/entry digests through the existing controlled launch process; documents record that authorization rather than create it. This remains administrative control, not cryptographic security against the local administrator.
3. **Numerical applicability:** actual passed evidence, with exact procedure/source/lock/model/read-policy/precision/data scope and original tolerances. A declaration cannot mark a failed or pending gate passed. A numerical-check allocation can execute the bounded check that produces evidence; it cannot authorize learning.
4. **Measured resource applicability:** actual discovery and cold-calibration evidence for the exact stage/shape/device/data/cache/optimizer/policy. Small profiling is separately bounded while calibration is pending. A profile's two updates are resource evidence, not accepted learning, convergence or a larger allocation.

Avoid self-referential hashes: pass the declaration reference as a separate request argument, outside the config it hashes. A preparation entry binds its exact inputs; its output manifest is new evidence for a subsequent profile entry. A profile entry produces calibration and fitted numerical evidence used by a subsequent learning entry. Each later entry explicitly changes mode/calibration references and binds its own complete config. Never prefill future output hashes, mutate an old entry, or silently ignore fields to make hashes match. Evidence applicability may reuse the existing execution-shape comparison, but stage transitions must name exact permitted deltas; profiles and learning otherwise retain identical model/data/optimizer settings. A changed optimizer, clip, schedule, horizon or execution cap requires new applicability assessment and fresh measurement unless existing measured evidence explicitly covers it.

## Small implementation boundary and ordering

If adopted later, add one strict declaration/validation module beside `analysis/development.py`; a typed execution request/receipt is threaded through existing `resolve_policy`, `run_development`, `train_model`, `make_model` and feature-preparation callers. Do not create a second trainer, evaluator, constructor registry or arbitrary numerical runner. Reuse existing helpers and bind any existing external procedure by reviewed bytes and explicit arguments. The receipt is immutable and revalidated against the config/source/entry; an ordinary dictionary claiming permission is insufficient.

Replace repeated **allocation literals** only on the new declared path. Retain family capability checks, `_require_fixed_upstream`, precision restrictions supported by actual constructors, the existing smoke path, phase checks and all source/cache/checkpoint validators. The original exact development path can remain unchanged during migration; a malformed or missing declaration on a request selecting the new path must never fall back to legacy execution.

Fail closed in this order:

1. Parse bounded metadata and exact config; reject protected phases/namespaces and unknown capability/stage. Resolve current package/Git/lock identity and independently supplied root allocation. Check amendments, request stop/resume boundary and exact entry digest before model/tensor/corpus allocation.
2. Validate all required evidence hashes/status/applicability, resource discovery, caps and disk reserve. Numerics/preparation/profile may have explicitly staged pending downstream evidence; learning cannot. Reject invalid profile-to-learning transitions before constructing a model or loading checkpoint tensors.
3. Apply existing pure descriptor/dimension/resource checks and checkpoint expected-identity validation. After bounded construction, compare actual exported tensor layout, complete persistent/static inventory and parameter/MAC accounting with declared limits before fitting/training. Account for the construction itself in the profile ceiling; never allocate an unbounded candidate merely to discover its size.
4. Fit fresh training-only statistics as required. Keep feature identity v2 comparison before raw-cache construction or feature tensor loading, followed by unchanged complete raw/feature file and order verification. Monitor actual costs, ceilings and explicit stop boundaries throughout execution.
5. Record entry/allocation/evidence hashes with current config/policy/source/data identities and actual expenditure. Preserve every attempted/failed run. Resume keeps the original full source, config, policy, checkpoint, RNG/optimizer/sampler checks; a new permit does not migrate a checkpoint. Historical inspection remains available without new execution permission.

Allocation receipts belong in run audit metadata. A newly allocated continuation stop must not rewrite the checkpoint's scientific config/policy identity; it is usable only if all existing continuation checks still match.

Persistent state includes timestamps/status/keys/occupancy/counters/normalization/convolution and hidden caches. Static buffers/parameters are separately counted and included in end-to-end totals. A declaration's guessed byte or parameter value cannot override actual accounting. Keep no-padding and objective-active **upper-bound** labeling. Preserve timing separation, preparation charges, no hidden CPU fallback/transfers, training-only statistics, full-query failure/fallback accounting and protected-phase closure.

## Cache and family limits

Same package/lock/raw-data identity may reuse the existing raw transport across eligible config-only variants after full validation. Any package change still invalidates it; no source-compatibility exemption or old-manifest re-signing. A one-time implementation change therefore requires one ordinary fresh raw regeneration if execution is later allocated.

Keep writer/state hash writer-only. Jet/Bank read epsilon/support floor stay independently bound in feature identity v2; changing epsilon must not pretend to change recurrence state. Changes to read map/reader schema, writer, rates, precision or fitted statistics require fresh applicable feature preparation and preprocessing. Do not relabel old fitted arrays or features as fresh. Existing learned-rate/writer and nonlinear-kernel paths must use raw histories with complete current computation/gradients; no cached detached states or fixed features. Optimizer-only changes may reuse fixed features only when the complete existing feature identity is unchanged and the new operation is separately authorized.

Start the declaration path with the already reviewed CPU families and execution modes; constructor existence alone is not development acceptance. Full-state/reader/state/load variants require exact applicable tests and budgets. Learned writers, polynomial/log-scale, delta and additional families retain their own gradient, independent numerical, short-task positive-control, serialization, convergence and budget obligations. Broader competitiveness remains gated on accepted families and equal expenditure; the permit cannot substitute for `validate_baseline_acceptance` or open pilot/confirmation/replication.

## Required verification and rejection cases if implemented

Extend existing fixed-basis, structured, learned-rate, cache, training/resume and selection tests; add only a small declaration-focused test module. Preserve the existing tests of actual behavior and preallocation rejection. No tests were run for this report.

| Counterexample | Required result |
|---|---|
| Change shape/seed/LR/clip/schedule/epsilon/horizon/stop, or add an unknown field, then recompute only the entry hash | Reject without the separately matching root allocation and applicable evidence |
| Change package/Git/lock, or reuse a checkpoint after metadata-only source drift | Reject under existing source rules; no compatibility override |
| Copy numerical `passed` text, cite source eligibility, or use old epsilon1e-8 results for epsilon1e-6 | Reject learning; require genuine applicable passed evidence |
| Use a two-update profile or config horizon32768 as permission for more updates | Reject absent a separate exact learning allocation; enforce stage stop |
| Raise caps, omit state metadata/static buffers, invent inactive parameters or padding | Reject declared/actual budget disagreement; preserve all inventory accounting |
| Change upstream/read policy/statistics but reuse feature files or re-sign their manifest | Reject identity/layout/provenance; require fresh preparation |
| Attach a learned upstream tensor or nonlinear family to the fixed-feature route | Reject before detachment/cache replay |
| Name an unapproved family, protected phase, wildcard config, plugin or custom predicate | Reject before model/data allocation |

Also verify raw-vs-feature trajectory equivalence and deterministic complete-step resume on bounded fixtures, exact handling of profile/learning deltas, failed-run accounting, resource stops and no policy bypass through direct training/preparation callers. These tests establish implementation behavior, not scientific numerical acceptance or convergence.

## Residual cost and decision timing

The main residual risks are incorrect evidence applicability, duplicated derived fields drifting, administrative allocation authenticity, and unbounded construction before inventory comparison. Strict records and explicit stage transitions reduce them but add review work. New scheduler/family semantics and ongoing Task19 package changes still trigger normal invalidation; this design cannot promise “one source change for all Task18.”

There is a credible saving over many already implemented config variants within a stable package. There is no measured engineering break-even, and the next numerical result may change which variants merit work. **Do not delay that gate for this proposal.** If it passes and repeated tuning remains justified, root can separately decide on a bounded amendment/design adoption and an implementation window after the current sole-writer task. Until then, leave the reviewed exact policy in force and keep science held except for separately allocated stages.
