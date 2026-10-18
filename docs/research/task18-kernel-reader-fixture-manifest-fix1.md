# Fixture-manifest F1 response — text-only round1

18 October2026. Addressed the independent finding **“F1 — Medium: explicitly separate stored-state reader correctness from source-state/end-to-end failure.”** The full finding and precise remedy were read, and the original [review](task-18-kernel-reader-fixture-manifest-review.md) remains unchanged. This records a prospective clarification under root's explicit pre-output ruling, not adoption, implementation, numerical evidence or a claim of reviewer reapproval.

## Preserved identity/history

* Reviewed manifest SHA256 before this correction: `4fdaab25ec6ba4f4508268c48965ea686496af6e264cdb28803c545085f60f90`.
* Manifest SHA256 after this correction: `bef00e8ff086e7b902956550c0e0bde5173b46acc49d50994f9b57cd8973310b`.
* Unchanged independent review SHA256, verified before and after: `50c4dbf6f721accbdb90d0566ddee960e42f599b49da4ff0c68fc17bb660c51b`.

## Exact changed paragraphs/blocks

The following line anchors identify the exact changed text in the after-SHA manifest; no fixture, transform, rate, ridge, epsilon, floor, sum order or resource-table value was edited.

| After-manifest location | Exact paragraph/block identification | Correction |
|---|---|---|
| [Line77](task-18-kernel-reader-fixture-manifest-draft.md#independent-reference-and-decision-gates) | Paragraph beginning `Require80/160 agreement` | Preserves original comparison tolerances; assigns precision/residual/engine failure to whole-stage stopping and leaves dependent checks unverified. |
| Lines79–90, `Prospective acceptance matrix — F1 clarification` | New definition paragraph, four-row matrix and paragraph beginning `Thus a correctly decoded but degraded supplied state` | P versus supplied-snapshot reference(a) gates reader arithmetic; (a) versus event reference(b) measures source fidelity; P versus(b) remains strict end-to-end comparison. Source failures retain FAILED/end-to-end FAILED and prohibit global Stage A PASS. Equal decisions do not excuse finite-output differences. |
| Line92 | Paragraph beginning `Eligibility uses finite inputs/results` | Stable differing source/event reference decisions are failed source/end-to-end evidence; reader decisions are tested against(a). Unresolved reference decisions stop the whole stage. |
| Line100 | Paragraph beginning `Candidate order is fixed` | Direct reader arithmetic/decision mismatch stops that candidate. Source-only failure permits remaining original reader-diagnostic slots while retaining failure. Reference/common/resource failures stop all work; transform discrepancies use the same attribution. |
| Line115 | Paragraph beginning `These are conservative` | Continuation consumes only existing slots/caps. Hard maximum768 includes timing; no replacement, retry, comparison rerun or cap extension. |
| Line123 | New paragraph beginning `F1 is a prospective clarification` | No existing kernel-gate waiver or repair of the old epsilon1e-8 trained failure. No automatic Stage B; later root must assess scoped results, ordinary source applicability and all failures. Structured work continues unchanged. |

The complete changed wording is retained in [the amended manifest](task-18-kernel-reader-fixture-manifest-draft.md), bound by the after SHA above. Source attribution must follow evidence; passing isolated-reader checks cannot erase source/end-to-end failures, and actual direct comparison results remain visible even if a prerequisite prevents certification.

## Verification and remaining status

Read the complete finding/remedy, reviewed the changed paragraphs and stopping/resource clauses, and recorded before/after document SHA256 values. **No tests were run because this correction is TEXT ONLY.** No calculations, fixture generation, source/config/Git edits, implementation, models/data access, performance work or agents were used. Only the ignored manifest and this ignored response were written. Row30 and its ordered FP64 stress remain intact; original numerical tolerances and all workload/cap values remain intact.

Manifest remains UNADOPTED/UNRELEASED with null execution fields blocking. Independent follow-up review and any later adoption/release remain pending; no global Stage A result or performance result exists here.
