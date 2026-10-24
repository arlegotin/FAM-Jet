# Task 18 external reader launcher source correction

**Status: DONE, source only. HOLD for independent review and fresh binding.** Base `38093b1ec1d0489a5d3d6247f76ce8baa07d6e74`; source commit `58014373c8f3b542b978d621f3c83652115526aa`; evidence commit `998aecaabc71e329e50e83ba038ef69993cbefbc`. This report is in the commit containing this file.

## Cause and correction

Panel 03 encoded all 96 jet histories, then stopped before its first reader subprocess with `reader Python image mismatch`. The real Stage A `reader_command` places the lexical project `.venv/bin/python` in argv[0]. Stage B compared that literal with the resolved `Runtime.executable`, so it rejected the valid launch before the owned reader boundary.

`Backend.read` now compares the unchanged command's argv[0] with `project_launcher(root, runtime)`. That existing authority function checks the fixed project venv, its canonical target and its bytes against the runtime hash, then returns the lexical launcher. The Stage A owned dispatch still calls its unchanged `python_launch`, which checks the canonical target and hash and retains the expected image separately. The original six-element command, `-I`, `-c`, bootstrap, event path, represented deadline, runtime identity, vector hash, and subprocess lifecycle are unchanged. The prior event and query dtype correction remains intact. The controlled query dtype test received only the minimal launcher gate fixture needed to reach its serialization assertion.

## Tests and retained evidence

The new CPU FP64 static writer test uses the real Stage A `reader_command`. It intercepts only `owned_reader_dispatch`, asserts all six original vector elements and deadline, and calls the pure Stage A `python_launch` inside that interception to verify canonical target and hash. It rejects canonical base and alternate symlink argv[0] values, plus incorrect runtime target or hash, before dispatch. No reader subprocess, native probe, history generator, factorization, training, or model-result experiment ran.

The [run index](task18-kernel-stage-b-reader-launcher-source-evidence/run-index.json) records exact argv, elapsed time, exit code, and raw stdout/stderr bytes and SHA-256 for every invocation:

| Invocation | Exact test selector after `.venv/bin/python -m pytest -q` | Result |
| --- | --- | --- |
| 01 RED | `tests/test_kernel_stage_b_reader_launcher.py` | Exit 1; 4 failed, 1 passed. The positive case hit `reader Python image mismatch`; the canonical argv case exposed the old gate accepting the wrong literal; wrong target and hash cases exposed the old gate's lack of launcher validation. |
| 02 GREEN | `tests/test_kernel_stage_b_reader_launcher.py` | Exit 0; 5 passed in 0.62s. |
| 03 cover | `tests/test_kernel_stage_b_source.py tests/test_kernel_stage_b_review.py tests/test_kernel_stage_b_lifecycle.py tests/test_kernel_stage_b_launcher.py tests/test_kernel_stage_b_input_dtype.py tests/test_kernel_stage_b_reader_launcher.py` | Exit 0; 67 passed in 9.63s. |

The [custody proof](task18-kernel-stage-b-reader-launcher-source-evidence/custody-proof.json) verifies 88 material rows with only `validation/kernel_stage_b/production.py` changed, 79 historical rows byte equal, the 53-file `famjet` package hash `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`, lock hash `2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1`, and all 15 Stage A files byte equal. All prior source, native, failure, and witness archives remain retained. The prospective source reference matches the refreshed manifest; approval, execution, and release remain null.

## Limit

This is source behavior and custody evidence only. The changed material invalidates binding 03 for this source. Independent review and a fresh binding are required before any panel execution or release decision.
