**F2/N1 — Live declared authority-helper RSS omitted until completion — ADDRESSED.** `validation/kernel_stage_a/monitor.py:227` now retains admission from the same contemporaneous exact classifier used for foreign-identity enforcement. `:179` uses that retained admission to charge the helper's observed absolute peak at baseline zero during reconciliation, immediately including it with authority-Python RSS in the enforcing cap. The marker persists when termination prevents the helper-end event, so the failed durable record retains the observed charge.

The charge marker does not replace the final identity verdict or modify the classifier. An unresolved lifetime still fails final validation, and a subsequently foreign sample still triggers immediate stopping. Completed-helper reconciliation remains available through the existing historical role. The original deadlines, memory/output limits, authority-Python charge and phase boundaries are unchanged.

The two controls in `tests/test_kernel_stage_a_preflight_fix2.py:10` address the precise defect: individually admissible synthetic Python/helper peaks exceed the combined cap before any helper-end event, and a separate foreign-identity stop preserves the same charge. Both require termination of the owned sleeping worker, an empty completed-helper inventory, baseline-zero helper accounting and equality of durable/returned JSON semantics. The test adjustment from direct Python-dictionary equality to JSON-semantic equality correctly handles the existing integer PID keys; it does not weaken the resource or verdict assertions.

## New breakage in the fix diff

None identified. The retained resource marker is separate from identity permission; it does not make historical helpers active or broaden executable, argument, parent or lifetime exceptions. No other executable source component changes in this diff.

## Out-of-scope observations

The previously ledgered native `comm` truncation/framework-launcher display prerequisite remains pending and unchanged. It is a separate compatibility component, not reopened in this fix round. No new out-of-scope issue was identified.

## Checks and limits

- Reviewed the controlling fix2 brief, full report and supplied diff for BASE `dd0b33927cce8abe254adc06e652263d835d20bf` through HEAD `5bcd05d545979125871a06f2346f1bd535a9aa43`, including the changed monitor hunks, full new test, raw RED/intermediate/final logs and verification record. No unchanged finding or whole-task review was repeated.
- The retained RED shows the original outer-timeout/missing-charge failures. The final focused log records **2 passed in 0.03s**, and the selected covering log records **15 passed in 1.64s**, with explicit exit0 records. The covering selection includes prior completed/late-helper, identity, timeout and durable-report controls. Compile, diff and unchanged-input records report exit0. These are supplied implementation evidence, not independently rerun results.
- No tests, Git commands, native probes, calculations, source edits or scientific execution were performed during this review. Only this ignored review report was written. Root's independent file/package verification is acknowledged without repetition.
- The controls use synthetic Git identities/RSS and an owned sleeping Python process. They do not verify native Git/ps parsing, native stage/reader identity, real resource feasibility, the six-factor setup or the scientific fixture/reference campaign. Actual execution seal fields and release remain pending; this approval fills none of them.

## Verdict

**SPEC: APPROVED. QUALITY: APPROVED.**

**Fix round: All findings under this scoped review addressed, no new Critical/Important breakage.** F2/N1 is closed. Prior F1/F3/F4/F5/F6 closure is unchanged. This is source-fix acceptance only, not native readiness or Stage A authorization.
