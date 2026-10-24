# Binding03 and panel03 witness drafts — scoped static preflight

**SPEC: YES. BUILDABLE: YES within the previously reviewed witness logic and root Publication boundary. No new helper blocker. HOLD: neither draft is promoted, pinned, allocated, or released by this review.**

The binding03 draft is 3,552 bytes, SHA256 `4729c6a9ad30639e9e8282ea45b6a8cb6a83b3323430415863d4b1c3dd1ec9e7`. Against the reviewed binding02 helper, its complete diff changes only the fixed Plan path from `binding-02-prep` to `binding-03-prep` and the error text from `binding02` to `binding03`. Its unchanged guard requires binding scope with null qualification.

The panel03 draft is 3,550 bytes, SHA256 `dfb2ce273c6980e874f94376251a3a44af1d89834f6e2ee968dbde00e0c102d5`. Against the reviewed panel02 helper, its complete diff changes only `panel-02-prep` to `panel-03-prep` and `panel02` to `panel03` in the error text. Its unchanged guard requires panel scope with non-null qualification.

Each fixed Plan path remains paired with the unchanged `execution.preparation_output == str(PLAN.parent)` check and sealed five-element parent argv. All remaining bytes retain the exclusive once marker, single parent launch and actual wait, ExitWitness, post-exit finalizer, and wrapper zero-exit predicate. Root must still observe the completed wrapper and approve RootInvocation/Publication using post-wrapper byte and time accounting; pending terminal status alone is insufficient.

Old once-marker paths remain untouched. This review did not assess the active dtype source fix or repeat product/source qualification. Root owns source acceptance, exact-byte promotion, new binding qualification, fresh admission, and any later release. Neither draft was imported or executed; no allocation exists.
