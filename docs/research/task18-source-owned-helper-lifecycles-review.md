# Independent SPEC + QUALITY review: source-owned helper lifecycles

**SPEC verdict: CHANGES REQUIRED / HOLD. QUALITY verdict: CHANGES REQUIRED.** No native execution or scientific release is supported by this review. No Critical finding; five Important findings and one Minor finding follow.

Reviewed BASE `100bf1c900e955d855267ba86d11c94948dcd3dd`, authored source `34143e8c47728d65c098003724bfc8f1c2a0a5f4`, and evidence HEAD `919c2c93c7b355cb41c239dff034a82645389970` as supplied. I read the complete review brief, implementation brief, adopted amendment, architecture report, implementation report, stopped03 report and named E69–82 evidence. I read the exact authored supplement, including both complete new static control files, rather than rereviewing duplicate pre-edit source snapshots. Focused outside-diff reads addressed actual Popen ownership, parent/proof/baseline integration, source ingestion/finalization, cleanup deadlines, reader rejection and the failed test's teardown. No tests, project/input imports, native probes, numerical operations or subagents were used. The only mutation is this review.

## Strengths and specification coverage

The design direction matches the adopted trusted-source model. `SourceLifecycles` provides common PID/launch-ID collision handling, retained immutable launch fields, matching integer returncodes/reap, finite timing checks, observation overlap and sticky failures. The actual supervisor installs that same registry in `PythonLifetimes`; numeric cleanup also registers into it after its local query validation. Ordinary observer ps, cleanup ps, both Git vectors and readers therefore participate in cross-family collision rejection. The directly owned root still uses its separate receipt route.

Actual ownership paths were inspected, not inferred from JSON: `process_tree` communicates with/kills/reaps its retained `probe` and publishes that object's returncode; `_cleanup_observation` retains its own Popen through bounded capture and wait; `authority.git` emits its launch/end around the same `process`; `production.owned_reader_dispatch` does likewise. Failed ps/Git operations raise, and reader dispatch returns the real nonzero status to its caller. Attribution is appropriately separate from operation success. Historical stopped03 observer ends have no returncode and are not repaired by the new protocol.

The ordinary image branch requires an actual matching `macos.proc_pidpath` lookup. ESRCH requires the native method/reason and ordered finite lookup times. Arbitrary teardown display and positive RSS are admitted only through a declared overlapping lifetime; successful contradictory images, ambiguous rows, wrong parent/artifact/vector, malformed timings and duplicate/reused generations remain negative paths. The pending batch dependencies include parent generations and preserve source/observation ordering. The stopped03-shaped positive controls are meaningful, and RED01 contains behavioral assertion failures rather than merely a missing module.

Resource handling is conservative: `reader_lifecycle` receives zero baseline subtraction; helpers retain full sampled peaks; cleanup readings enter numerical accounting before classification; the final lifecycle record uses null for an unobserved peak. A later favorable join does not lower the already established incremental peak. Genuine reader SELF/live-image/post-import baseline qualification remains separate. Exact reader launch, candidate-derived deadline, one-reader ownership and unchanged closed-request/result/isolation paths remain in place.

The new worker actually invokes both authority Git commands, imports the normal runtime, calls real `record_baseline`, and calls the existing `owned_reader_dispatch` with the real reader vector and `{}`. `reader_worker.main` rejects that request after baseline and before `Trace`, `isolation._worker`, factor or read operations. The parent's expected-error-string/nonzero-status/empty-result checks support that narrow negative operation; the hard-coded zero counters alone would not. The unknown case uses one forked child holding the socket and the success path reads genuine payload/EOF before fallback closes it. Both controls remain static, and the report accurately says the final cover failed and no native compatibility was observed.

## Important findings

### I1 — Parent lifetime validation does not bound the child's owning completion

**Locations:** `validation/kernel_stage_a/monitor.py:291`, `validation/kernel_stage_a/monitor.py:1257`; related `validation/kernel_stage_a/source_lifecycles.py:49`.

Both the sampled helper-parent join and final generation sweep check only that the child's *launch* lies inside the parent's lifetime. Neither rejects a child completion later than the parent's owning completion. The registry's `_end` validates the child's own launch/sample/image bounds, not its owner generation's end.

A concrete static counterexample uses the existing prepared root ending at 14.5, an ordinary ps launch at 12.3, a child completion at 16, and a valid ESRCH row over 13–14. The child passes the local overlap/end checks and `helper_parent`; the final sweep also accepts its launch inside the parent interval. Yet the reviewed source requires the parent itself to wait/reap and emit the helper end before that parent exits. The claimed source chronology is impossible under the actual same-Popen path. A later-arriving parent end likewise lacks a child-completion consistency check.

Validate this cross-generation bound independently of whether the helper was sampled, and retain sticky rejection when the parent end arrives later. Add controlled negative coverage for child-end-after-parent-end, including reordered parent completion. This is consistency checking of the adopted source contract, not a request for adversarial kernel identity guarantees.

### I2 — Never-sampled Git helpers bypass the launch-time authority phase check

**Locations:** `validation/kernel_stage_a/monitor.py:933`, `validation/kernel_stage_a/monitor.py:945`, `validation/kernel_stage_a/monitor.py:1250`; contrasted with the sampled helper check at `validation/kernel_stage_a/monitor.py:358`.

The launch event handler checks that the phase is active when the record is ingested, but does not check `entry['launch_start'] >= phase['start']`. The phase-end handler checks child completion against phase end, and the final registry sweep checks only parent lifetime. The stricter launch-phase bound exists only in `helper_role`, which runs for an observed row.

Consequently a journal with both exact Git operations, valid source IDs/artifacts/statuses, launch timestamps before authority start but after root launch, and no sampled Git rows can settle and emit `source_lifecycle` records. The same launch is rejected if a row happens to be sampled. The contract explicitly covers fast helpers with no live image/sample while preserving phase boundaries; validation must not depend on catching the helper in ps.

Enforce the family phase bounds at declaration/completion/final generation validation and cover never-sampled wrong-phase negatives. The final sweep also uses weaker parent qualification than `helper_parent` (no retained proof/baseline qualification); reconcile or explicitly justify that difference while making family validation coherent.

### I3 — The failed cover demonstrates an unresolved bounded-cleanup limitation

**Locations:** `validation/kernel_stage_a/monitor.py:1237`, `validation/kernel_stage_a/monitor.py:1157`, `tests/test_kernel_stage_a_native_process_fix2.py:98`.

The unchanged partial-journal test failed in cover02 and cover03 with `FAILED`, null owning returncode and a `TimeoutExpired` wait. Both archived verdicts also contain a signal-operation `_MonitorStop('outer timeout')`; neither archive establishes a successful recorded SIGKILL and owning reap. Their outer durations are approximately 88.36 ms and 88.43 ms against an 80 ms allocation. The final cover is therefore **335 passed, 1 failed, 6 deselected**, not an accepted cover with a harmless exception.

There is a concrete scheduling weakness in the inspected code: the loop calls `check()` and then unconditionally sleeps 20 ms. For an 80 ms allocation the reserved cleanup interval is only 8 ms. A sleep begun just before the work deadline can consume that entire reserve and leave the required owning wait with timeout zero. The raw samples are consistent with this explanation, although the archives do not time each sleep and cannot isolate every scheduler contribution. The source truthfully reports incomplete accounting/status instead of inventing success; that is good failure semantics, not proof of complete cleanup.

The test's child loops until a `finish` file exists; this test neither creates it nor installs its own Popen teardown. I found no repository `conftest.py` teardown. The monitor returns after the failed bounded wait, so there is no later owning wait recorded by this task. Root separately reported a current exact-PID query showing neither original child listed; I did not perform that query, and current absence cannot recover historical kill/reap evidence.

This is an existing scheduling path exposed by the required cover, not a demonstrated new registry defect. It still blocks declaring the task verified. Resolve the deadline/cleanup contract and implementation within the original allocation, preserving the failed evidence and assertion. A favorable rerun, extra grace, longer budget or inferred late status would not resolve it. No such execution is recommended or authorized here.

### I4 — Unknown-child PASS does not require the mandated nonabsent SIGKILL

**Location:** `docs/research/task18-source-owned-helper-native-control.py:109`; producer distinction at `validation/kernel_stage_a/monitor.py:1077`.

The control accepts any `cleanup_signal` with truthy `success` and `owner_unreaped`. The monitor also emits `success:true, absent:true` after `ProcessLookupError`. The parent never excludes that absence record, nor explicitly checks the signal number and target root PID. Thus its PASS predicate does not establish the exact nonabsent owned SIGKILL required by the brief; numeric membership plus later EOF cannot convert an absence result into a successful signal delivery.

Require the record's root PID, SIGKILL, successful nonabsent result and owner-unreaped state before the actual root end. Preserve the existing socket payload/EOF-before-fallback conditions. Add a static/mocked negative check for the `absent:true` shape before any separate native allocation.

### I5 — The parent can report PASS after its final artifact exceeds the aggregate output cap

**Locations:** `docs/research/task18-source-owned-helper-native-control.py:126`, `docs/research/task18-source-owned-helper-native-control.py:147`.

The aggregate 64 MiB check runs inside each case before `native-result.json` is written. The monitor allowance subtracts existing destination files but reserves nothing for the final parent artifact, which embeds verdicts and lifecycle records. The final write has neither a size budget nor a post-write aggregate cap check. A destination just below the cap can therefore exceed it during final commitment while `compatibility` remains PASS. This contradicts the unchanged aggregate-output limit even though ordinary small runs may not reach the boundary.

Budget the final artifact within the same aggregate allowance and ensure the committed status cannot remain PASS on cap violation. Do not enlarge the limit or discard retained logs to make room.

## Minor finding

**M1 — Successful commit timing is not retained.** At `docs/research/task18-source-owned-helper-native-control.py:148`, `artifact_commit_end` is added only after serializing the file. It is persisted only on the overrun rewrite. A successful saved result therefore contains a pre-write `end`/`elapsed` but no saved post-write timing, while stdout prints that same pre-write duration. Retain an honest post-commit/caller timing boundary within the original budget; do not claim the saved elapsed includes the commit. This matters to the requested actual clock evidence, not to an invented performance benchmark.

## Quality and test assessment

The small stdlib registry and shared failed set improve reviewability, and preserving raw evidence/status distinctions is strong. The main quality problem is that complete generation validation remains distributed between sampled classification, journal event handlers and a weaker final sweep. I1/I2 are consequences of that split. Centralizing or consistently invoking the finite family/owner validators would address the specific gaps without expanding this into an OS security framework.

The changed existing tests generally track the explicit amendment: arbitrary unavailable-image displays and retained parent proofs are now permitted; reader lifecycle alone is full-charge rather than a baseline-bearing worker; fixture returncodes/native method/timestamps represent the new protocol rather than backfilling history. The root receipt negatives remain separate. Replacing the early authority-peak assertion with full-charge/incremental assertions is consistent with pending attribution, though it no longer verifies that specific authority metric in that pending case.

Focused 51-pass evidence and meaningful RED are useful but do not cover the counterexamples above or erase the failed affected cover. The registry-only completion-before-declaration tests exercise storage order, not every journal-ingestion ordering; actual helper journal order is constrained by the reviewed writer paths. No universal native compatibility claim follows. The static control covers actual family invocation and one unknown-child cancellation shape; it cannot guarantee naturally observing every teardown display/interval schedule.

## Cannot verify here / root responsibilities

- Independent byte hashes, current original/archive equality, full BASE-to-HEAD scope and protected/math/lock preservation are delegated to root's separate verification. I inspected the authored supplement and reported metadata; I did not rerun those checks.
- No native input has been executed by this reviewer. Runtime duration, actual sampled display/ESRCH behavior, actual family joins, resource peaks, reader rejection and cancellation/EOF behavior remain unobserved for these new inputs.
- No later historical owning returncode or signal success can be recovered from the two failed test verdicts or root's reported current process absence.
- Intermediate revisions were not retained per attempt, as disclosed in the implementation report. Logs establish the reported attempt outcomes, not a complete source snapshot for every intermediate diagnostic run.
- Root must separately allocate source/destination/clock and authorize any future native run after resolving review findings. Scientific, model/factor/read and protected work remain unreleased. Earlier failures, including stopped03 and this failed cover, remain unchanged.

**Disposition: HOLD for source/control correction and the unresolved verification boundary.**
