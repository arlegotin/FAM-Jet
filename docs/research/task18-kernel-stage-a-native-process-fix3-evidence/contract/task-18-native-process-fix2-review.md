# F1: ADDRESSED. F2: ADDRESSED.

**SPEC: Issues found in new fix behavior. QUALITY: Needs fixes.** The original late-inner failure-accounting defect and adjacent emergency-refusal omission are corrected. One new ordering dependency in the numeric prepass can attribute post-authority RSS to the full-RSS authority phase; it needs a focused correction before accepting this fix.

Scope: `6ba6100de56ad983920a07f067e6f460840081b9` → `1b0bb18aed81bcb88a0faec5f6d56397fb2de5d7`, F1/F2 and new breakage only. Earlier accepted I1 mechanisms, old preflight findings and the held lifetime design were not reopened.

## Per-finding dispositions

### Important F1 — ADDRESSED

`validation/kernel_stage_a/monitor.py:344` adds a separate numerical cursor over new complete source-journal rows. It retains the numerical values at `:369` before moving that cursor, independently of declaration/completion copying. `:427` performs this pass before semantic ingestion, and `:526` attempts bounded final numerical recovery before semantic finalization. Thus failure copying an earlier witness no longer prevents the ordinary already-written four-row sample from reaching RSS accounting.

`tests/test_kernel_stage_a_native_process_fix2.py:15` exercises declaration-cap, completion-cap and witness-serialization failure with the outer sample missing the inner observer. The retained verdicts in `docs/research/task18-kernel-stage-a-native-process-fix2-evidence/declaration_cap/monitor.json:1`, `completion_cap/monitor.json:1` and `serialization/monitor.json:1` each report absolute/aggregate/conservative RSS980, numerical source completeness true, and identity completeness false. The tests check the inner observer's full RSS900, unresolved role, bounded output and returned/durable agreement. This directly covers the prior finding rather than merely changing its expected failure message.

`validation/kernel_stage_a/monitor.py:350` detects source shrinkage; partial rows remain pending and fail final recovery. Deadline/storage failures set incomplete numerical accounting and a FAILED result through `:376` and `:433`. Tests at `tests/test_kernel_stage_a_native_process_fix2.py:60` and `:82` and their saved specimens retain known RSS70 without inventing the unavailable RSS900. This follows the root's explicit incomplete-accounting ruling.

### Minor F2 — ADDRESSED

`validation/kernel_stage_a/monitor.py:482` retains raw completeness, refusal count/RSS and source-accounting completeness in the independent emergency commitment. The strengthened existing control at `tests/test_kernel_stage_a_native_process_fix1.py:242` asserts those labels. `docs/research/task18-kernel-stage-a-native-process-fix2-evidence/minimum/monitor.json:1` contains `raw_identity_complete:false`, one refused observation and RSS70 while retaining its 512-byte reservation. No cap increase is introduced.

## Strengths

- The new cursor does not authorize identities, cache image proof, create another journal, or repeatedly scan settled history. `validation/kernel_stage_a/monitor.py:344` limits each pass to the current source byte boundary and checks the original deadline per row.
- `validation/kernel_stage_a/monitor.py:333` and `:393` distinguish an already numerically accounted source sample from a new direct sample. Semantic copying and classification remain separate; failure to copy proof is explicitly labeled instead of being repaired with source numerical data.
- `validation/kernel_stage_a/monitor.py:565` exposes numerical completeness separately from identity completeness. The saved failed recovery specimens and tests assert this distinction.
- The diff changes only the external monitor, its README and focused tests, plus technical records. Authority/commands, exact initialized inventory, native identity policy and the scientific protocol are not changed.

## New fix breakage

### Critical

None identified in this scoped review.

### Important N1 — The numeric prepass uses semantic phase state before consuming the corresponding phase-end event

**Locations:** `validation/kernel_stage_a/monitor.py:294`, `:295`, `:344`, `:369`, `:427`.

The newly reordered source pass invokes `numeric()` on all new source samples before `semantic_events()` consumes any of their preceding source events. But `numeric()` is not independent of semantic state: when `phase['active']` is true, it immediately raises `authority_worker` from the root's RSS and records that value as authority-phase RSS. These maxima are monotonic and cannot be corrected after the later semantic `authority_end` is read.

If authority is currently active and the next source batch contains `authority_end` followed by the stage's post-import `observer_sample` and baseline, the prepass processes the post-authority sample under the stale active phase. It can permanently include import/baseline RSS in the full-RSS authority charge, rather than treating that sample at its actual post-authority boundary. This can produce an incorrect memory-cap stop. The event sequence is legitimate: the focused unchanged call-site check at `validation/kernel_stage_a/__main__.py:34` shows `authority_end` is emitted before entering `scientific_worker`, whose imports and `record_baseline` follow at `:10`–`:16`.

**New-versus-existing scope:** the new defect is the prepass's direct use of stale semantic phase state, not a broad finding against every earlier `charge()` transition. In a state where authority start has been observed but the root has no settled authority-worker RSS role—for example, the authority interval was not captured in a root RSS observation—the previous semantic path consumes `authority_end` before `numeric()` sees this source sample; the new path updates `authority_worker` first. Where an older authority-worker role already exists, separate pre-existing charge behavior may overlap the symptom. This review does not reopen that older behavior or claim every possible baseline inflation originated in round2.

No native memory measurement or reproduced failing test is claimed here; this is a source-ordering finding. The new four-row controls do not contain an authority transition, and existing successful tests do not establish this missing ordering case.

**Required correction:** keep the early numerical recovery phase-independent—retain raw numerical maxima and full conservative failure costs without using an out-of-date semantic authority flag. Apply phase-specific resource attribution later using the sample interval and the ordered authority boundaries, while preserving numerical recovery when copying those boundaries fails. Add a focused synthetic authority-end-plus-baseline batch control, including no prior settled authority-root RSS role, and assert that post-end baseline RSS cannot raise the authority-phase peak. Preserve the original cap, strict identity policy and the newly passing F1 cases; no native/scientific rerun is required.

### Minor

No additional Minor defect identified. F2 is closed.

## Checks, evidence and limits

- Read the fix2 requirements, full prior fix1 review, full fix2 implementation report, executable/test/documentation diff and relevant saved verdicts. Used the supplied diff for line references and retained test summaries; no Git regeneration or source edits were performed.
- One named, focused outside-diff check: to establish whether N1's authority-end/post-import-baseline ordering is a real producer sequence, read only the matching `authority_end`/`record_baseline` call-site context in `validation/kernel_stage_a/__main__.py`. No broader unchanged-code review was performed.
- `docs/research/task18-kernel-stage-a-native-process-fix2-evidence/final-focused.txt:1` records **58 passed, 24 deselected, 2.60 s**. Retained RED/GREEN summaries match the reported sequence. No tests, probes, benchmarks, native/scientific runs or package checks were repeated.
- Artifact hashes, 121-file inventory, 48 source-to-durable mappings, eight specimen byte counts, clean main, unchanged prior evidence and package identity are controller-provided verifications. This review did not duplicate those checks. Preserved pytest whitespace/reserved padding and documented packaging exit2 remain distinct from source-only exit0.
- The earlier native compatibility observation remains about its explicitly earlier dirty snapshot. This fix establishes no fresh native runtime identity, full native Stage A pass, ordinary-reader viability, scientific readiness or release. The separate lifetime design stays HELD; conservative later-Python-ESRCH failure and all scientific nulls remain unchanged.

## Scoped verdict

**F1 ADDRESSED; F2 ADDRESSED. New-breakage check: N1 needs a focused correction. SPEC: Needs fixes. QUALITY: Needs fixes.** No out-of-scope acceptance or scientific release is granted.
