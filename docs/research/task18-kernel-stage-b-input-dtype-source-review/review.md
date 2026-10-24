# Task 18 input dtype source review

## Spec Compliance

**YES — spec compliant for the task-scoped source correction.** At `validation/kernel_stage_b/production.py:305-323`, both families use a separate writer event view whose key features and values follow the actual kernel reference tensor. The stream still slices events in original order, with integer IDs and timestamps untouched. `validation/kernel_stage_b/production.py:329-343` hashes a raw event on the nonfinite path, preserving the input hash's original FP32 meaning. At `validation/kernel_stage_b/production.py:384-390`, the request serializes a separate, correctly typed query feature view after checking the original query hash. The prospective plan changes only its source hash reference (`validation/kernel_stage_b/prospective-plan.json:1`); the material manifest changes only the production row (`docs/research/task18-kernel-stage-b-source-evidence/source-manifest.json:1`).

**⚠️ Outside this review:** The preservation proof reports 88 sorted material rows, 79 historical rows byte equal, 53 `famjet` files at the protected digest, 15 Stage A files byte equal, the lock digest, and null approval/execution/release (`docs/research/task18-kernel-stage-b-input-dtype-source-evidence/preservation-proof.json:1`). Those are whole-tree byte assertions and need the root's separate audit. No native, binding, reader subprocess, factor, or panel result is implied.

## Strengths

- The writer fix uses `dataclasses.replace` and tensor conversion without modifying the original episode (`validation/kernel_stage_b/production.py:305-317`). Masks and auxiliary tensors move to the writer device while timestamp and identifier tensor dtypes remain intact.
- The new test drives both jet and bank through real static CPU FP64 writers and compares complete state hashes against the correctly typed writer path (`tests/test_kernel_stage_b_input_dtype.py:19-104`). It includes an unobserved event, timestamps above `2**53`, uint64 keys above `2**63`, and checks raw event fields and hash afterward.
- The query test proves the real kernel rejects FP32 query features, then intercepts dispatch before a reader subprocess and verifies the serialized FP64 request can be consumed by that kernel (`tests/test_kernel_stage_b_input_dtype.py:107-162`). It checks original query hash and precision-sensitive IDs and time.
- The packaged logs show the observed writer dtype error for both RED cases and the query serialization failure before correction; the final covering log reports `62 passed in 9.51s` (`docs/research/task18-kernel-stage-b-input-dtype-source-evidence/01_red.log:81`, `03_read_red.log:74`, `05_final_covering.log:2`). The run index records all five invocations with argv, elapsed time, exit code, log bytes, and SHA (`docs/research/task18-kernel-stage-b-input-dtype-source-evidence/run-index.json:1`).

## Issues

### Critical (Must Fix)

None.

### Important (Should Fix)

None.

### Minor (Nice to Have)

None.

## Assessment

**Task quality: APPROVED.** The conversion is confined to external writer and reader inputs, and the focused tests exercise the real family kernels while keeping dispatch intercepted. Read-only review of the supplied three-commit package; no tests or native probes were run here.
