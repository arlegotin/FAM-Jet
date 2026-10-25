# R7 independent source review

**SPEC: NO. QUALITY: CHANGES REQUESTED. Source gate remains HOLD.**

Reviewed Task R7 in `docs/superpowers/plans/2026-10-25-sealed-report-recovery.md`, its adopted `docs/superpowers/specs/2026-10-25-sealed-report-recovery-design.md`, the full implementer report, and the exact `6caddb3e..3056df79` changes (source `5b3d3123`, evidence `3056df79`). Review-package SHA-256: `2f6802c9e70cb5e8350f1eea6630cd3337af98c755298d983b0824fddda6bcae`.

This verdict concerns source readiness only. Full downstream scientific validation, actual recovery rendering, and the original-locations-unavailable replay are **NOT RUN** and are not approved by this review. No tests were rerun, no science or protected stages were executed, no old04 private outcomes were read, and no source or Git state was edited. The only review write is this document.

## Findings

### R7-R1 — P1: preparation inputs are not protected from output writes

**Location:** `scripts/report_run06_recovery.py:91`, `scripts/report_run06_recovery.py:94`, `scripts/report_run06_recovery.py:99`; relevant input inventory at `famjet_poc/report_inputs.py:173`.

The launcher excludes output paths inside the supplied run and source archive, but the exact recovery also treats the sibling preparation directory as immutable indexed input. An output such as `.../e2e-core-run-06-prep/recovery/final.md` passes the exclusion. The launcher then creates `recovery-attempt-001` inside that preparation directory before admission. `_inventory(prep, ...)` ignores empty directories, so it does not reject this initial destination creation. Subsequent render files, or the failure receipt alone if rendering fails, are written into the preserved input tree. The resulting preparation inventory no longer matches its original index. Even a failed invocation can therefore change the indexed preparation archive, contrary to the preservation requirement.

Resolve and protect the required preparation root before any output mkdir/write, covering both `run`/`prep` archive layout and the original `run-name`/`run-name-prep` layout. Test attempted output placement under each input root and assert the complete inputs remain unchanged.

### R7-R2 — P1: launcher authorization can be rewritten without changing the admitted reporter

**Location:** `famjet_poc/report_inputs.py:123`, `famjet_poc/report_inputs.py:152`, `famjet_poc/report_inputs.py:167`.

The verifier records the manifest digest but never checks that digest against a trusted authorization. Its launcher check compares the actual launcher only with `manifest['launcher_sha256']`. Because the launcher is outside the 74-file executable map, changing the launcher and updating that one manifest field leaves the current reporter identity, all old/run anchors, and the transition predicate unchanged. The same registered migration is admitted by the unchanged verifier for a different launcher. This is a concrete coordinated metadata rewrite, not a hypothetical change to the verifier itself.

The old source/map and run anchors are well bound; the new launcher is not independently fixed to the reviewed transition. Pin the expected launcher digest in the trusted admission code, or provide an equivalent independently trusted authorization check without a caller override. A launcher does not need to embed its own hash, so a fixed launcher digest in the reporter followed by a detached target manifest need not be self-referential. Add a mutation case that changes launcher bytes and consistently rewrites the manifest launcher hash; it must fail before downstream score parsing. Do not describe matching two mutable values alone as exact authorization.

### R7-R3 — P2: failed recovery receipts omit admitted provenance and partial output hashes

**Location:** `scripts/report_run06_recovery.py:115`, `scripts/report_run06_recovery.py:116`, `scripts/report_run06_recovery.py:117`, `scripts/report_run06_recovery.py:123`.

Both identities, manifest/launcher digests, input archive identity and original failed status reach the receipt only after `_render` returns. Any later scientific validation, plotting, machine composition or write failure discards that provenance. The failed receipt retains invocation, Git HEAD, error, time and RSS, but does not bind the admitted source/artifacts; partial chart or report outputs are also not hashed because `_files` is called only on success. The existing failure test checks only an empty-run admission failure and does not detect this.

Capture attempted authorization metadata with an explicit admission state before downstream work, retain verified provenance as soon as admission succeeds, and collect partial output hashes in failure finalization. Do not mark unverified inputs as admitted. Add a small controlled post-admission failure fixture and check the retained record against the successful receipt contract. Publication failures should also leave an accurate failed attempt rather than a receipt already labelled completed before `os.replace` succeeds.

### R7-R4 — P2: required source-gate mutation and output fixtures are substantially incomplete

**Location:** `tests/test_poc_report_recovery.py:14`, `tests/test_poc_report_recovery.py:77`, `tests/test_poc_report_recovery.py:103`, `tests/test_poc_report_recovery.py:119`; scope claim at `docs/research/e2e-report-recovery-source-report.md:31`.

The new recovery file has seven tests. Its transition unit test changes one scientific-map value and one synthetic anchor value; the integration admission test changes one archived protected source file. There are no recovery admission mutation cases for either lock, added/missing executable paths, changed reporter bytes, changed launcher, altered manifest target map, different freeze/release/run, or coordinated launcher/manifest rewriting. The clock test covers one consistently rewritten clock but not the enumerated field/schema/type cases. No fixture checks successful recovery Markdown/JSON/receipt provenance or replay determinism. The copied preflight does not hide the original locations or exercise downstream recovery, as the report correctly acknowledges.

The recorded existing tests provide useful strict API, row/count, policy, CLI and ordinary smoke coverage, but they do not substitute for the R7 requirement to supply fixtures for all seven acceptance groups. Add the missing focused admission and output/failure fixtures, and identify which existing tests cover the unchanged semantic requirements. The complete real-run render and unavailable-original replay remain Root's later actual gate; they need not be run to repair this source-gate deficiency. The original RED observations are reported candidly as session-only and cannot be independently verified from this package.

### R7-R5 — P2: volatile plot invocation metadata remains outside the recovery receipt

**Location:** `scripts/report_run06_recovery.py:55`, `scripts/report_run06_recovery.py:117`; unchanged called helper `famjet_poc/report.py:119` and `famjet_poc/report.py:123`.

The launcher calls the existing plot helper, which writes `plot-invocation.json` containing actual interpreter/script/attempt-directory paths and elapsed time. `_files` includes that file in the published output inventory. Thus volatile invocation/time metadata is still a separate output artifact, although the review contract confines volatile paths/timing to the recovery receipt. The scientific machine report and chart data do not directly include this invocation object, which is good, but the publication inventory cannot be treated as deterministic except for the one recovery receipt.

Preserve the unchanged scientific helper while explicitly moving its invocation metadata into the recovery attempt receipt, or obtain and document a narrower approved comparison contract naming the separate volatile artifact. Add a fixture that compares the complete deterministic output inventory with only the agreed volatile evidence excluded. Do not discover and silently expand exclusions during the actual replay.

## Requirements that are satisfied by source inspection

- The exact diff changes only `famjet_poc/report_inputs.py` among existing executable files. `protected.py`, `execution_policy.py`, `report.py`, scientific implementation and both locks are unchanged. The recorded source-preservation check confirms 74 original files, one changed path and two admitted run roots.
- `_require_study_run_roster` checks list/string schema, uniqueness, expected cell/method roster, equal ID sets and explicit run-ID binding. It does not reorder receipts. Existing per-pair, history/query, row, grant, model/source, count and resource checks remain after it.
- Ordinary `load_report_inputs` still uses `FrozenStudyRef.read`, `verify_run_policy` and `bind_run_policy`. The general execution APIs receive no compatibility argument. The historical branch is limited to the registered ID and runs admission before downstream parsing.
- Original source bytes are independently hashed; additions, omissions and symlinks in archived source and indexed run/preparation inventories are rejected. The old map is fixed by the pinned original index and original aggregate. Scientific-byte/map laundering cannot pass the old/new one-path predicate with the fixed old index.
- The historical policy helper pins original raw policy and anchor bytes, checks the dated policy and baseline hashes, reconstructs field types/key inventory/deadline arithmetic and compares frozen resource policy. A consistent policy/anchor clock rewrite is rejected by the original hashes.
- Freeze/releases/inference/ledger/original failed guard/stderr/exit witness are pinned through code constants and the exact archive index. Original failure remains exit 1. No new grant, fit, generation, resealing, pipeline resume, or alternate inference is introduced by the recovery diff.
- On the success path, the launcher reuses existing science/chart/Markdown helpers and labels old execution versus corrected reporter identity separately. Manifest and launcher hashes and original failure are included in human/machine outputs. Current Git revision and recovery clocks are added in the recovery receipt rather than substituted into the original freeze.

## Evidence and limits

Read and checked `checks.json` against every recorded log's byte length and SHA-256. All five recorded entries match their logs and report exit 0. The targeted log records **68 passed in 11.46s**; compile, fixed launcher help, source-preservation/admission and diff-check logs are consistent with the report. This is inspection of prior evidence, not an independent test rerun.

Independently hashed the current changed reporter, launcher and reporting lock against their manifest fields; all match. Manifest SHA-256 is `d8c2383dba7240b15f525af549a991280417a304fe86ed8e8b0840b59af721b9`. I did not rehash the 2 GB run or rerun admission; the recorded full-inventory preflight supports that limited claim.

No actual recovered Markdown/JSON/chart outputs exist in this source-gate package. No conclusion is drawn about complete downstream run06 scientific validation, prescribed inference equality, resource limits during rendering, copied replay with original locations unavailable, or final deterministic hashes. Those remain required after an accepted source repair and updated manifest/evidence review. A later unrelated downstream failure must retain its own attempt evidence and receive separate diagnosis.
