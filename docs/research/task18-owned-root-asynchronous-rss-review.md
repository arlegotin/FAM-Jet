SPEC verdict: PASS for the narrow source contract and static native input, with the disclosed evidence-capture limitations. No Critical or Important source findings.

Strengths:

- validation/kernel_stage_a/monitor.py:167, :185, and :1112 consistently require actual integer, nonnegative RSS. The surrounding generation, retained-object identity, genuine SELF/baseline, parent, ESRCH provenance, ordering, complete membership and actual poll0/end requirements remain intact.
- The named accounting risk—larger membership RSS being lost during successful attribution—is resolved by the existing path. monitor.py:754 retains the maximum; cleanup records membership numerically before qualification at :1090; baseline subtraction uses that retained maximum at :728; reconciliation and finalization enforce the cap at :1011 and :1247. There is no zero overwrite or new query/wait.
- tests/test_kernel_stage_a_owned_root_terminal.py:159 tests earlier-positive/later-zero, later-positive and larger-later observations with exact expected peaks. :178 checks positive-RSS poll=None cancellation before wait; :187 demonstrates successful identity qualification while the original memory cap still stops acceptance. Invalid RSS controls at :197 preserve the broader proof, provenance, ownership, completion and sticky-failure negatives.
- docs/research/task18-owned-root-asynchronous-rss-native-control.py:73 and :80 accept and retain actual nonnegative integer observations without a display requirement. Genuine live proof and SELF/baseline remain required at :67 and :104; complete empty versus qualified nonempty membership stays distinct at :113; survivor failure, owned signal-before-end, and child EOF remain enforced at :125.
- Saved logs support the reported four RED failures/one pass, repository-venv 66-pass GREEN, and single 286-pass/6-deselected cover. These are controlled test results, not native compatibility evidence.

Critical findings: None.

Important findings: None.

Minor findings:

1. Stale native-input reference. validation/kernel_stage_a/README.md:340 still names task18-owned-root-lifecycle-native-{control,worker}.py as the new, static-only inputs. The current parent is task18-owned-root-asynchronous-rss-native-control.py; the lifecycle worker is reused, while the lifecycle parent belongs to the already-consumed historical control. Update this paragraph to name the new parent and unchanged worker explicitly. This prevents selecting the superseded zero-RSS parent.
2. The prose understates the timestamp capture gap. docs/research/task18-owned-root-asynchronous-rss-report.md:15 associates missing live start/end epochs with the first three commands and implies a subsequent capture-runner transition. docs/research/task18-owned-root-asynchronous-rss-evidence/attempt-index.json:4 states that absolute epochs were not captured, and all six attempts—including both fresh GREEN runs and the cover—have null epochs. Clarify that the timestamp gap applies to every listed test attempt, while separately identifying the missing pre-edit RED snapshot and interrupted full stream. Preserve the historical nulls.

QUALITY verdict: APPROVE WITH MINOR DOCUMENTATION CORRECTIONS. The implementation is appropriately small and the added tests are behavioral. I found no specific current-source uncertainty requiring another controlled test. The historical provenance gaps remain limitations; repeating tests would not repair them. Native input remains NOT RUN, and source acceptance does not authorize native or scientific execution.

Archive note: reviewer /root/owned_root_rss_review, gpt-6-astra/high, isolated read-only task review. Substantive text/verdicts retained; formatting normalized for a portable repository report. Minor corrections are separately verified by root after the author's documentation-only commit. No test/native/math rerun occurred in this review.
