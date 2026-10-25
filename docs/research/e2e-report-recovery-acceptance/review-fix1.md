# R7 fix round 1 independent rereview

**SPEC: YES for the repaired source gate. QUALITY: APPROVED for Root's actual recovery gate.**

All five findings R7-R1 through R7-R5 are **ADDRESSED**. No new blocking defect was found in the repair diff. This accepts source readiness only; actual downstream scientific validation, complete recovery rendering and original-locations-unavailable replay are **NOT RUN** by this review and remain required before any delivery-complete claim.

## Scope and evidence identity

Reviewed the full updated `docs/research/e2e-report-recovery-source-report.md`, including its round 1 section; the original five findings; Task R7 and its adopted recovery spec; and exact repair range `3056df79..108c958c` (source `42940514`, evidence `108c958c`). The supplied review package `.superpowers/sdd/2026-10-16-famjet/e2e-report-recovery-fix1-review-package.diff` has SHA-256 `d45b68f6eede5a5cd3155ce77c9f2fba2c2b40fc3c4a228dff7008fe143e0d8f`.

The detached migration now hashes to `881cf66a7a5b099e5620ab4e4d17699b1c1c005052e67dabb649ec1642b00e27`. Its corrected reporter identity is `1bd8aca2d561f7412995c87dd183f908918c5f0ad0aef2006c75f3362f3c0703`; launcher identity is `9bcb1724fd16793314f5fcd5f8faef87d78fccfc70343705540ff92f206eb83e`. The original execution identity remains `b994b3ef7b770fb50db7adba3a9125f75c7c5dc1a4cd3dc3d85843d3177e1260`.

No test rerun, recovery render, scientific execution, protected work or old04 private-outcome inspection occurred. No source/Git edits or subagents were used. This review document is the only write.

## Finding resolutions

### R7-R1 — ADDRESSED: preparation inputs protected before output writes

`famjet_poc/report_inputs.py:117` centralizes the required preparation-root derivation. `scripts/report_run06_recovery.py:125` resolves that root and `scripts/report_run06_recovery.py:127` rejects destinations inside run, preparation or source archive before output directory creation. The two permitted preparation layouts match admission's own resolver.

`tests/test_poc_report_recovery.py:210` exercises six input-root/layout combinations, verifies unchanged sentinel file contents and rejects before the destination is created. The recorded RED log contains both prior preparation-root failures; the recorded final GREEN suite includes the fixed cases. The concrete immutable-preparation write path from R7-R1 is closed.

### R7-R2 — ADDRESSED: independently pinned launcher authorization

`famjet_poc/report_inputs.py:27` fixes the reviewed launcher digest inside the reporter. `_verify_launcher_authorization` at line 122 independently compares both manifest field and actual launcher bytes with that constant; production admission invokes it at line 168. Coordinately changing launcher bytes and its detached manifest field can no longer pass the unchanged reporter verifier.

`tests/test_poc_report_recovery.py:230` reproduces that coordinated rewrite using a copied launcher and the production verification helper. The separately pinned reporting lock is preserved through `_verify_reporting_lock` at `famjet_poc/report_inputs.py:128`, with its coordinated rewrite case at `tests/test_poc_report_recovery.py:244`. Neither helper introduces a caller-supplied identity exemption into `load_report_inputs` or any execution API.

### R7-R3 — ADDRESSED: admitted failures and publication state retain truthful evidence

`scripts/report_run06_recovery.py:145` starts the receipt as unverified. Exact migration admission occurs at line 154, with verified source/input provenance retained at lines 155–156 before `_render`. A failure after this point keeps both identities, migration/launcher hashes, original failure and archive-index binding. A rejected admission is not labelled verified.

The success path writes `validated_pending_publication` before renaming and only marks `completed` after the rename succeeds (`scripts/report_run06_recovery.py:161`, line 167, line 169). The exception path at line 173 selects the remaining attempt or published directory, records partial output hashes and renderer evidence, changes status to failed and records elapsed time/RSS. It no longer leaves a false completed receipt when publication itself fails.

`tests/test_poc_report_recovery.py:308` verifies a controlled downstream failure after real migration admission, including provenance and partial-output digest. The publication-failure fixture at line 332 verifies failed status and no final publication. The existing early-admission-failure test remains present at line 188. These cover the identified failure-record defect without claiming the scientific renderer ran successfully.

### R7-R4 — ADDRESSED for source-gate coverage

The added fixtures close the material source-gate coverage gaps identified in the first review:

- Archived lock/addition/omission rejection at `tests/test_poc_report_recovery.py:120`; sealed freeze/release/ledger/addition/omission byte inventory mutation at line 138.
- Source-map changes, current reporter changes, executable additions/omissions, pinned artifacts and altered target-map rejection at line 257, supplementing the original changed scientific-source integration test.
- Historical policy schema/type/deadline/source/hash mutation at line 291, supplementing the existing consistently rewritten policy/anchor test.
- Copied admission with original-run opens forbidden and protected pipeline/freeze/seal entry points instrumented as forbidden at line 166.
- Post-admission failure/publication fixtures at lines 308 and 332; repeated complete deterministic output inventory at line 353; human/machine recovery composition at line 396.

The roster tests, strict original execution API rejection tests, and existing report/scientific-report/policy tests remain unchanged in this repair. The fixtures deliberately mix isolated production helpers, real indexed admission and controlled orchestration outputs. They are adequate for this source gate; the copied-admission fixture is not a complete hidden-original-source render, and the fixed SVG fixture is not a real Matplotlib determinism result. Those distinctions are accurately disclosed in the updated implementer report and retained as actual-gate requirements below.

### R7-R5 — ADDRESSED: volatile plotting evidence confined to the receipt

`scripts/report_run06_recovery.py:37` captures invocation JSON, command/path/time metadata and raw stdout/stderr bytes, with hashes, into the recovery receipt and removes the volatile files from the attempt's deterministic publication inventory. It handles a log without accompanying metadata. Both successful and failed rendering paths use this capture; the scientific plotting helper remains unchanged.

`tests/test_poc_report_recovery.py:353` compares two full output inventories despite different invocation metadata and checks the invocation files are absent from both publications. `tests/test_poc_report_recovery.py:386` covers an orphan partial plotting log. The emitted Markdown, machine JSON, chart data, plots and deterministic renderer receipt can therefore be compared independently of the single volatile recovery receipt. The actual run still needs to prove this with real outputs.

## Preservation and recorded verification

The repair changes `famjet_poc/report_inputs.py`, the new recovery launcher, its detached manifest, tests and evidence/report documents. No other existing executable source or lock appears in the repair diff. Compared the two detached manifests: the only changed top-level fields are launcher digest, new file map, new reporter-file digest and new aggregate. The old 74-file map and all old/run/clock/release/inference/witness pins are unchanged; the only changed member of the new file map is `famjet_poc/report_inputs.py`.

Independently checked current reporter-file, launcher and reporting-lock byte digests against the repaired manifest. All match. This supplements the recorded source-preservation log, which reports 74 files, only the report reader changed, and successful original/copied full-inventory admission. The large run inventory/admission check was not rerun during review.

Read the raw RED log and checked its length/SHA-256 against `fixround1/red.json`: exact match, recorded exit 1, **6 failed, 4 passed, 15 deselected**. Checked all five GREEN log lengths/hashes against `fixround1/green.json`: exact matches, all recorded exits 0. The targeted log records **98 passed in 17.07 s**. Compile, fixed-ID help, preservation/admission and diff-check evidence are consistent with the updated report. Later individual RED observations are candidly identified as session-only and are not treated as independently archived evidence here.

The repair does not change roster semantics, formulas, inference, protected APIs or normal strict report/execution behavior. No generic manifest override, identity exemption, grant creation, fit, data generation, resealing or scientific pipeline resume was introduced. Execution and reporter identities remain distinct, with the original exit 1 and failed report preserved.

## Required actual gate and limits

Root may proceed with the separately witnessed, resource-bounded artifact-only recovery specified by R7. It must inspect complete human/machine output and receipt, verify prescribed inference against sealed inference, preserve original inventories and clocks, and complete copied-run/source replay with original locations unavailable. Compare deterministic Markdown/JSON/chart data/SVG and renderer evidence hashes, excluding only the explicitly volatile recovery receipt.

This approval does not establish full downstream scientific validation, actual SVG equality, plotting-environment behavior, recovery resource compliance or final delivery completion. Any downstream failure must retain its own failed attempt and receive separate diagnosis rather than being absorbed into the roster migration.
