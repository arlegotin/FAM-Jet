# Task 18 Python launch-generation/lifetime compatibility implementation

Implemented the separately released compatibility component from accepted I1 BASE `d698a5e422d6b55148bb795f0ad0bd86d9c5e10b`, on current `main`, with no branch, worktree, subagents, reviewer, push, selfacceptance or scientific release. Source commit: `18c7753e982b9ea2a8d6191a35970c5151403ab7`. The source was committed before the ONE native sequence. The subsequent delivery commit contains evidence and this report only.

This is an explicit policy extension, not a retrospective correction to strict ESRCH results. Existing held-open 0.867s native evidence and previous source acceptance remain historical and unmodified. The release prerequisite was the independent SOURCE-only I1 acceptance at the BASE. The adopted design remains SHA256 `3eaf212d9880befc2d635dbb4eecec04c3bb3c79a31e85fb539f88cb43158432`.

The binding original brief was first read in full at 9367 bytes / SHA256 `e301c3db11381e615fbf512c207d7bbd1778c9be82e75b08e4a594e753ce4f64`; its exact original bytes are preserved in `contract/task-18-native-python-lifetime-brief-original.md`. Root subsequently clarified that the capitalized FAILED wording concerns unsuccessful worker execution, not a replacement of existing monitor status enums. The current clarified brief is preserved separately at 10518 bytes / SHA256 `c3343cb1c3236a53dc57f82e56bc04b2772c591e002531415609d4bab4dbd36d`. Existing STOPPED semantics remain; incomplete source recovery retains literal FAILED. Identity compatibility never rescues worker execution.

All paths below are relative to `docs/research/task18-native-python-lifetime-evidence/` unless stated otherwise. A durable identical report also resides at `docs/research/task18-native-python-lifetime-report.md`.

## Contract and implementation

`authority.python_launch` rechecks the resolved launcher artifact immediately before launch, binds its path/hash separately from the observed runtime framework image/hash, and mints a unique source launch ID, exact vector/hash, parent, role and pre-Popen monotonic launch start. It does not guess a Python image from an executable name.

The native supervisor records its actual root Popen launch and post-wait completion. `PythonLifetimes` only supplies an ESRCH extension when the one exact generation has a successful applicable image proof and a trusted matching reaped completion. Root proof can be acquired only on the owned unreaped path. Reader proof comes only from the existing baseline observer event's tagged emitter/self row; other rows and generic outer observations cannot supply it. Reader baseline RSS must match that own row, the postimport/preallocation boundary and the same lifetime. Delayed self sample, baseline, launch and completion joins retain bounded per-generation state. Duplicate IDs/PIDs, overlapping reader ownership, conflicting parent/vector/image, malformed/non-ESRCH lookups, out-of-lifetime evidence and unmatched final evidence fail. No PID reuse support was added.

Admitted rows retain their original ESRCH image record and raw RSS, and are explicitly labeled `image_evidence=unavailable_exited`, `launch_evidence=source_owned_python_lifetime`, with launch ID and original proof reference. Every new successful live row still needs its own exact image/parent/display. Source proof is a sampled trusted-source assumption; it is not continuous kernel identity or arbitrary OS argv-byte certification. An unsampled exec transition is not excluded.

The existing incremental journal, dependency wakeups, settled-sample disposal, phase-independent raw RSS recovery, conservative failed-provenance charge and bounded final commitment remain. The new reader-owner check uses one current-reader pointer, not an all-history scan; unmatched evidence uses a bounded set and constant-time final presence check. Pending evidence retains full conservative charge, and a late successful attribution cannot lower an already established peak or erase a cap violation. The integration control observed exactly that retained full-RSS peak.

Only `production.clean_read` dispatch changed: its existing one `ledger.call('read_dispatch', ...)` now calls `owned_reader_dispatch`, a small local Popen/communicate operation. The exact reader vector, seven-key environment, canonical stdin request bytes, file stdout/stderr, temporary cwd and original candidate deadline remain. Remaining deadline is recomputed after witness work. Every post-Popen exception/timeout kills as necessary, reaps the exact child, emits a truthful completion and propagates failure. No retry, second dispatch or additional read was added. The reusable operation also permits the authorized nonnumerical native control without invoking clean_read's numerical request construction.

No behavioral changes were made to commands.py, __main__.py or reader_worker.py. No famjet source, dependency, data, cache, request/response schema, factor, mathematical definition or source-compatibility guard changed. The package digest remains exactly `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`.

Original scientific limits remain 600s outer, 90s candidate, 201326592B incremental worker, 67108864B outputs, 4294967296B free disk and CPU64 <=4 numerical threads. Identity reconciliation does not renew any limit or authorize any scientific allocation.

## Source verification: every actual attempt

`attempts.json` contains every exact executable command, exit code, log, original `/tmp` and actual `/private/tmp` basetemp, durable specimen mapping and source-input mapping. Every attempt used its own basetemp. Its actual outputs and then-current affected source/test inputs were immediately copied into `attempts/<attempt>-specimens` and `attempts/<attempt>-source`; no old missing output was recreated and no attempt directory was reused. Pytest's copied `*current` aliases are preserved as symlinks; the durable concrete sibling directories contain the outputs.

| Attempt | Actual result | Meaning |
| --- | --- | --- |
| red-01 | exit 1; 20 failed, 1.22s | Expected missing lifetime and owned-dispatch interfaces. |
| green-01 | exit 0; 20 passed, 1.20s | Initial generation and cleanup contract. |
| red-02 | exit 1; 1 failed, 25 passed, 1.54s | Late root self-emitter could supply proof after owner reaping; fixed by retaining owner-only root proof. Additional baseline controls passed. |
| green-02 | exit 1; 1 failed, 26 passed, 1.19s | Real monitor integration exposed missing root-end dependency wake; corrected before covering run. This failed intermediate attempt is retained. |
| cover-01 | exit 0; 91 passed, 24 deselected, 3.99s | Covering external monitor/native/authority/fix2 controls. |
| red-03 | exit 1; 1 failed, 27 deselected, 0.04s | Completion could precede a later owned image proof; added latest-proof lifetime bound. |
| cover-02 | exit 0; 92 passed, 24 deselected, 4.23s | Covering verification after latest-proof bound. |
| red-04 | exit 1; 4 failed, 28 deselected, 0.06s | Missing launch incorrectly deferred contradictory parent/native errors; late completion did not recheck bound baseline timestamp. Both fixed. |
| cover-03 | exit 0; 96 passed, 24 deselected, 4.36s | Final source verification before source commit. |

The final covering command was:

```sh
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_python_lifetime.py tests/test_kernel_stage_a_native_process_fix3.py tests/test_kernel_stage_a_native_process_fix2.py tests/test_kernel_stage_a_native_process_fix1.py tests/test_kernel_stage_a_native_process.py tests/test_kernel_stage_a_preflight_fix2.py tests/test_kernel_stage_a_preflight.py tests/test_kernel_stage_a_preflight_fix1.py -k 'python_lifetime or native or monitor or authority or observer or baseline or f3 or f5 or same_interpreter or prospective' --basetemp=/tmp/task18-python-lifetime-cover-03
```

No full suite was run, per the binding focused-control allocation. Existing `test_python_success_and_later_missing_image_are_distinct_retained_samples` remains unchanged and passing: earlier success without applicable generation proof still fails. New controls also cover delayed ordering, absent proof/end, parent/display/image/native-error/lifetime conflicts, duplicate/reused PIDs/IDs, baseline binding, overlapping ownership, post-reap success, nonzero exits, one actual dispatch, timeout cleanup and witness-write failure cleanup. A monitor integration control uses synthetic identities and an actual naturally reaped nonnumerical child; native evidence below independently supplies real kernel outcomes.

`py_compile` succeeded for authority.py, monitor.py, production.py and native-normal-exit.py; `git diff --check` passed. Initial non-escalated git add/commit was denied by the workspace .git write sandbox (`index.lock: Operation not permitted`); the authorized auto-reviewed escalated source commit succeeded. There was no auto-review rejection and no human approval question.

## Single native sequence on frozen source

Exact command, invoked once with auto-reviewed native ps read access:

```sh
.venv/bin/python docs/research/task18-native-python-lifetime-evidence/native-normal-exit.py docs/research/task18-native-python-lifetime-evidence/native-01 18c7753e982b9ea2a8d6191a35970c5151403ab7
```

Exit 0. `native-01/result.json` reports `PASS_IDENTITY_ONLY_EXPECTED_WORKER_FAILURES`; `native-01.exit` retains the command exit and `native-01.log` retains stderr (empty). The exact executed script is committed in the source commit and copied byte-for-byte into `native-01-source/native-normal-exit.py`. All external helper Python inputs were copied there immediately afterward. `frozen-source.json` binds the source commit, all external helper/test/script hashes, actual runtime/helper identities and unchanged package hash. Native execution rehashed the actual helper/script files and runtime. Git-blob comparison in the subsequent artifact audit confirmed the frozen source bytes matched the committed source.

The one sequence's absolute start was 547833.362862666, deadline 547843.362862666, elapsed 2.031376834s including 0.991232084s ordinary import overhead. Both child watchdogs were bounded by min(original 10s deadline, child start+5s). No watchdog kill, retry, policy widening or allocation renewal occurred.

| Fixed case | PID / launch ID | Natural return | Identity and sampled cost |
| --- | --- | --- | --- |
| Exact stage vector, incomplete FIFO then `{}` | 18680 / a0c7600e030e4bfb8c502558bb8add34 | 2; `REFUSED: closed seal schema mismatch` | Own unreaped image proof 547834.453616750–547834.453848083; reaped completion 547834.507098208; real ESRCH lookup 547834.507191541–547834.507290291. Retained RSS 22151168B. No postimport baseline claimed. |
| Exact reader vector, trusted owned dispatch, empty stdin then EOF | 18688 / 9df2596b68f74608bd14e17e0f6e92bb | 1; JSONDecodeError at input decoding before profiling/read work | Own emitter proof 547835.166593875–547835.166810166; completion 547835.393272166; real ESRCH lookup 547835.393714416–547835.393815541. Own baseline 222806016B; retained RSS 223690752B. |

The stage was held using the existing seal FIFO and genuine entry path. FIFO writer-open synchronization confirmed a waiting reader before holding the incomplete stream. The TEST-ONLY seam intercepted image lookup after process_tree had parsed an actual ps row, delivered invalid seal input/EOF, allowed natural exit and owner reaping, then called the unmodified real `authority.process_image`/macOS proc_pidpath on the retained PID. No kernel result was manufactured and no exit sleep race was used. Reader stdin was held by a test-only Popen proxy around the real owned dispatch; after release it recomputed the same original deadline. The exact vectors, raw rows, lookup intervals, launch/completion records and proof references are retained in `native-01/raw.jsonl`, `native-01/root/events.jsonl`, `native-01/reader/events.jsonl` and result.json. Both stdout files are empty. Both deliberate stderr refusal traces are retained byte-exact.

Reader absolute import RSS exceeds the scientific incremental budget; this is a baseline measurement, not a demonstration of cap compliance or an allocation waiver. These controls exercise real identity compatibility and the real owned dispatch. They do not constitute a full native supervisor/candidate-ledger/resource-limit run; supervisor reconciliation is covered by the focused synthetic integration controls. The harness is the trusted reader parent for this control, not a scientific stage.

Actual numerical requests, request bytes, reads, factor constructions, factorizations and model constructions are all zero. Ordinary imports of existing worker/production modules, torch and famjet.eval.isolation occurred, as expressly permitted. Stage refusal preceded backend work; reader refusal preceded profiler installation and isolation._worker. No snapshots, fixtures, histories, references, panels, protected data, corpus/cache, fit/train/bootstrap/calibration or scientific request was accessed or constructed.

The native directory holds 26738 regular-file bytes including result.json (21988B before result serialization). Its FIFO remains an original nonregular synchronization endpoint with no stored data; the artifact manifest records its type and path. Total selected RSS is sampled evidence, not an allocator peak. Preparation/source-test artifacts are separate compatibility overhead and do not consume or renew a scientific 600s allocation.

## Actual identity hashes and artifact verification

- authority.py: `25d172f31df4ee70069f91840c5f48a2d12759d733744744fbb0ff30163af5d4`
- monitor.py: `687be22c28334e59b2bfdeb380f760c94d39998dad0a3f2c51267dc782ad9137`
- production.py: `1345896c886d683e1354ccb93feee63dbb62690e3d3eff5a9fa382cbadde25d0`
- Exact executed native script: `d3c3b022f3ac3d1075da858afe78edce942bcac788b0112a2e15fe09b2fb1e8e`
- Resolved Python launcher: `a1f6d9dc20d4787a84dc2fe782094a7bac5946f49a962aa0af48a02f0e8d5bc5`
- Actual framework Python image: `619a54258d9057844c176bfb41b56501ee8d00966929c899c2aae73c7ddac506`
- /bin/ps: `16d273739778797145fd22cba76113d2aaa99c759313d56ef87ed56a16bca083`
- Resolved Git helper: `03d4a6c5328d4a1ce84eba2765664284b1fb2414d9e657358733056a89a95954`

The full paths, Python 3.13.5/arm64 and decimal extension identity, unchanged commands/entry/reader hashes, and all remaining external helper hashes are recorded in frozen-source.json and verification.json. `artifact-manifest.json` inventories durable regular-file byte sizes/SHA256, original specimen mappings, pytest symlink targets and the original FIFO endpoint.

Read-only artifact audit command:

```sh
.venv/bin/python docs/research/task18-native-python-lifetime-evidence/audit.py
```

Exit 0, retained in audit.exit/audit.log. It confirms both actual ESRCH records, source launch IDs, successful same-generation proof-before-completion-before-lookup ordering, sample/lifetime overlap, own reader baseline, actual expected nonzero codes, zero numerical counts, empty stdout, no watchdog kill, 10s/5s bounds, exact original brief and frozen Git/source/helper/script hashes. This is implementation artifact verification, not independent source acceptance.

## Remaining limits and handoff

No continuous image identity, kernel birth token, arbitrary argv-byte proof, never-proved Python admission or PID-generation reuse is claimed. Unobserved exec remains a trusted-source assumption. Late/missing events can still cause conservative full-RSS or cap stops. Nonnumerical normal exit compatibility does not establish successful numerical readers, scientific resource sufficiency, authority-seal completion or Stage A feasibility.

Independent task-scoped SPEC and QUALITY review and root FULL-read/actual artifact verification remain required. Scientific release, numerical feasibility, rate records, static exports and all protected scientific results remain NULL/HELD. No scientific work is authorized by this report or the compatibility PASS.
