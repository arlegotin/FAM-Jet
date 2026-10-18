# Independent scoped F1 re-review — 18 October 2026

**F1: ADDRESSED.**

**Contract/spec compliance: APPROVED.**

**Technical quality: APPROVED.**

No new load-bearing defect was found in the correction. These are prospective text-review verdicts only; they do not adopt the manifest, authorize implementation, certify any numerical result or release a stage.

## Reviewed scope

Read `task-18-kernel-reader-fixture-manifest-fix1.md` and the corrected `task-18-kernel-reader-fixture-manifest-draft.md`, focusing on F1's acceptance matrix, threshold decisions, failure attribution, continuation and resource boundaries. The version is identified in the request and fix report by SHA256 `bef00e8ff086e7b902956550c0e0bde5173b46acc49d50994f9b57cd8973310b`; no independent hash calculation was performed in this text-only review. The unchanged design was not broadly re-reviewed.

## Why F1 is resolved

The revised matrix expressly assigns production versus the independent reference on the exact supplied snapshot to isolated reader correctness. It separately retains supplied-state versus event-sum source fidelity and production versus event-sum strict end-to-end results. The comparisons include finite values even when eligibility decisions agree, which closes the specific gap identified in F1.

Source-state failure cannot be erased by a passing reader check or an accidentally passing direct end-to-end comparison. It retains a FAILED status, blocks source/end-to-end certification and prohibits a global Stage A PASS. Conversely, source degradation alone cannot be reported as a failure of correctly executed reader arithmetic. Cause attribution must follow the retained evidence rather than be assumed from the fixture name.

The prospective continuation ruling is compatible with these distinctions: remaining prelisted slots evaluate the decoder on supplied states while preserving source/end-to-end failures. They do not certify the failed source path or release a dependent population experiment. Direct reader mismatch stops the candidate; reference precision/engine/residual failure, unresolved reference decisions and common identity/isolation/resource failure stop the stage. The manifest expressly preserves ordinary source-applicability assessment before any further release.

No tolerance, fixture, row30 magnitude or summation order is relaxed. No new slot, retry, replacement, repair or expanded resource allowance is granted. Continuing diagnostic collection consumes only the existing inventory and caps, including the hard total of768 production reads. This is a pre-output clarification of an unadopted contract, not retrospective acceptance of a failed result. The old trained epsilon1e-8 failure and the running structured program remain unaffected.

## Verification limits and remaining boundaries

No tests, calculations, fixtures, source/Git changes, numerical or performance work, data/model/protected access or agents were used. This ignored review is the only edit. Actual source-state error, reader agreement, reference stability, guard outcomes, failure attribution, inventory accounting and resource compliance remain unverified until separately authorized implementation and evidence exist.

Null execution fields remain blocking. Scoped reader success alone cannot release Stage B; root must review actual completed/stopped scopes, ordinary source applicability and all failures under the stated later decision boundary. No global Stage A result, implementation approval or scientific outcome is established here.
