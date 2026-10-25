# Sealed Report Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an auditable report and portable replay of the completed run06 without rerunning science or changing frozen artifacts.

**Architecture:** Correct order-sensitive inventory validation in the report reader. An explicit run06-only transition pins the old execution and new reporter byte maps, and a separately hashed launcher renders from sealed artifacts using existing scientific helpers. Normal execution APIs remain strict.

**Tech Stack:** Existing locked CPython, standard library, NumPy/SciPy and separate locked plotting environment; no dependency changes.

**Spec:** [Adopted recovery design](../specs/2026-10-25-sealed-report-recovery-design.md). This supplements existing E6 in the original SDD workspace.

## Global Constraints

- Current main; one tracked/Git writer; no branch, push or PR.
- Only `famjet_poc/report_inputs.py` may change among the 74 frozen executable/lock paths. No additions/removals in that inventory.
- Preserve original source f886e3c41517fd935a642cb83233dd72faf083b0, old full identity b994b3ef7b770fb50db7adba3a9125f75c7c5dc1a4cd3dc3d85843d3177e1260, raw run, failed report, policy and clocks unchanged.
- Exact registered migration only. No generic identity override, monkeypatch, arbitrary manifest argument, grant creation, fit, selection, data generation, resealing, or scientific pipeline resume.
- Read all 288 receipts in sealed order; require exact unique roster plus run ID/cell/method binding. Preserve all downstream source/model/data/count/query/resource/inference validations.
- Original execution failed report assembly. Recovery success is separately attributed, timed, source-bound and recorded.

## Review Focus

- Same roster in different order must pass; duplicates, missing/extra IDs and swapped method bindings must fail.
- Consistently rewritten policy/anchor and source-map laundering must fail before score access.
- Old protected execution APIs must stay strict under corrected reporter source.
- Copied full run and archived source must work with original locations unavailable and unchanged JSON bytes.
- Recovery provenance must appear in human/machine outputs while prescribed scientific values and chart data stay deterministic.

---

### Task R7: Exact report-only recovery source

**Files:** modify `famjet_poc/report_inputs.py`; create `scripts/report_run06_recovery.py`, `docs/research/e2e-run06-report-migration.json`, `tests/test_poc_report_recovery.py`; extend `tests/test_poc_report_inputs.py` only for affected ordinary roster contract. Report and raw receipts under `docs/research/e2e-report-recovery-source-report.md` and `docs/research/e2e-report-recovery-source-evidence/`.

**Interfaces:** consume original indexed run, old archived source map, normal report composition helpers and fixed migration ID `run06-report-order-v1`; produce `load_report_inputs(run, *, compatibility_id=None, archived_source=None)` with strict default plus exact explicit recovery, and launcher `--run RUNROOT --out MARKDOWN --archived-source DIR --compatibility-id run06-report-order-v1`. Interface details may be narrowed by implementation without introducing a generic exemption.

- [ ] Write and capture RED `test_reordered_run_roster_preserves_exact_inventory`, `test_run_id_is_bound_to_cell_and_method`, `test_report_migration_rejects_scientific_source_or_clock_change`, and fixtures covering every seven-group acceptance requirement in the spec.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_poc_report_inputs.py tests/test_poc_report_recovery.py`; capture expected failures before source edits.
- [ ] Implement the exact transition and reporter predicate. Keep normal `FrozenStudyRef.read`, `verify_run_policy`, `bind_run_policy`, `render_report`, scientific formulas and inference byte-exact. Include both source identities, manifest/launcher digests and original failed status in recovered Markdown/JSON/receipt.
- [ ] Generate the detached target inventory only after reporter/launcher bytes settle; verify the sole changed frozen path and every archived original source byte. The manifest pins the original index, freeze/releases/inference, ledger, policy/anchor, stderr and exit witness. It contains no outcome-driven configuration.
- [ ] Pass affected report inputs/report scientific/recovery/CLI tests; compile and documented launcher help; mutation/copied fixture coverage. Capture exact commands, UTC, exit, elapsed and raw log lengths/hashes. Do not run a full actual recovery or protected work before Root review.
- [ ] Commit source and evidence; write full report including known limits. Root reads it and dispatches independent spec/quality review with exact diff.

### Task R7 execution: Root actual recovery and handoff

- [ ] After accepted source, run one separately witnessed artifact-only recovery in a new sibling output directory, at most 900 seconds, 1.5 GiB RSS and 128 MiB new output, CPU1, preserving old inputs and clocks. Record all failures separately.
- [ ] Read full recovered report, source-bound machine output and receipt; verify raw-data prescribed inference matches sealed inference exactly. Render/replay in the clean locked main environment plus separate plotting environment.
- [ ] Copy the entire original run and archived source, make original locations unavailable, replay with unchanged frozen JSON; compare deterministic scientific values, Markdown/JSON/chart data/SVG hashes, allowing only explicitly separated volatile receipt metadata.
- [ ] Publish reports, raw custody/index/archives, cumulative failed execution/recovery costs and decision-first README/AUDIT/PROGRESS/DECISIONS. Then complete the outstanding original-base whole-branch review and one repair wave under E6, archive SDD rulings and hand off clean main.

Self-review: source/report identities and changed-file scope map to the exact migration task; all five Review Focus items have required fixture groups. Old scientific source, frozen artifacts and inference choices remain unchanged. Source gate is separate from actual replay and original E6 final audit; a passing source task is not completion.
