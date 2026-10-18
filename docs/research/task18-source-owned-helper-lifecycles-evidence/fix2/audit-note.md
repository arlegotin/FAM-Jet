# Fix round 2: I3 cleanup evidence audit

HOLD for scoped I3/new-breakage review. Source commit `8642b7c57c90b16ff4a2eab2f04759540e5a9962` follows clean `f02a432cdd63359be7d1938e7d62a3ec57c48df0`. I1/I2/I4/I5/M1 source remains closed and unchanged. No native control, probe, model, factor, numerical read or scientific operation was performed. The native parent/worker were not imported or executed.

## Investigation and exact change

The retained fix1 partial-journal trace ended after successful SIGKILL; it had no per-wait timing and cannot establish the precise scheduler contribution. Inspecting this interpreter's POSIX `Popen._wait` (`posix-popen-wait.txt`) showed timed polling with successive 1/2/4 ms sleeps, capped only at the timeout supplied by the caller. Cleanup supplied all remaining absolute time, leaving no bound for its wait evidence, native end and final commitment.

A controlled Popen instance exercises the actual stdlib wait algorithm with controlled `_try_wait`, monotonic time and sleep; it never creates a process. At 72 ms, the old code supplied 8 ms. The ready child became waitable after 3.5 ms but the backoff observed its actual simulated status at 79 ms. An explicit 1.1 ms journal serialization cost plus bounded final encodings pushed the controlled caller to 80.7 ms and prevented the wait record. RED02 added the not-waitable case: no status could be recovered and the full wait allocation also prevented its failure witness. Both actual failed logs and controlled traces are retained.

The fix supplies at most half the *existing remaining* allocation (still capped at one second) to the same owning Popen.wait. It does not increase the original work/cleanup reserve, overall deadline, grace or resource budget. The remaining half permits wait evidence, existing native `root_end` and final commitment. The wait record retains actual returned value or actual exception, current Popen returncode, PID, timeout, start/end and reap flag. A separate `cleanup_owner_end` records current owner status and explicit synthetic/native origin without another poll, signal or reap. Unknown returncode stays null/reaped false. This diagnostic is not a Python generation end, root receipt or baseline proof; native root_end and root receipt ASTs are unchanged.

Controlled ready and unknown cases now preserve signal→wait→diagnostic-end ordering and complete the caller inside 80 ms. Unknown retains TimeoutExpired/null status. Both retain deliberately malformed source as FAILED/incomplete. No invalid input is converted to success. Arbitrary OS scheduling cannot be guaranteed by a finite deadline; failed observations/statuses continue to fail honestly.

## Actual attempts and bounded specimens

All commands below were issued through `.venv/bin/python docs/research/task18-source-owned-helper-lifecycles-evidence/fix2/capture.py LABEL ...`. The child interpreter is the absolute repository venv shown below. Every attempt has a fresh task-owned basetemp, actual pre/post UTC and monotonic timestamps, environment, child exit and full combined output in LABEL.json/LABEL.log and `attempt-index.json`. The inherited VIRTUAL_ENV points elsewhere; it is not the executed interpreter.

| Attempt | Actual output | Exit | External seconds |
|---|---|---:|---:|
| red01 | 1 failed, 76 deselected in 0.07s | 1 | 0.172334 |
| red02 | 1 failed, 77 deselected in 0.07s | 1 | 0.166834 |
| green01 | 78 passed in 0.16s | 0 | 0.267127 |
| cover01 | 1 failed, 362 passed, 6 deselected in 2.35s | 1 | 2.462566 |
| cover02 | 363 passed, 6 deselected in 2.31s | 0 | 2.420429 |

RED01 and RED02 failed only their intended missing evidence assertions. The focused file grew from the previously accepted 76 to 78 passing controls. cover01's sole failure was `test_unsampled_git_still_requires_exact_phase_and_qualified_parent[late_completion]`: its rapid monotonic calls produced equal helper completion/phase-end timestamps **563445.970125833**, so the intended late-end input was not late. Root authorized only guaranteed ordered fixture instants plus an explicit ordering assertion, preserving I2 source and rejection assertion. `math.nextafter` now constructs successive representable instants inside the mocked owner's lifetime. This concrete fixture correction justified cover02; no favorable rerun or standalone 80 ms retry occurred.

The original unchanged partial-journal test passed in both covers. Its actual operation stays FAILED/outer timeout/source_accounting.complete:false, with actual owning returncode −9 and no cleanup diagnostics. cover01 saved pre-commit outer_seconds **0.07472729205619544**; cover02 saved **0.07480183301959187**. Both retain successful nonabsent SIGKILL followed by actual owning wait and diagnostic synthetic owner end. In cover02 the wait starts 563509.310297291 with timeout 0.003650958475191146, returns −9/reaped at 563509.311825541, and owner_end is 563509.312019875. Final report timing remains honestly labeled before bounded final commit; the controlled regression separately checks the caller after commitment. No claim recovers earlier statuses or proves universal/native compatibility.

### Exact pytest child commands

red01 (exit 1):

```text
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python -m pytest tests/test_kernel_stage_a_source_lifecycles.py -k owning_wait_leaves -q -ra --basetemp=/private/tmp/task18-source-lifecycle-fix2-red01-absptwtg
```

red02 (exit 1):

```text
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python -m pytest tests/test_kernel_stage_a_source_lifecycles.py -k 'owning_wait_leaves and unknown' -q -ra --basetemp=/private/tmp/task18-source-lifecycle-fix2-red02-1u3e0rtc
```

green01 (exit 0):

```text
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python -m pytest tests/test_kernel_stage_a_source_lifecycles.py -q -ra --basetemp=/private/tmp/task18-source-lifecycle-fix2-green01-9ac2doju
```

cover01 (exit 1):

```text
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python -m pytest tests/test_kernel_stage_a_owned_root_terminal.py tests/test_kernel_stage_a_terminal_attribution.py tests/test_kernel_stage_a_terminal_lifecycle.py tests/test_kernel_stage_a_python_lifetime.py tests/test_kernel_stage_a_python_lifetime_fix1.py tests/test_kernel_stage_a_native_process.py tests/test_kernel_stage_a_native_process_fix1.py tests/test_kernel_stage_a_native_process_fix2.py tests/test_kernel_stage_a_native_process_fix3.py tests/test_kernel_stage_a_source_lifecycles.py -k 'not python_launcher_is_rechecked and not owned_dispatch_once and not monitor_root_generation_reconciles and not git_launch_witness_write_failure' -q -ra --basetemp=/private/tmp/task18-source-lifecycle-fix2-cover01-cuqsc9lg
```

cover02 (exit 0):

```text
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python -m pytest tests/test_kernel_stage_a_owned_root_terminal.py tests/test_kernel_stage_a_terminal_attribution.py tests/test_kernel_stage_a_terminal_lifecycle.py tests/test_kernel_stage_a_python_lifetime.py tests/test_kernel_stage_a_python_lifetime_fix1.py tests/test_kernel_stage_a_native_process.py tests/test_kernel_stage_a_native_process_fix1.py tests/test_kernel_stage_a_native_process_fix2.py tests/test_kernel_stage_a_native_process_fix3.py tests/test_kernel_stage_a_source_lifecycles.py -k 'not python_launcher_is_rechecked and not owned_dispatch_once and not monitor_root_generation_reconciles and not git_launch_witness_write_failure' -q -ra --basetemp=/private/tmp/task18-source-lifecycle-fix2-cover02-mggs7twb
```

## Preservation and current hashes

`pre-fix-manifest.json` records the actual pre-edit monitor/test snapshots with UTC/monotonic timestamps and hashes. No intermediate per-attempt revision snapshots are claimed. `specimen-manifest.json` maps 44 selected original/archive files (93934 bytes): both RED controls, ready/unknown controlled finalization, both actual partial-journal covers and the failed/corrected Git fixture. Full original/archive bytes and hashes were verified; no unrelated shared pytest tree was read/copied. Old evidence and failed statuses remain intact.

`static-audit.json` records AST checks, clean diff check, unchanged protected files, native inputs, source registry, closed Git phase predicate, native root_end and root receipt methods. No math, command, isolation, fixture/reference, old assertions or resource limits changed.

- `validation/kernel_stage_a/monitor.py` SHA256 `044b6d0f76e11bc2a2f2d608d35f1e36e3bd85244e31fc063335124a0db5c473`
- `validation/kernel_stage_a/source_lifecycles.py` SHA256 `4538fb9887cfc13c98c5ff61be16168e88cf2f5a590d6f67b9fc7feab3e09004`
- `tests/test_kernel_stage_a_source_lifecycles.py` SHA256 `bf30fd88af77f6e474e0a94315d7b9ffae76b20ff52092ed19ade7ac14d76c5b`
- `docs/research/task18-source-owned-helper-native-control.py` SHA256 `3275a093357ca2618973690e03c55f407d2219e60eb68572343b08dc20d42198`
- `docs/research/task18-source-owned-helper-native-worker.py` SHA256 `14a1f41cd099fed3bfe553340e2cbdf174e2e4c005312a25fb6c5c9b976de254`

Package `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`; lock `2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1`. Independent scoped review and any future native/science allocation remain separate. HOLD.
