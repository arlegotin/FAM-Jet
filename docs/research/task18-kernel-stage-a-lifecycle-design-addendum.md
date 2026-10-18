# Adopted cleanup observation design

Design only. Control03 read fully: signal-zero succeeds live but returns EPERM for the exited/unreaped root; actual image/getpgid ESRCH and owning wait 0 follow (0.046655791 s). No further signal-zero workaround is proposed.

**Keep normal `PS_ARGV` unchanged.** Add exactly:

`['/bin/ps','-axo','pid=,ppid=,pgid=,rss=,comm=,args=']`

Use this only in a supervisor-owned cleanup-observation phase. Require the existing hashed `/bin/ps` artifact, exact vector/hash, unique source-owned launch ID, supervisor parent PID, real helper PID, launch/completion times and actual reap. Classifier admission requires that exact vector plus this internally established phase and declaration; worker-emitted phase claims, altered vectors and ordinary sampling cannot authorize it.

**Preserve group ownership before releasing the root PID.** Remove native loop-header polling that could reap before cleanup observation. Normal native sampling continues while the owning Popen remains unreaped. A root-absent/ESRCH terminal sample, cancellation, or failure enters cleanup. First retain numerical rows and any valid current same-generation root image proof while unreaped, under existing identity-completeness checks. Then enumerate while the owning root PID remains reserved. Retain this unreaped ownership boundary explicitly. No new signal may rely solely on an already-reaped numeric PGID. An unexpectedly pre-reaped root with remaining unbound members is unsuccessful cleanup, not permission to guess ownership.

Bound the helper by `min(original_remaining_time, existing_observer_bound)` and remaining output bytes. Drain stdout/stderr with bounded reads; timeout, overflow, nonzero exit, malformed/duplicate numeric rows or incomplete/truncated output invalidate the observation. Always attempt helper cleanup/reap. Retain exact raw output, parse outcome, sample interval and selected membership; empty membership requires a complete successful parse, not absence from a truncated prefix.

Select every row whose PGID equals the original owned root PID, regardless of PPID, plus the observation helper itself. Retain PID/PPID/PGID, RSS and raw identity fields. Account selected RSS numerically before identity decisions; retain helper launch/completion and charge its observer overhead. Charge query logs, raw output, failed artifacts and finalization against unchanged output/time/RSS bounds. No sampling allowance or deadline renewal.

**Decision:** complete empty group → skip SIGKILL; non-root group survivors → required group SIGKILL while root remains unreaped; live root under cancellation → required group SIGKILL. Root-only terminal observation → owning reap, not unconditional group signaling. Unknown/denied/incomplete observation remains unsuccessful; existing ownership still permits cancellation, but no absence claim. In nested finally, attempt bounded owning wait regardless of query/signal failure, then publish exactly one truthful end only after actual integer returncode. Reconcile retained rows after that end. Preserve first violation and separate cleanup diagnostics; neither subsequent reap nor proof resolution erases a cap or denial.

Use synthetic/native seams for deterministic ordering/error tests. After source commit, require a separately authorized bounded native control with a genuine same-group survivor after root exit, alongside empty-group normal exit. Existing timeout/output-cap coverage remains required. No implementation, tests, control, numerical work or setup retry occurred in this addendum.
