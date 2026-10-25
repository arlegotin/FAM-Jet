# Run06 sealed-report recovery design

Design only, 25 October 2026. No source changes, tests, training, scoring, or outcome inspection performed for this note. The source authority remains `docs/superpowers/specs/2026-10-24-famjet-core-delivery-design.md`. Root's requested recovery scope supplies authorization; Root adopts this design for the authorized end-to-end delivery; it is not yet an implemented recovery.

## Finding and recommendation

The sealed release is complete. Metadata inspection found 288 expected IDs and 288 receipt IDs, each unique, with equal sets and unequal ordering. The freeze starts each cell with Jet then Bank; canonical selected-model dictionary iteration produced Bank then Jet. `seal_release` already validates cell/method closure without ordering. `report_inputs._release_rows` incorrectly strengthens that contract to list equality before reading rows. The preserved traceback ends at that check.

Recommend one explicit, run06-only reporting migration. Correct the inventory predicate for future ordinary runs. For this already sealed run, distinguish the immutable execution identity from the corrected reporter identity through an exact reviewed transition manifest. Keep `protected.py`, `execution_policy.py`, all scientific implementation, and both dependency locks unchanged. Do not resume the scientific pipeline, rewrite the freeze, reorder serialized receipts, reseal, or silently replace the old executable hash.

A plain one-line fix is insufficient: `FrozenStudyRef.read()` compares the complete current executable identity with the freeze, and `verify_run_policy()`/`bind_run_policy()` independently reconstruct that same identity. Making those general scientific APIs accept an override would create an unnecessarily broad admission path. A temporary monkeypatch or copying modified code over an allegedly frozen source tree would conceal provenance. Neither is acceptable.

## Smallest concrete implementation boundary

Only `famjet_poc/report_inputs.py` changes among existing executable-identity files. It gains the corrected roster predicate and a narrowly scoped report-reader compatibility path. Add a committed recovery launcher outside the scientific package, for example `scripts/report_run06_recovery.py`, and a committed detached migration manifest under `docs/research/`. The launcher is explicitly hashed in the reporter provenance even though the existing executable inventory does not include scripts. No existing executable file is silently omitted from either manifest.

The recovery launcher accepts run/output paths and one fixed migration ID, not arbitrary old hashes, changed-file allowlists, or replacement policies. It calls `load_report_inputs(..., compatibility_id=...)`, then the existing report composition/plot/write helpers in `report.py`, adding recovery provenance to the machine report and Markdown. This small explicit composition duplicates only the final orchestration of `render_report`; it must not copy or replace scientific validation, aggregation, inference, plotting, or scientific prose. Keep the normal `render_report` and `run` entry points unchanged. A future maintenance refactor is outside this recovery.

The corrected ordinary roster check must require list schema, nonempty string IDs, uniqueness of both frozen and observed IDs, equal lengths and equal sets, and a valid expected roster derived from frozen cell/method pairs. Every receipt's `run_id` must equal its declared `cell_id + '-' + method`. Preserve subsequent duplicate pair, history, query, status, source/model/data, grant, count, score-contract, resource and hash checks. Never reorder input bytes or sort rows to satisfy this check. Continue processing receipts in their sealed order to avoid changing aggregation arithmetic.

## Exact transition, not a file exemption

Before implementation Root archives the complete original run, failed report generation, logs/witness, source bytes and inventories. The migration manifest must be complete before recovery opens score rows and must record:

- Fixed migration ID, reason, old commit, full old executable file map and aggregate, full new executable file map and aggregate, and the precise old/new `report_inputs.py` hashes. The maps must differ at exactly that one existing path, with no additions or removals in the executable inventory. This is one exact approved transition; future reporter edits require another reviewed transition.
- Launcher path/hash, manifest schema, and reporting dependency lock hash. Record the manifest's own SHA and the actual reporter Git revision in the recovery receipt; do not introduce a self-referential manifest hash.
- Exact freeze, synthetic release, real release, stored inference, original ledger including failed report generation, run policy, clock anchor, stderr and external exit-witness hashes, plus the preserved archive inventory. Pin these from the original archive before recovery opens score rows. The sealed primary inference was already unblinded after every comparison completed; this timing is recorded, and no scientific choice changes in this migration. The recovery must not accept a different run with the same source version.
- Explicit scope: artifact validation and reporting only; no fit, selection, fresh data generation, scientific stage execution, release creation or grant creation.

The committed reviewed manifest is an authorization artifact, not a claim that a caller-supplied manifest is intrinsically trustworthy. Resolve only the fixed repository migration ID; no arbitrary manifest-path argument or environment-based override. Verification rejects any manifest that does not match the fixed old commit/run anchors and the exact permitted transition structure. Record manifest and launcher digests in the final outputs so the authorization and actual implementation remain auditable.

Independently hash the preserved original source tree and require its entire inventory to equal the frozen executable map. Accept an archived source bundle at a supplied local location; never require the original checkout or original run absolute path to exist. Bind Root’s `e2e-run06-original-index.json` archive index (4,813 run files, 2,062,164,087 bytes, plus 10,158,074 preparation bytes as reported by Root) by hash in the transition. Reuse `ArtifactPaths` for artifact-only copied-root replay, preserving recorded path strings and enforcing traversal/symlink rejection. Independently hash the current tree and require its entire inventory to equal the manifest's target map. Consequently every scientific source byte and `requirements.lock` must equal both the old and new inventories. Check the reporting lock separately. The old aggregate remains the execution identity everywhere it originally appears; the new aggregate is labeled reporter identity, never substituted into frozen artifacts.

## Read-only frozen checks and unchanged science validation

Normal `load_report_inputs` retains its current strict calls to `FrozenStudyRef.read`, `verify_run_policy`, and `bind_run_policy`. Only the explicit run06 report path uses a separate read-only verification helper in `report_inputs.py`; it does not alter those general APIs or obtain a `FrozenStudyRef` suitable for scientific work.

That helper verifies the original freeze hash/schema/version/source commitment, the full original executable map and aggregate, and the exact target reporter transition. For the run policy, it verifies pinned raw policy/anchor bytes, equality to the frozen `resource_policy`, policy-file and baseline-file hashes, original execution hash, and exact canonical anchor fields. Recheck the original policy field types, complete key inventory and deadline arithmetic from the unchanged dated policy. The only contextual distinction is that historical `execution_source_sha256` is checked against the independently verified archived execution identity instead of current reporter bytes. A mere matching clock anchor is not sufficient.

All other validations in `load_report_inputs` and `_verify_frozen_science` remain on their existing paths, including stage inventories, qualification/calibration acceptance, selected checkpoints, transfer source, public selection gate, sidecars, row hashes, paired coverage, inference recomputation and exact comparison against sealed inference, real releases and native-unit checks. No new inferential choice is introduced. Existing validation may read sealed scores and recompute prescribed summaries after compatibility admission. External Beijing arrays retain the truthful existing `verified_inventory_not_rehashed` status; do not imply that report replay reopens or rehashes them.

## Outputs, clocks and failure preservation

Write recovery outputs to a new sibling directory outside the original run, using write-once attempt directories and final publication only after validation. Preserve the full original ledger, failed report entry, stdout/stderr, original exit code 1, and witness unchanged. Do not append a misleading successful generation to the historical pipeline ledger.

A separate recovery receipt binds both source identities, transition/launcher hashes, input artifact inventory, output hashes, invocation, start/end times, elapsed time, resource observation and success/failure. Failed recovery attempts remain present. Fresh reporting time is separately disclosed and never attributed to the original run or used to reset/extend its scientific clock. The original 25,786.649-second run and its original resource witness remain historical evidence. Completion is described as “sealed scientific run completed; initial report failed; audited report-only recovery completed,” not as an original uninterrupted exit-zero CLI run.

Normal future CLI execution freezes the corrected current identity and uses the ordinary strict path. This recovery mechanism does not authorize `run --resume` against the old freeze under changed source.

## Acceptance tests required before recovery

1. Small fixtures accept Jet/Bank order reversal and arbitrary receipt permutations, while rejecting duplicate, missing, unknown, malformed, and cell/method-swapped run IDs. Preserve duplicate cell/method, history/query and row-hash failures. The original fixture reproduces the old ordering exception.
2. Exact approved transition succeeds; a changed scientific byte, either lock, extra/missing executable, different reporter byte, different run/freeze/release, altered manifest target map, changed launcher, or unregistered migration fails before score rows open.
3. Ordinary `FrozenStudyRef.read`, policy binding, scientific admission and `run --resume` still reject the old identity under the corrected source. No compatibility token is accepted by those APIs. A new-source fixture uses normal report flow without recovery authorization.
4. Changing policy start, either deadline, policy schema/type, execution source, raw policy hash, or anchor fails. Rewriting policy and anchor consistently also fails against the pinned original hashes and frozen policy.
5. Existing semantic mutations remain rejected: checkpoint/count/row/grant/resource byte tampering, omitted method/cell, altered calibration or stored inference. Compare existing prescribed inference to sealed values; do not introduce alternative estimators or new tolerances.
6. A recovered copy of the original archive, with original run/source locations unavailable and only archived source plus required pinned project metadata present, completes reporting with every scientific stage accounted for; original input tree inventories before/after are byte-identical, including failed report artifacts and clocks. Guard instrumentation demonstrates no fitting, scientific source access, grant creation, resealing or pipeline admission occurs.
7. Both identities and the original failure appear in machine/Markdown outputs and the recovery receipt. A repeated report attempt preserves prior attempts. Output comparison allows explicitly volatile invocation/resource metadata only; scientific values and chart data remain deterministic.

Tests are proposed here, not executed. Use small synthetic fixtures for mutation coverage; do not rerun the protected experiment to test this fix.

## Verified metadata anchors

- Old commit: `f886e3c41517fd935a642cb83233dd72faf083b0`; tracked-source diff hash is the empty-byte SHA.
- Old full executable: `b994b3ef7b770fb50db7adba3a9125f75c7c5dc1a4cd3dc3d85843d3177e1260`.
- Freeze: `a0a1a66bc15de891b3bd365008e8ea24be74008d6fdc06bba958c619e6828845`.
- Synthetic release: `8b1ed1eec3c3899a4a2d5d8efb38329dbc33545ed88b5ca76e04ddf8dcb9b635`.
- Run policy: `175433f8e414bca12fc4e1308e259e1d64e804aba0f65a551a2579b4a5accd24`.
- Clock anchor: `87019266034d447e6dc7b1359bcce02a3a5117894388a8e7e3a22065fc41285d`.
- Initial stderr: `2e7387bd39f3440c036c8fa1694d89aae15a584552f78bc865d53407711c2065`.
- Exit witness: `567f5759da13b8d336a2cbe3a8dc9fce90cfff82512c730c386d2130e6261f71`.

Remaining risk is implementation drift between the report-only historical-policy verifier and the normal verifier, plus the small duplicated final rendering orchestration. Exact run pins, unchanged scientific APIs, mutation tests, and an independent review constrain those risks. Do not expand the migration to absorb a later unrelated validation failure; diagnose and review that failure separately.

## Root adoption and execution authority

Adopted 25 October 2026 for the existing authorized delivery. The user requested execution, subagents and meaningful commits and has repeatedly directed continuation. This repairs reporting only and requires no new user preference or permission. Original execution source is archived byte-for-byte at `docs/research/e2e-run06-execution-source/`, with all 74 executable/lock paths matching the frozen map. The complete original 4,813-file/2,062,164,087-byte run and preparation are indexed at `docs/research/e2e-run06-execution-record/index.json`; bulk data remain local and ignored. Preserve original CLI exit 1 and failed report, all source and artifact hashes, and every original clock. The separately reported sealed inference is inconclusive; no superiority claim is authorized.
