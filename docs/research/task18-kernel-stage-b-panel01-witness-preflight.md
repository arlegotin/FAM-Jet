# Panel01 one-use witness draft — static preflight

**SPEC: YES. BUILDABLE: YES within the adopted root Publication boundary. No helper-delta blocker. HOLD: this review grants no source promotion, allocation, execution, or panel admission.**

Compared the unreleased 3,550-byte draft (SHA256 `9e2de41881c7bdb0c44d8e6630747140dc6cdfba5dee2141564af70d0c4e9d38`) directly with the accepted binding02 witness. The source diff contains exactly four substitutions: docstring, fixed `panel-01-prep/plan.json`, the scope/qualification guard, and its error text. No helper import, test, subprocess, native run, or product-source review occurred.

The guard requires `release.scope == "panel"` and a non-null `execution.qualification`; `authority.validate_plan(plan)` runs first and enforces the sealed Plan schema. Thus the wrapper permits the separately released panel scope and rejects a binding Plan or missing qualification. The “full 96/Q8” message describes its intended use; this guard does not itself prove scientific completion. The unchanged parent/finalizer and later qualification admission own that evidence.

The new fixed Plan path is also checked against `execution.preparation_output`. Before launch, the wrapper recomputes the exact five-element parent argv using the lexical project Python launcher, `-I`, bootstrap, `--seal`, and that Plan; it compares the vector and hash with sealed terminal fields and verifies its own source Ref bytes. It creates the exclusive once marker, makes one `Popen`, records the actual `wait()` returncode, PID, launch/reap times, Plan hashes, and argv/hash in the ExitWitness, then calls `finalize_terminal` after parent exit. Its zero return still requires parent exit zero and `ELIGIBLE_PENDING_PUBLICATION`.

The wrapper cannot attest its own final return or approve Publication. Root must observe the completed wrapper, verify terminal commitment, and account for post-finalizer `witness-result.json`, stdout, and other charged preparation/output bytes and elapsed receipt time in RootInvocation and Publication under the original reserves and deadline. Pending terminal status alone is not reusable.

**Minor, nonblocking:** inherited failure strings still say “binding preparation identity” and “original binding deadline.” They do not affect the predicates or evidence. Root retains prospective source/material qualification, exact-byte pinning, release, and admission ownership; no allocation is implied here.
