# Stage B terminal witness and allocated cost protocol

DESIGN ONLY / HOLD. Corrects only I2/I3 against frozen `e9007839802bcb730af76ff8d0c72c9b2ba98f4f`. Preserve monitor/native algorithms and binding/full96-Q8 scopes. No allocation follows.

## Ownership and minimum interface

Keep implementation in existing `__main__.py`, `authority.py`, `driver.py`. Add stdlib `finalize_terminal(plan,root,exit_witness)`; it performs no model import, science, launch or cleanup. A separately pinned, one-use root wrapper launches the existing Stage B parent exactly once, observes `Popen.wait()` returncode, and calls the finalizer only after that actual exit. The parent continues using unchanged supervise for the scientific worker. No additional CLI scope, identity algorithm or generic launcher.

Parent argv is exactly `[runtime.executable,"-I",ROOT/validation/kernel_stage_b/bootstrap.py,"--seal",PLAN]`; ROOT/PLAN use existing canonical substitutions. This five-element vector is distinct from the existing six-element worker vector. The wrapper source and expected parent vector are bound in the later allocation. The wrapper cannot declare its own successful exit: root observes its real invocation outcome and accepts publication separately.

All parent/worker success records are provisional. Replace reusable binding PASS with `PENDING_TERMINAL`; raw scientific `COMPLETED` remains scientific status only. Preserve raw monitor status/returncode and all scientific evidence. Qualification requires the three-part chain: provisional binding record → terminal report → root publication acceptance. Missing/failed publication means no qualification, regardless of an earlier status.

## Closed additions

Use existing Ref schema and strict scalar types: H SHA256, G full Git, F finite number, N nonnegative integer; exact keys, no boolean-as-number. `Failure` is existing phase=finalize failure. Add `Execution.terminal={witness:Ref<python_source>,parent_argv:S[],parent_argv_sha256:H,publication_seconds:F,publication_bytes:N}`; positive reserves remain unallocated. Add `Qualification.terminal:Ref<terminal_report>` and `Qualification.publication:Ref<publication_acceptance>`.

```
ExitWitness={version:1,plan_sha256:H,plan_file_sha256:H,witness:Ref<python_source>,
 parent_argv:S[],parent_argv_sha256:H,parent_invocations:1,parent_pid:N,
 launch_monotonic:F,reaped_monotonic:F,returncode:int,reaped:true}
Terminal={version:1,scope:"binding"|"panel",plan_sha256:H,exit:ExitWitness,
 status:"ELIGIBLE_PENDING_PUBLICATION"|"FAILED",failure:Failure?,
 run:Ref<Run>?,binding:Ref<binding_record>?,monitor:Ref<A_monitor>?,
 allocation_start:F,program_end:F,intervals:Interval[],costs:Cost[],
 campaign_seconds:F,selection:{jet:S?,bank:S?},
 same_plan_bytes:bool,program_output_bytes:N,publication_reserve_bytes:N}
Publication={version:1,approved:true,terminal:Ref<terminal_report>,
 witness:Ref<python_source>,invocation:Ref<root_invocation_record>,
 observed_witness_returncode:0,receipt_commit_observed:true,
 receipt_phase_seconds:F,charged_output_bytes:N,
 within_original_deadline:true,within_publication_budget:true,ruling:Ref<markdown>}
RootInvocation={version:1,witness:Ref<python_source>,plan_sha256:H,
 actual_returncode:int,publication_verified_monotonic:F,
 output_bytes:N,commit_success:bool}
```

RootInvocation is root's retained observation of the one-use wrapper's completed invocation, not a claim authored by that wrapper about its own future exit. Root samples the same host monotonic clock after observing actual return and verifying terminal commitment. Require `receipt_phase_seconds=publication_verified_monotonic-Terminal.program_end`, nonnegative, within publication_seconds, and publication_verified_monotonic<original_deadline. Invocation source/plan/witness identity, returncode, bytes and commitment must agree with Publication; all referenced hashes are verified. Failed/missing invocation evidence cannot produce approved Publication. Never infer timestamps from artifact mtimes. This uses existing root acceptance, not native certification.

## Publication order and failure handling

1. Reserve receipt space/time inside the original allocation. Preserve allocation start before parent verification. The parent commits worker Run/binding artifacts and monitor results, performs plan/output/deadline checks, then exits. It writes no authoritative external-exit record.
2. Wrapper records actual wait outcome, with `allocation_start<=launch<=reaped`. Nonzero exit, changed plan, unsuccessful monitor/common controls or incomplete science prohibits eligibility. Finalizer preserves failed evidence/costs; it never resets completed work to zero.
3. Finalizer validates raw artifacts and interval ownership, commits the final Run/binding record atomically, rereads/hash-checks it, then samples `program_end>=reaped_monotonic`. This sample is AFTER the scientific/monitor/Run commitment, not before serialization. Run version2 adds `cost_scope:"worker_provisional"` and `completion:"PENDING_TERMINAL"`; binding version2 uses status=PENDING_TERMINAL. Terminal costs are authoritative. Eligibility requires successful substantive commitment, same-plan verification, full charged-output check and program_end<original_deadline. Missing artifacts allow only FAILED, never eligibility. Final Run selection remains provisional until terminal acceptance.
4. Construct terminal costs/selection through program_end, write terminal report atomically and verify its bytes. Measure this receipt phase from program_end through report verification and final byte/deadline checks; return its result to the wrapper. Any exception or cap/deadline/reserve failure returns nonzero and, when possible, retains FAILED evidence. Never swallow a failure because rename already succeeded.
5. Root observes wrapper completion and checks actual charged directories, report hash and invocation result before publishing Publication. Require successful commit, actual wrapper exit0, original deadline, receipt seconds/bytes within sealed reserves, and total output≤allocated cap. Without this separate acceptance, ELIGIBLE_PENDING_PUBLICATION cannot be reused. A surviving report after late failure is inadmissible.

Receipt phase is separate measured overhead, never zero or hidden in science throughput. Root acceptance's own bookkeeping cannot self-time its final write; label it external acceptance bookkeeping, outside the measured program/receipt interval, retaining its artifact bytes in custody accounting. No assertion of a self-measured total through that final bookkeeping is permitted.

Charged bytes sum the original output and preparation trees, including witness logs, receipt files and temporaries; avoid double-counting overlapping paths. Publication.charged_output_bytes equals the retained invocation observation after report commit; admission recomputes current charged bytes and requires the same immutable total≤cap. Receipt growth over program_output_bytes must fit publication_bytes. Root acceptance/invocation bookkeeping is external custody, separately retained by Ref byte counts, not silently added to monitored science output.

Before every finalizer atomic write, serialize once and require charged_bytes+len(raw)≤cap, including the temporary copy while an old target exists; check deadline before/after commitment. No retry or overwritten-success repair can bypass failed publication acceptance.

## Cost partition

Authoritative intervals partition `[allocation_start,program_end]` exactly, ordered, contiguous and nonoverlapping. Prepend common startup from allocation start to the first driver interval; append common finalization from the last driver interval through actual worker/parent exit, supervisor cleanup, hashing and final Run commitment. Preserve existing family encode and candidate direct intervals. Binding uses one common interval and costs=[]; report its campaign cost separately. Failed work remains charged. Malformed/missing attribution stops eligibility; retain a conservative all-common failed total rather than inventing direct timings.

Recompute costs only from this final partition: each candidate gets all common time, its family's full encoding time and its direct time; campaign charges every interval once. `authority.validate_completion(plan,terminal,publication)` returns accepted costs after adding publication.receipt_phase_seconds once to campaign and fully to each standalone common cost; retain program and receipt components separately. Recompute exact loss/cost/config-hash selection from preserved complete finite science with these accepted costs; failures select none. Terminal.selection is provisional until this check; consumers must not reuse driver selection or costs. No model/central-metric rerun is needed.

## Hashes and controlled checks

C/D retain adopted sorted compact UTF-8 finite JSON/no newline. plan_sha256=D(complete released Plan); file/Ref hashes cover exact bytes; parent argv hash uses unchanged commands.vector_hash. Terminal embeds ExitWitness; Publication references terminal raw bytes; neither report nor Run references Publication. The DAG is plan→raw evidence→final Run→terminal→publication; no self-hash or timestamp cycle.

Source-only tests use fake clocks/wait/atomic writers: monitor success with parent exit1; late serialization/fsync/rename/cap/deadline failure; successful rename followed by failed verification; missing/forged publication; tampered plan/argv/report; startup and terminal tails; binding/failed totals; overlapping/gapped intervals; exact cost recomputation. Verify no provisional status qualifies and publication failure preserves monitor outcome. No actual process/model/panel test is authorized here.
