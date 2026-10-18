# Independent review: source-owned terminal rows

**NEEDS_REVISION.** The proposal is suitable in scope and honestly limits its claims, but the observer-helper parent predicate and its pending dependencies need one explicit ruling before adoption. No implementation, test execution, native allocation or source acceptance is certified by this review.

Reviewed the complete proposal, `validation/kernel_stage_a/monitor.py`, the lifecycle brief and deadline clarification, the referenced lifecycle adoption, and the file-control evidence report. The evidence summary suffices; no unrelated process rows or archived global tables were inspected.

## Blocking point: define “qualified parent generation”

The observer-PS family requires “a qualified parent generation or the owning supervisor,” without defining qualification when that parent is absent from the current sample, still live, terminal but awaiting completion, or awaiting its reader SELF/baseline join. These cases are material to the proposed extension. Existing `classify` admits an inner observer through a parent in the current sample's `expected` set; that set requires current exact display and a successful Python image. It cannot implement the new historical-parent route directly.

Reusing the terminal predicate recursively would require the parent's actual completion even for an otherwise valid live parent. Replacing that with merely an accepted launch would allow a never-proved or invalid reader generation to authorize a terminal helper. Looking only at the parent's numeric PID could attach an old parent's proof to a later observed generation. The proposal's general provenance exclusions should prevent those outcomes, but do not select the actual parent predicate a builder must implement.

The pending rule also needs to name this cross-PID dependency. Existing `wake(pid)` and reconciliation dependencies are keyed by the pending row's PID. A helper waiting for its parent's proof/baseline/end is not necessarily reconsidered when that parent changes state. Requiring wakeups only for the helper's matching source witnesses would leave a valid row unresolved or encourage an unbounded history rescan.

**Minimal correction:** specify that an inner PS helper binds to exactly one accepted root/reader parent launch ID, with its correct source relationship, compatible parent lifetime and no failed/conflicting generation. Parent qualification requires an applicable successful historical Python proof with the existing allowed origin; a reader additionally requires its genuine SELF/baseline join. A live parent need not have completed. If qualification relies on a terminal parent observation, that observation must satisfy the full terminal predicate, including actual completion. State whether an absent parent can qualify from those historical witnesses; permitting that is consistent with the proposed source-only limitation, provided it is explicitly adopted. Reject observed contradictory identity, release or reuse rather than borrowing a different generation's proof. The owning supervisor remains the separately direct ownership case.

Index a pending helper against both its own launch ID/PID and the bound parent generation. Wake it on relevant parent launch/proof/SELF/baseline/end/failure changes. Unavailable evidence remains pending under the original deadline/output bounds, then fails closed with conservative charging. This requires only bounded dependency bookkeeping, charged through existing evidence, not a general monitor redesign.

## Resolved builder choices

The other three families are sufficiently specified. Root requires supervisor-owned pre-reap proof; reader requires parent launch/end plus its own tagged SELF and baseline; Git requires its exact declared vector/artifact and the existing authority-phase bounds. Helper source completion must actually say `reaped=true`; ordinary observer witnesses do not supply a return code and must not be rewritten to imply zero.

Implement terminal recognition as a separate source-attribution branch. Both raw fields must remain literally `<defunct>`, RSS must be integer zero, and native evidence must retain the exact ESRCH method/reason and ordered intervals. Historical Python proof must finish no later than terminal sample start and strictly before completion. Exact live-vector matching remains unchanged. Persist attribution in a separate resolution record with proof/completion references, never by replacing raw arguments or treating historical image evidence as current.

“Already-qualified” root-only cleanup must be read as provisional eligibility before owning poll, followed by final qualification after actual end. Before release, require the complete numeric query, sole zero-RSS root member, and all currently available terminal prerequisites. Actual wait/poll zero plus truthful end completes qualification before reconciliation. Report `qualified_terminal_root_only` and `membership_empty=false`. Poll `None`, missing prerequisites, nonroot survivors or an earlier violation cannot become successful cleanup. Required cancellation remains attempted under retained ownership even after budget exhaustion.

## Focused acceptance controls

Require positive controls for all four families and parent-dependent observer wakeups, including a live parent, absent historically qualified parent if adopted, and terminal parent awaiting end. Negative controls must cover missing/foreign SELF, missing baseline/proof/end, false reap, wrong parent/vector/hash/launch ID, duplicate/reused PID, contradictory image, nonliteral markers, nonzero RSS, other native errors, stale/nonoverlapping lifetimes and incomplete provenance. Include child-before-parent evidence arrival and parent failure while the child is pending.

Supervisor controls must establish sample/proof → unreaped membership → actual poll/end → terminal resolution, root-only versus empty membership, nonroot cancellation before release, poll `None`, and sticky prior cap/failure. Preserve all resource, phase, selection and scientific guards.

The stated limitations adequately disclose source reporting bounds, parent-witnessed ownership, interval capture uncertainty and unobserved exec/reuse ambiguity. They support conservative sampled accounting, not OS birth identity or security containment. The retained root case supplies design motivation only; reader, helper and survivor compatibility still require separately authorized verification.
