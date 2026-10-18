# Fresh independent SPEC + QUALITY review: terminal attribution

18 October 2026. **SPEC: NEEDS_REVISION. QUALITY: NEEDS_REVISION.** One Important finding prevents acceptance of this finite source task. No Critical or separate Minor finding is reported. Native compatibility and scientific readiness remain unestablished independently of this source finding.

Reviewed BASE `d0c9a51e77a2028f6b648c4cfc0889734ec089b5` to HEAD `2fa298a5af3ed78b44f7ea50c56838e11498bffa`, including source `795e4c05f07378fc57accae4ad4012d4d9f57b8b` and frozen future input `fd888972801ba5582ec2413122e9882b4fc68f82`. This is an independent task-scoped review, not the later broad branch review and not a reversal of the accepted earlier lifecycle fixes.

## Important R1: observed cross-family PID reuse bypasses generation rejection

**Locations:** `validation/kernel_stage_a/monitor.py:689` (`register_launch`, especially its condition at 691), `monitor.py:703` (`declaration`), and `monitor.py:267` (Python-priority literal-terminal dispatch). The analogous Python launch ingestion is at `monitor.py:826`.

The new global registry is keyed only by launch ID. It rejects an existing ID or an already failed PID, but accepts two different launch IDs for the same PID. The subsequent duplicate-PID guards are local to individual stores: observer declarations check `declarations`, authority helpers check their phase table, and `PythonLifetimes.launch` checks Python generations. A PID moving between those stores therefore escapes every duplicate-generation check. `dependency_key` also prefers the Python generation when both stores contain that PID.

The new literal-terminal classifier makes this omission consequential: once a Python generation exists for the PID, lines 267–272 return its attribution before inspecting any helper declaration. An explicit conflicting/new helper generation for that same PID is ignored. Conversely, a new reader can be admitted while a different completed observer generation remains recorded under that PID. This is observed reuse, not the acknowledged limitation concerning unobserved reuse.

**Concrete trigger:** accept a reader generation `g1`, its genuine SELF proof and matching baseline, and its truthful completion. Register an exact source-owned PS helper with the same PID and a distinct launch ID after that completion. A literal terminal row whose sampling interval overlaps the old reader completion and the new helper lifetime is attributed to the old reader. Its raw PPID can be unchanged because both source launches can have the root as parent. The helper's explicit launch/end does not make the row unaccounted. Interval overlap is intentionally allowed by the adopted contract, so it cannot substitute for the missing uniqueness check.

The reverse ordering is also relevant to the actual source protocol: the root's baseline PS helper completes before readers are launched. If a later reader receives that earlier helper PID, the separate stores do not reject the observed reuse. A simultaneous overlap is unnecessary; the contract explicitly rejects reused generations, rather than attempting to reconstruct PID birth identity.

**Evidence:** one isolated source-only check exercised the unchanged `register_launch` function extracted by AST and the actual `PythonLifetimes`/`classify` implementation, with controlled fixtures derived from existing test functions. It observed:

```json
{
  "registrations": {"g1": 20, "new-ps-generation": 20},
  "registration_failed_pids": [],
  "old_reader_completion_end": 14.5,
  "new_helper_launch_start": 14.6,
  "new_helper_completion_end": 14.9,
  "controlled_sample": {"start": 13.0, "end": 15.0},
  "roles": {"20": "worker"},
  "attribution": {
    "terminal_attribution": "source_only_terminal_attribution",
    "family": "reader",
    "launch_id": "g1",
    "image_evidence": "unavailable_exited"
  }
}
```

The fixture used arbitrary controlled timestamps; it did not run a two-second process observation. The failure does not depend on that interval width: by source inspection, moving sample_start from 13 to 14 preserves every tested inequality (`12.1 <= 14 <= 14.5`, `14 <= 15 <= 15 <= 15.1`) and gives a one-second interval overlapping the two lifetimes. This narrower variant is a source deduction, not an additional executed control.

The check's first invocation stopped during fixture construction because the AST fixture namespace omitted `errno`; no attribution result was obtained. After adding that stdlib binding, the same isolated check completed successfully and printed the counterexample; measured in-script elapsed time was 0.013090957887470722 seconds. This was not a pytest run, native process experiment, or numerical import. The nested registration function was executed without editing it; its only environmental substitute was a no-op wake callback. The classifier used the real monitor source and the existing exact command/vector helpers. This establishes the local registration/attribution defect, not a measured full-supervisor COMPLETED result.

**Why this blocks SPEC:** the binding brief requires an unambiguous unique source generation and says duplicate/reused generations cannot be repaired by late events. The adopted v2 expressly excludes conflicting generations and observed replacement/reuse. The new path instead selects a family from a preferred PID store even when another source generation is already known. The recorded family, launch ID, proof and completion can consequently refer to the wrong generation. Baseline, helper-cost and parent-dependency bookkeeping are also keyed through the conflated PID; this review does not claim a measured numerical undercharge from the isolated zero-RSS example.

**Why this blocks QUALITY:** the new tests cover duplicate Python generations, reused IDs and conflicting helper witnesses within individual families, but omit cross-family PID collisions. The new central registration function appears to enforce global uniqueness while enforcing only global launch-ID uniqueness. That leaves a load-bearing invariant dependent on callers using separate stores consistently.

**Smallest correction:** enforce PID-to-launch-generation uniqueness across all source families at registration, before inserting into any family store. Mark the reused PID failed and wake its existing pending dependencies; preserve the failure on later events. Keep the existing launch-ID collision rejection. The terminal classifier should also fail closed on conflicting family entries if it is expected to accept independently constructed state at its existing unit seam, rather than silently choosing Python. Add focused negative controls for observer→reader and reader→observer reuse with distinct IDs, including an interval overlapping the transition, and ensure the original pending row cannot later resolve through either generation. Cover authority/observer collisions through the same central guard. No broader identity framework, native retry or scientific execution is needed for this correction.

## Scope and reviewed evidence

Read the complete binding implementation and review briefs, the entire 9,975-byte implementation report, the dated adopted amendment, complete linked v2 contract, parent ruling, first-SELF correction, and original/scoped design reviews. Root's explicit preservation of the exact-display/ESRCH route was treated as binding. Inspected the supplied four-authored-path diff and relevant current dependencies in monitor, command/authority helpers and existing test fixtures. The large archival diff was supplied as the complete package; no archival crawl or repeated broad Git diff was performed.

Root's independent delivery verification was read and used as delivery evidence, rather than rerunning its archive work. It reports 1,116 new entries / 7,199,370 bytes, 183 raw symlink payloads, 709 original specimen mappings, 916 attempt-file hashes, six source hashes and four statically checked native inputs; 5,063 prior entries / 67,169,676 bytes remained unchanged. Package `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`, the lock and both consumed old controls were preserved, with the new worker bytes equal to the durable archived original ROOT_BODY. Those facts are attributed to root's verification, not represented as a second independent hash audit by this reviewer.

Read the final retained command and its complete short pytest output: **211 passed, 6 deselected in 1.79s**, with 84 new cases. The exact selection includes the new terminal attribution suite and directly related terminal lifecycle, Python lifetime/fix1 and native-process/fix1/fix2/fix3 controls. Its `-k` expression excludes `python_launcher_is_rechecked`, `owned_dispatch_once`, `monitor_root_generation_reconciles` and `git_launch_witness_write_failure` (six collected cases). The report honestly distinguishes RED01's missing-signature failures from RED02 behavioral failures, retains all nine attempts and reports later behavioral RED corrections. No reported suite was rerun for this review.

No source, existing evidence, native input or Git mutation was made. The review report is the only authored repository artifact. No subagent, native control, numerical backend, reader/reference evaluation, model, training, calibration or protected operation was executed. Read-only `git status --short` was empty before writing this report.

## Positive specification and quality observations

- The literal-terminal predicate keeps both raw fields, integer RSS0 and the exact native error method/reason/errno, and requires ordered sample/lookup intervals. Python terminal attribution requires a retained proof reference before its terminal sample, matching source end and, for readers, genuine SELF plus joined baseline. Historical image evidence is recorded separately from unavailable current image. The explicit raw journal sample precedes resolution metadata.
- Root proof production is gated by the actual owned collection path. Forwarded source samples no longer create owning-supervisor root proof merely by containing a root row. The helper same-sample path checks retained object identity and the actual sample's proof dictionary, not equal timestamps alone. Reader first-SELF joining uses the same retained batch and waits for its baseline. Python's own earlier-proof cutoff remains separate.
- Python generations are classified before helpers. Present terminal parents require full terminal attribution; live and absent historical parent routes are distinct, and same-sample qualification requires a live parent. The task's child-first reader-context regression is directly covered. Except for R1's cross-family generation ambiguity, parent launch order, completion bounds and failure checks follow the adopted finite relation.
- Pending observations use own/parent generation dependencies, with PID keys for missing-launch discovery. Launch, proof, SELF, baseline, completion and first failure wake affected batches. Removed batches are not rescanned; failure notifications are bounded rather than repeatedly waking themselves. The first-SELF/late-launch tests exercise supervisor event ingestion, not just direct helper calls.
- Literal root-only cleanup is provisional under unreaped ownership, requires complete sole-root zero-RSS membership and available prerequisites, and obtains final qualification after actual poll0 and truthful root end. Its record explicitly retains membership_empty=false. A literally empty observation has a separate record. Poll=None remains failure; survivor cancellation occurs before release. Existing exact-display/ESRCH attribution remains a separate route. Earlier reasons continue through cleanup/emergency handling, and no renewed deadline, grace, cap reset, fabricated completion or post-reap numeric signal was introduced by this diff.
- Existing resource equations, ordinary exact live vectors, PS_ARGV and the private cleanup query were not widened. Numeric collection precedes new identity operations, and provenance failure continues to force conservative accounting. There is no scientific or information-access change in the authored paths.

These observations do not waive R1 or certify the entire monitor. In particular, acceptance of a helper relation still depends on fixing uniqueness across the actual family stores.

## Frozen future native control

Inspected the new input statically. Its parent assertions can consume the monitor's actual sample, proof sample_id, owning completion, resolution, cleanup membership and qualification records. The empty case distinguishes no members from a qualified zero-RSS root-only observation and chooses the actual literal-terminal or exact-display/ESRCH resolution path. It does not manufacture a marker for an exact-display row.

The survivor case permits a qualified terminal root row but rejects a live/nonterminal root observation. It requires actual root returncode0, a genuine same-group child observed after reparenting, a successful owned group signal and bounded descendant socket EOF. It does not claim an owning orphan reap. Its original worker comparison points to the durable archived ROOT_BODY, and the original deadlines, file vector, proof gate, EOF loop and failed-attempt retention remain present. No additional task-created blocking defect was identified in these assertions by static review.

This is an unexecuted future input, not evidence that macOS supplies all of those witnesses in the intended two cases. It must remain frozen/allocated under the existing separate native gate after the source correction and review. Synthetic controls, root's archive verification and this review do not establish native compatibility, continuous birth identity, security containment, unsampled memory peaks or scientific readiness. Protected/scientific work remains CLOSED.

## Disposition

Return this finite task for the cross-family generation correction and focused source-only regression evidence, then re-review that delta. **SPEC and QUALITY remain NEEDS_REVISION because of R1.** A separately authorized native control remains outstanding even after that source finding is resolved.
