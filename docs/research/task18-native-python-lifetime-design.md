# Task 18: source-owned Python lifetime proposal

Unadopted design, 2026-10-18. Scope is the normally exiting Python prerequisite at root-supplied clean base `a0353ba6cb51b453e49929aa7c7d0a48b3f86ace`. Read only the targeted monitor/authority/commands code, stage caller, and reader `clean_read` launch. No Git command, probe, test, scientific execution or source edit was performed. The separately assigned I1 history fix and current strict per-sample Python policy remain unchanged.

## Recommended rule

Permit an `ESRCH` sample of an exited Python worker to receive **source-owned lifetime attribution** only when the exact launch generation has both a successful applicable image proof and a matching trusted-parent completion witness. This is a narrow extension of the helper witness contract. It does not turn old PID evidence into proof of the current sample's image, and it does not admit Python solely because its parent or executable name looks familiar.

Require the successful proof; do not add a second, weaker Python route accepting a launch artifact without ever observing that generation's actual framework image. A process that exits too quickly to supply that proof remains unresolved and fully charged. The added rule addresses an ordinarily observed worker that exits between `ps` row collection and image lookup.

## Minimal generation contract

Use one source-owned launch record per existing stage/setup root and per reader, with these fields:

- Unique `launch_id`, PID, actual parent PID, role (`owned_root` or `reader`), exact launch vector/hash, and pre-`Popen` monotonic `launch_start`.
- Resolved launcher artifact path/hash, separately from the expected runtime image path/hash. Both must match the already verified runtime identity. Recheck the launcher artifact immediately before launch; the framework mapping remains runtime-derived, never guessed from its path.
- A completion record naming that same `launch_id`/PID/parent, `reaped=True`, return code, and post-wait `completion_end`. This timestamp is an observed upper bound on exit/reaping, not the exact kernel exit time. A timeout or forced termination remains visible and cannot become successful worker execution.

The supervisor owns the root `Popen` already. Mint its witness around that exact `command`; do not add another root-command pattern. The parent worker owns reader creation. Replace only its `subprocess.run` dispatch with equivalent `Popen`/`communicate` ownership so it can emit `python_worker_launch` immediately after obtaining the PID and `python_worker_end` immediately after reaping. A UUID or existing launch-ID construction identifies the source operation; it is not a kernel birth token.

Validate the reader vector against the exact existing `reader_command(root,event_path,candidate_deadline)` and its current candidate range. The supervisor binds the reader's parent PID to its one owned root generation when ingesting the witness. No generation token, extra control input, history, reference data or new numeric request field needs to enter the reader. Reject duplicate IDs, unmatched completions, inconsistent parents, overlapping reader ownership and more than one launch generation for a PID within this supervision. Refusing observed PID reuse is the smallest safe policy while accounting and baselines are PID-keyed; supporting reused PIDs would be a different change.

## Applicable image proof, without post-reap borrowing

For the root, a successful exact native sample can establish the generation proof while its sole owning supervisor has not reaped that `Popen`. The supervisor must track this ownership condition explicitly. A successful lookup made after reaping cannot establish it, even if its path/hash matches.

For a reader, use its existing `record_baseline()` self sample. That function already calls `process_tree(os.getpid())` and emits an `observer_sample` before the baseline. Extend that diagnostic event with the trusted emitter PID and identify its self row. In the sealed source, the emitter executes its own image lookup before emitting the event, so its PID cannot have been reaped and reused during that lookup. Other rows in the event do not inherit this guarantee.

Bind this self row to exactly one parent launch witness by PID, exact parent/display, sample/lookup times and the no-reuse rule. Require `image.status == ok` with the sealed runtime image path/hash, and a lookup interval within that source lifetime. The baseline must belong to the same generation and retain the existing post-import/pre-allocation boundary. The event may arrive before the parent's launch line; retain it as bounded pending evidence until their unique join is available. A generic previous outer sample or a bare baseline PID is insufficient for reader generation proof.

The proof record retains its original lookup interval and evidence origin. A later ESRCH row is labeled, for example, `image_evidence=unavailable_exited`, `launch_evidence=source_owned_python_lifetime`, plus `launch_id` and a reference to the earlier generation proof. Do not rewrite the ESRCH row to `kernel_image`.

## Exact ESRCH admission and failure behavior

Every admitted exited row must satisfy all of the following:

1. The native error is specifically `ESRCH`; no permission error, path/hash failure, malformed result or other native failure qualifies.
2. Its PID, parent and raw command display match that witness's exact source vector and verified runtime mapping. Root/reader role and candidate/authority timing constraints still apply.
3. The sample interval overlaps that generation's observed lifetime. A row wholly before launch or wholly after completion fails. The applicable successful proof ends no later than this ESRCH lookup begins. There is exactly one compatible generation.
4. The source parent has completed/reaped that same child and emitted the matching end record. A missing end can be pending only inside the existing deadline; final unresolved evidence stops the run.
5. No sample or event for the generation contradicts its image, hash, command, parent or ownership. A later successful matching observation must never erase a prior mismatch. An observed duplicate/reused PID remains a stop, not a reassignment.

Preserve each raw row and all RSS before attribution. While completion/proof is pending, retain the conservative full-RSS charge; unresolved or contradictory evidence keeps baseline zero and stops. Once admitted with its correct baseline, the worker retains the existing worker accounting semantics; historical absolute observations and any already-established conservative cap violation remain. This rule must not reset peaks, grant a new deadline, add a retry/read dispatch, or rescue failed process execution. Missing/delayed events can therefore still cause conservative stops.

This is sampled evidence under trusted sealed-source launch/lifetime semantics. Source timestamps bracket observation, not kernel birth/death precisely. A unique source ID and a prior image proof do not prove that no unsampled exec occurred, and formatted `ps` display does not certify arbitrary argv bytes. If continuous kernel identity proof is required, this extension cannot supply it.

## Concrete change boundary and dependencies

- `authority.py`: a narrowly named Python launch-witness constructor reusing the existing artifact/hash and launch-ID machinery, with explicit launcher-versus-image fields. No generic process registry.
- `monitor.py`: root launch/reap witnesses; trusted self-row emitter metadata in `record_baseline`; validation/join of reader launch/end records; bounded generation proof and pending-completion state; the ESRCH rule and honest report evidence. Add this state within the separately fixed history/output bounds; do not duplicate or redesign I1.
- `production.py`, only `clean_read`'s owned dispatch: expose reader PID with `Popen`, emit launch/end, preserve the exact vector, environment, stdin bytes, file outputs, working directory and return-code handling. Wrap the owned operation in the existing single `ledger.call('read_dispatch', ...)`. Recompute the remaining original deadline after witness work; timeout/error cleanup kills and reaps, records truthful completion, then propagates failure. No second launch and no altered read counters.
- `commands.py` and `__main__.py` need no behavioral change. `reader_worker.py`, numeric request/response, production `famjet`, factors, fixtures, mathematical code, dependencies and source guards remain outside scope. Focused external tests/notes accompany the eventual change.

Adoption requires a separate root ruling and implementation release after I1 closure. Updated external files require their ordinary source/authority verification; this proposal grants no seal, factor construction, reader-science or integration release. The extra event/proof state, file hashing and dispatch bookkeeping consume the existing output, memory and time budgets. The normal-exit controls below are still required; the earlier held-open checks establish no completion behavior.

## Small nonnumerical controls to run only after separate release

First use deterministic synthetic evidence to check one generation with valid proof then ESRCH/end, delayed launch/end ordering, missing proof/end, non-ESRCH errors, changed parent/display/image, out-of-lifetime samples, duplicate PID generations and failed/timeout exits. Assert raw RSS retention, correct baseline binding and unchanged dispatch counts/caps. Include a successful lookup after reaping which must not become generation proof.

Then run one bounded native control for each exact production vector, without any numeric request:

- Root: hold the exact stage vector in its existing seal FIFO read; obtain a live, unreaped-owner image proof. Complete the stream with an invalid seal such as `{}`. It returns through the genuine refusal path with code 2, normally, before backend work. Record its launch/end and confirm normal-exit attribution independently from its necessarily failed stage verdict.
- Reader: launch the exact reader vector from the trusted owned-dispatch harness with stdin held open and no bytes sent. Wait only within the short test deadline for its existing baseline/self-image event, then deliver EOF. Empty input makes JSON decoding fail before profiling or numeric work; allow the interpreter to exit naturally and the parent to reap it. Its nonzero return must remain a reader failure, while its identity/lifetime is attributable. No model, request, read or factor is constructed.

For each, use a test-only synchronization seam after a genuine `ps` row has been captured but before its image lookup: permit natural exit/reaping, then call the real image lookup for that retained PID and require actual ESRCH. This makes the exit case deterministic without inventing a successful native image or using a sleep race. A watchdog may kill a stuck control, but that outcome fails the normal-exit check. If the platform returns something other than ESRCH, record it and stop; do not widen production acceptance. All test artifacts/events remain under the test's small fixed budget.

These controls demonstrate normally completed OS lifetimes and truthful identity handling, not successful numeric readers or a complete Stage A run. Their deliberate nonzero exits are essential to keeping genuine worker entry paths nonnumerical. No controls have been executed for this proposal.
