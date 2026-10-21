# One-use binding witness draft — source-only preflight

**SPEC: YES. BUILDABLE: YES within the adopted root Publication boundary. No blocking finding. HOLD: this is not source acceptance, allocation, native qualification or execution permission.**

Reviewed only the new wrapper draft, adopted terminal-cost protocol, terminal-publication amendment and frozen a993cad `finalize_terminal(plan, root, exit_witness)` interface. Confirmed draft identity: 3,530 bytes, SHA256 `cb62d3d0c63e225981d8f2b666bdc92b9dda166eb3d8468dc31575914b6c0d13`. No wrapper/product import, test, AST rerun, subprocess or native execution occurred. Source fix2 and the broader adapter were not reviewed.

The helper implements the requested witness contract:

- Lines 33–47 validate the closed plan, require binding with qualification=null, bind the fixed preparation path, match the exact five-element isolated parent argv and existing vector hash, and compare its source bytes with the sealed witness Ref.
- Lines 49–60 create an exclusive once marker and exclusive parent log files, apply the sealed environment, check the original deadline, perform exactly one Popen, and obtain returncode from the actual wait. Launch/reap timestamps bracket that invocation; the recorded PID belongs to the launched parent. There is no retry or invented successful exit.
- Lines 61–69 build the prescribed ExitWitness with both semantic Plan and raw Plan-byte hashes, save and verify it before calling the finalizer, then retain the finalizer result. The call matches the frozen stdlib interface and occurs after the parent has exited. A nonzero parent still reaches finalization so failed evidence can be retained.
- Lines 70–76 report parent outcome and pending terminal status; wrapper exit0 requires both parent exit0 and ELIGIBLE_PENDING_PUBLICATION. The helper does not create RootInvocation/Publication or claim its own observed exit. Exceptions propagate as failed wrapper execution; the once marker remains.

**Nonblocking publication-accounting detail:** `save()` at lines 20–29 does not itself check the allocation cap/deadline. In particular, `witness-result.json` and final stdout are written after the finalizer returns, so the returned `charged_output_bytes` and `receipt_seconds` are intermediate observations. Root must use the adopted post-wrapper byte/time observation, including both witness JSON files, parent/wrapper logs and any retained temporary files; it must reject exhausted reserves, late completion or unsuccessful writes even if an earlier terminal record survives. This is already required by the adopted Publication contract and does not make the helper's pending status reusable on its own.

Promotion of these exact bytes remains conditional on product-source acceptance, a separately pinned one-use source and an actual allocation/release. No concrete runtime identity, caps, reserves or clock has been accepted by this preflight.
