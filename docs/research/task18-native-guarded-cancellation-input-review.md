# Independent static input review: guarded cancellation

**SPEC verdict: PASS for the static-input objective.** The reviewed package is `a22354c..ab69e315f0c397ee22d3565baaecffb5e91baace`. I read its full authored diff (261 added lines) once, the binding input brief and adopted amendment, the implementation report and static provenance, then made focused source checks of the frozen worker and the monitor/authority/commands APIs named by the input. This is a source review only: I did not import or execute the input, run native or OS probes, perform numerical work, or run tests. No native diagnostic outcome is claimed.

## Strengths

- The input allocates one survivor case, one `monitor.supervise` call, a 10-second parent clock, and a 4.5-second case with 0.25-second reserve. Its exact `-I -B` worker vector and unchanged worker hash are checked at [control.py:24–53](../../../docs/research/task18-native-guarded-cancellation-control.py). The monitor's original default sampled incremental cap, output cap, and free-disk prerequisite are at `validation/kernel_stage_a/monitor.py:670`; the frozen worker's one-thread setting and sole child socket owner are at `docs/research/task18-owned-root-lifecycle-native-worker.py:25–45`.
- Unique runtime/launch/end/membership/signal/wait records, vector/source accounting, matching launch and owning end, live supervisor proof, and actual SELF/baseline are required at `control.py:62–156`. The source API supplies the launch and end identities at `validation/kernel_stage_a/authority.py:90–102` and `validation/kernel_stage_a/monitor.py:1033–1039,1204–1210`. The monitor's native membership query retains numeric group rows and completeness at `monitor.py:544–629`.
- The group is limited to exactly the socket-identified child and an optional observed root, with nonnegative numeric RSS; query parent and socket parent are retained separately at `control.py:113–121,171–180`. The `STOPPED` foreign-child status and actual costs remain in the full verdict at `control.py:54,88–96`.
- A real successful, non-absent owned signal 9 while the owner is unreaped, ordered before matching wait/end, and integer owning status 0 or -9 are required at `control.py:97–112`. The monitor emits these events around its actual `os.killpg` and owning wait at `monitor.py:1068–1080,1152–1161`. No natural-exit or reparenting conclusion is inferred.
- The controller reads a bounded child JSON line and actual EOF before any fallback or peer close at `control.py:157–180,190–203`. The frozen worker sends that line from its child and blocks on the peer until child termination or controller close at `worker.py:33–45`. Missing EOF enters `NEEDS_CONTEXT`, and fallback is marked unsuccessful.
- The full monitor verdict, artifact hashes, raw membership, selected proof/current-root RSS rows, source baseline/SELF, socket bytes/EOF, and bounded post-cleanup syscall outcomes are retained at `control.py:54–73,120–180,181–188`. The report and provenance accurately label this input static and the old combined survivor failed.

## Findings

**Critical:** None found.

**Important:** None found.

**Minor — source commit label is externally supplied.** `control.py:39` copies `TASK18_SOURCE_GIT` into the result without comparing it with the checked-out commit. A future result's `source_git` string therefore needs allocation-time verification before it is used as a commit claim. The parent and worker byte hashes, monitor hash, exact vector, and actual monitor source events are still retained separately (`control.py:23–32,44–53,62–87`), so this does not make the guarded-cancellation predicate pass on its own. The static provenance's `head_at_check` is correctly labeled as the precommit base, not the reviewed head (`static-provenance.json:4–6`).

**QUALITY verdict: PASS with the minor provenance caveat above.** The single-case control is readable, preserves the original budgets and failed-state handling, and makes EOF a real pre-fallback requirement. Review scope was static; a later separately allocated one-call native run must supply actual evidence before any guarded-cancellation PASS can be claimed.
