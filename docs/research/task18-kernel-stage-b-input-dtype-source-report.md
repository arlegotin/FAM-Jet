# Task 18 Stage B input dtype source report

**Status: DONE, source only.** Base: `ddb90e9c73a72588dbe33d53b66d9b91d163151c`. Source commit: `aa88d4fb96f500a54ca31bee72d4e98bd1227840`. Evidence commit: `36109dd85a6d7e8fa279a3e27a5ed5fbf463fc72`. This report is committed separately; its commit is the one containing this file.

## Root cause and correction

The failed panel's first encode passed raw FP32 `key_features` and `values` into the sealed CPU FP64 writer. Both jet and bank reject that dtype mismatch in their shared raw adapter. `Backend.encode` now makes a separate writer-facing event batch using the actual kernel reference tensor's device and dtype for those two floating fields. It places masks and auxiliary tensors on the writer device, retains original CPU integer IDs, CPU timestamps, lengths, event order and mask values, and uses the original raw event for a nonfinite trigger's input hash. The original episode is not changed.

Inspection found one related crossing: `Backend.read` had serialized raw FP32 query key features for an FP64 saved state. The actual jet and bank kernels reject those features. The request now serializes a separate query view whose key features match the writer reference tensor. The original query hash, times, IDs, tasks, masks and intervals stay intact.

## Bounded tests and evidence

The tiny test manually constructs two real static CPU FP64 writers and FP32 input, with a three-event history including an unobserved event, uint64 keys above `2**63`, and int64 times above `2**53`. It compares the external encode state hash with the same real writer fed correctly typed events. The read test uses a real one-event state, proves raw FP32 queries fail the real kernel contract, inspects the serialized request, and intercepts dispatch before any reader subprocess. No generator history, factorization, training, panel, native probe, or model-result experiment ran.

The complete [run index](task18-kernel-stage-b-input-dtype-source-evidence/run-index.json) records exact argv, elapsed time, exit, and raw log bytes/SHA for every test invocation:

| Run | Exact argv after `.venv/bin/python -m pytest -q` | Result |
| --- | --- | --- |
| 01 RED | `tests/test_kernel_stage_b_input_dtype.py` | 2 failed with the panel's exact raw dtype error |
| 02 GREEN | `tests/test_kernel_stage_b_input_dtype.py` | 2 passed |
| 03 read RED | `tests/test_kernel_stage_b_input_dtype.py::test_external_read_request_types_query_features_for_fp64_state` | 2 failed: serialized `float32`, expected `float64` |
| 04 GREEN | `tests/test_kernel_stage_b_input_dtype.py` | 4 passed |
| 05 final | `tests/test_kernel_stage_b_source.py tests/test_kernel_stage_b_review.py tests/test_kernel_stage_b_lifecycle.py tests/test_kernel_stage_b_launcher.py tests/test_kernel_stage_b_input_dtype.py` | 62 passed in 9.51 s |

The first unprivileged `git add` attempt failed on the sandboxed `.git/index.lock`; an approved escalation staged the same files. `git diff --cached --check` flagged trailing whitespace only in immutable raw pytest logs. Rechecking all other staged files passed; the logs were preserved exactly. A read-only manifest inspection initially assumed an object, then used the manifest's actual list structure.

## Preservation and limits

The [preservation proof](task18-kernel-stage-b-input-dtype-source-evidence/preservation-proof.json) verifies 88 sorted material rows and all row/file hashes; only `validation/kernel_stage_b/production.py` changed its material row. All 79 historical rows are byte equal. The 53-file `famjet` digest remains `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`; all 15 Stage A files equal base; `requirements.lock` remains `2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1`. Historical native, failure, archive, and witness paths were untouched. The prospective source reference matches the refreshed manifest; approval, execution, and release remain null.

The changed material manifest invalidates the old binding for new-source qualification. This source work makes no accuracy, snapshot, reader, factor, panel, native, or release claim. Independent source review and a fresh binding belong to the root task.
