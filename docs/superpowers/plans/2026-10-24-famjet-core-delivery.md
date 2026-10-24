# FAM-Jet Core Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an executable and reproducible local fixed-writer memory PoC, with an honest completed decision.

**Architecture:** A small `famjet_poc` package reuses frozen kernels and metrics, fits a qualified convex query-conditioned reader, freezes paired scientific runs, and reports raw-artifact results. Fitted-model conditional inference is separate from old failed crossed inference. Existing failures remain immutable.

**Tech Stack:** Existing locked Python, NumPy/SciPy, PyTorch CPU64, standard-library JSON/hash/CLI and pytest; no new mandatory dependencies or models.

**Spec:** [Completion design](../specs/2026-10-24-famjet-core-delivery-design.md), with its exact linked model/data and inference contracts. This supplements original Tasks18–25; use the original plan's SDD workspace and ledger rather than restarting completed tasks.

## Global Constraints

- Work on current `main`; no branch/worktree/push/PR.
- Preserve53historicalcore files/15StageA/lock/88historicalsource rows and previous outcomes.
- CPUfloat64, same causal writes/publicqueries/statebytes for Jet4/Bank8.
- No eventual query in writer, no raw-history access during bounded-state reads.
- Numeric failure uses frozen training-prior fallback and retains full loss; invalid oracle targets retain explicit eligibility status.
- Primary conditional-on-frozen-model estimand;12strata and H1536 plus independent H1536 replication, unless predeclared calibrated revision.
- No protected generation/read before accepted source, calibration, frozen complete inventory and grant.
- Both Beijing modes; no mismatched16/V8 checkpoint, no test-derived preprocessing.
- Qualifying a new reader or inference class does not repair old failures.

## Review Focus

- State versus reader identity: a new reader may reuse fixed-writer snapshots; changed rates/time units must reject stale snapshots (E1/E3).
- Arbitrary tagged feature rows must never become verified production provenance (E1).
- A crash or missing method/history cannot shrink inference or appear complete (E4).
- Scalar contrast unit inversion must not add pollutant mean (E4).
- Report replay must not choose configurations or mix unavailable metrics with zeros (E5/E6).

## E1 — Dimension-general models and authorized data

Create `famjet_poc/{__init__,contracts,data,models}.py`; tests `tests/test_poc_models.py`, `tests/test_poc_data.py`. Exact interfaces/formulas are in the model/data contract; replayable factories are mandatory. Produce typed strict schemas, golden primary-generation equivalence, content-verified protected grants, current-v2 Beijing loader, query-interaction ridge fitting/static roundtrip.

- [ ] Write behavioral REDs for feature order/count, factory/row binding, strict manifests/shapes, unknown fields, independent normal-equation/QR reference, masks and unit/shift invariants.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_poc_models.py tests/test_poc_data.py`; implement minimal source and pass covering checks.
- [ ] Commit source/evidence, independent spec+quality review and necessary scoped corrections.
- [ ] Run one separately bounded qualification over two numeric shapes×two widths×two families; record fit/fresh-validation errors and objective residuals without changing thresholds.

## E2 — Conditional inference and independent calibration

Create `famjet_poc/inference.py`, `tests/test_poc_inference.py`. Consume exact adopted conditional-history protocol; produce `conditional_interval`, strict paired12-stratum validation, deterministic calibration batches, counts/Clopper–Pearson acceptance and source/seed-bound evidence. Analytic endpoints have no bootstrap-MC status.

- [ ] RED then implement/check hand-derived mean/variance/df, sign/A-A/zero-variance rules, source/inventory tampering, duplicate-query rejection and every fixed law's analytical mean/variance.
- [ ] Commit/review covering tests; probe one small predetermined calibration chunk to forecast/lock deadline.
- [ ] Execute the fixed20k×8 campaign, retain every count/raw summary; use only the prospective H3072 revision if needed. No posthoc fixture removal.

## E3 — Audited read wire, baselines, development and costs

Create `famjet_poc/{wire,worker,study,timing}.py`, `tests/test_poc_{wire,study,timing}.py`. Consume E1 models/data; produce source-pinned snapshot/query-only worker, full byte ledger, packed simple references, complete18-per-family development matrix and deterministic selection, subset curves and real incremental timings.

- [ ] REDs for hidden cache/labels/raw-history injection, static/snapshot mismatches, parameter/statebyte accounting, immutable query order/resume and failed-trial inventory.
- [ ] Implement cache keys/streams/fallback/coremetric use, exact/ring/reservoir/buckets/latest where task-compatible. Worker gets no raw history or training cache.
- [ ] Commit/review then run measured feasibility and finite development; save convergence-within-feature-class residuals, every configuration cost and selected family artifacts.
- [ ] Measure randomized separated blocks for preprocessing/fit, actual streaming ingestion, cold/warm/batched queries, serialization and repeated-query totals; no terminal-encode timing mislabeled ingestion.

## E4 — Frozen complete execution and both transfers

Create `famjet_poc/{protected,transfer,pipeline}.py`, tests `tests/test_poc_{protected,transfer,pipeline}.py`. Produce immutable manifests, source/weight/calibration commitments, authorized grants, seal/complete/unblind, stage-boundary resume, nuisance and confirmation/replication phases, shape-matched frozen and task-adapted real runs.

- [ ] REDs for incomplete pair, changed code/weights, unauthorized test access, partial output/restart, all-station cluster grouping, native contrast inversion and modes untouched by test selection.
- [ ] Implement phase dependency validation, atomic evidence, metadata-only commit allowlist and source hashes; failures retain full inventories and costs.
- [ ] Commit/review; test-only end-to-end manifest before scientific freeze. Reprepare/verify local Beijingv2 without inspecting sealed scores.

## E5 — CLI, artifact-derived reporting and reproducibility

Create `famjet_poc/{__main__,report}.py`, tests `tests/test_poc_{cli,report}.py`; README and final ledgers. Commands: `python -m famjet_poc run --out RUNROOT [--resume]`, `python -m famjet_poc report --run RUNROOT --out reports/final.md`, and `--help`. The run command drives actual accepted phases, not stubs.

- [ ] RED for missing pair/changed artifact/refusal of fake success, unavailable values, unsupported secondary inventory and deterministic report replay.
- [ ] Implement native/normalized error tables, paired uncertainty with scope, cost/quality/storage plots as standalone artifacts, tuning/failures/licenses/claims inventory and optional-not-entered status.
- [ ] Commit/review; verify lock installation in fresh temporary environment, all documented entry-point help, interruption/resume and new entered-scope suite. Preserve legacy test semantics.

## E6 — Execute the complete core and final audit

- [ ] Before protection freeze accepted implementation, fits, data/seed inventories, primary allocation, inference/calibration and measured resource forecasts in a separate preregistration commit.
- [ ] Run the one-command workflow/resume to complete confirmation and direction-independent replication, both real modes, finite stress/secondary inventory and report; never open a partial comparison.
- [ ] Rebuild report from saved records with identical content/artifact hashes; verify source/data/model/expected-vs-actual ledger and all failures.
- [ ] Most-capable whole-branch review from originalBASE78f7ba8, plus new completion delta; one repair wave, required checks and final meaningful commit.
- [ ] Handoff final report, exact reproduction command, measured findings, limits and clean Git state. No optional language/probe work or broad superiority claim implied.

Self-review: requirements map to E1 mathematical/data provenance, E2 applicable inference, E3 fair costs/selection, E4 protection/real/resume, E5 runnable/report, E6 actual evidence/clean handoff. Entered numeric core is finite; hypothesis failures are valid outcomes, incomplete engineering is not called end-to-end delivery.
