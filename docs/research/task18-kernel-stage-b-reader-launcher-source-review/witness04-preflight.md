# Binding04 and panel04 witness drafts — scoped static preflight

**SPEC: YES. BUILDABLE: YES within the previously reviewed helper logic and root Publication boundary. No new helper blocker. HOLD: no source promotion, allocation, admission, or release is authorized here.**

The binding04 draft is 3,552 bytes, SHA256 `f7b5cba67e27364a8d2a5f77593470d95395705fb7c2da7cd86bc4c7d7205d4e`. Its complete diff against tracked binding03 changes only `binding-03-prep` to `binding-04-prep` in the fixed Plan path and `binding03` to `binding04` in the error text. The binding scope/null qualification guard is unchanged.

The panel04 draft is 3,550 bytes, SHA256 `ae3425416c6de6e2df27782fab3fd0180ffec9849f66065598154bc1dfb7c0ec`. Its complete diff against tracked panel03 changes only `panel-03-prep` to `panel-04-prep` and `panel03` to `panel04` in the corresponding literals. The panel scope/non-null qualification guard is unchanged.

Each fixed path remains tied to the preparation-output identity check and sealed parent argv. The exclusive once marker, single launch and actual wait, ExitWitness, post-exit finalizer, and wrapper zero-exit rule are byte unchanged. Root still owns observation of the completed wrapper and post-wrapper byte/time accounting in RootInvocation and Publication before qualification. Earlier paths remain untouched. This review did not assess the active reader-launcher source fix; root retains source approval, exact-byte promotion, fresh binding, and admission gates. No draft was imported or run, and neither is allocated.
