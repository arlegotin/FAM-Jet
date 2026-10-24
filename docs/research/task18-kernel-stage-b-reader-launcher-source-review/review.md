# Task 18 reader launcher source review

**Range:** `38093b1ec1d0489a5d3d6247f76ce8baa07d6e74..9c4b4b3017ddaa97267b9e8c35b68991bc1bc6db` (three commits). **SPEC: YES. QUALITY: APPROVED.** Source only; HOLD for fresh binding and independent release decisions.

## Strengths

- `validation/kernel_stage_b/production.py:405-414` retains the real Stage A six-element reader command, deadline, environment, dispatch call, and runtime identity. The changed gate compares its lexical argv[0] with `project_launcher(root, runtime)`. That existing function checks the fixed `.venv/bin/python` path, canonical target, and target SHA-256 before returning the lexical path. The unchanged Stage A `python_launch` checks the same canonical target and hash immediately before the owned dispatch proceeds to `Popen`. The original `reader Python image mismatch` error remains for wrong literal argv[0].
- `tests/test_kernel_stage_b_reader_launcher.py:74-137` exercises the real command builder with a CPU FP64 static writer/state/query fixture. Its interception occurs at `owned_reader_dispatch`, checks the entire vector and deadline, and invokes the actual pure Stage A `python_launch`. Negative cases cover canonical-base and alternate-symlink argv[0], plus wrong canonical target and hash, all before dispatch. The pre-existing dtype test's controlled launcher stub was minimally adjusted.
- Retained RED output shows the actual `reader Python image mismatch` on the positive path, with four failures and one pass; retained GREEN shows five passes; the final six-file covering invocation records 67 passes. The run index preserves argv, elapsed time, exit codes, and raw output byte hashes. I inspected these records; I did not rerun tests or launch a reader.
- The manifest's only changed material row is `validation/kernel_stage_b/production.py`; the prospective plan changes only `/evidence/source/sha256` and leaves approval, execution, and release null. The custody proof records 88 material rows, 79 equal historical rows, 53 unchanged package files, the unchanged lock hash, and 15 unchanged Stage A files. The durable report matches its SDD mirror byte for byte. Whole-tree custody verification remains with the root reviewer.

## Issues

- Critical: none.
- Important: none.
- Minor: none.

## Declined to judge

- Prior accepted adapter, native image, and subprocess behavior: outside this narrow source correction; the relevant unchanged Stage A launch boundary was inspected only for compatibility.
- Panel results, fresh source binding, approval, and release: no such execution or decision is part of this source-only gate.

## Assessment

**Ready for the next source gate: yes.** The correction resolves the lexical-versus-canonical identity mismatch while preserving the actual command and both identity checks. The retained test evidence and scoped manifest/reference changes support the report. Fresh binding is still required for the changed material before panel execution.
