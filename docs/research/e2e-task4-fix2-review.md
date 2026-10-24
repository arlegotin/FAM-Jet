# E4 FIX2 scoped rereview — 24 October 2026

**SPEC: YES**  
**QUALITY: APPROVED**  
**F1 / remaining I4: ADDRESSED**

Reviewed FIX_BASE `55c6f105ae516e72c73c69436f56e1a27f482d0f` through HEAD `c319e394d160e5e1e5447c1cc65f16c18b4c0b98`, the supplied 78,263-byte review package, the complete appended repair-round-2 report, and the named RED/GREEN/final/compile/mirror evidence. Scope was the sole open atomic-output observation race and regressions in this narrow repair. The prior acceptance of I1/I2/I3/I5/I6/I7 is preserved.

At `famjet_poc/pipeline.py:160–180`, `_run_output_bytes` verifies the run root, enumerates with `os.walk`, and uses a single `os.stat` result for both file type and size. This removes the original `is_file()`/`stat()` gap. A vanished entry raises only the specifically tolerated `FileNotFoundError`/`NotADirectoryError`; permission and other I/O errors are not swallowed. Traversal errors also propagate except for disappearing subordinate entries, and loss of the required root fails closed. `observe_resources` now calls this helper at line 221.

The deterministic regression intercepts the first stat of a temporary output and performs the real atomic rename after obtaining that result. The supplied RED trace demonstrates the old second-stat `FileNotFoundError` and the resulting live-guard failure. The repaired implementation retains the successful first stat result and completes the count; the next sample counts the final file. Tests cover both the production observer and the actual `LiveStageGuard`. Host command output is stubbed to avoid sandbox `ps` denial; filesystem stat/rename behavior and guard handling are exercised. Separate observer and live-guard regressions show that `PermissionError` still propagates and blocks stage entry/completion.

The Root-authorized independent stdlib witness change at `docs/research/e2e-process-witness.py:20–33` applies the same narrow counting rule to periodic and final output accounting. Its optional output root may remain absent before creation. The diff does not change allocation caps, clocks, argv, process-group ownership or termination logic. The witness regression extracts only the counting function by AST, avoiding execution of wrapper setup or an actual campaign. The supplied mirror comparison exits 0 and records matching SHA-256 `f7d820def776bc78a05d6f39895111ef746c1a69619e083b8be5ba29b8709761` for the tracked witness and SDD mirror.

`resources.py` is unchanged by FIX2. Its final post-work sample, output-cap check including the guard receipt, genuine observer-error handling, current-tree RSS enforcement and owned-child cancellation remain in place. This repair tolerates normal transient filesystem disappearance; it does not convert arbitrary observation errors into successful admission.

Critical: none. Important: none remaining in the scoped repair. Minor: none identified. F1 is closed, completing I4 and all seven original E4 review findings.

The supplied final command `./.venv/bin/python -m pytest -q tests/test_poc_pipeline.py tests/test_poc_resources.py` records **21 passed in 1.44 s**, exit 0, wrapper elapsed 1.669881958 seconds. The compile command covers the production observer, both witness copies and the two affected test files, and exits 0 with empty output. The focused four-regression GREEN command also exits 0. These are inspected supplied results, not reviewer reruns. The initial sandbox-blocked RED invocation and the subsequent isolated-race RED trace are both retained. Root's separate audit owns verification of preserved historical and new raw evidence bytes.

No tests, Git commands, protected-data access, wrapper execution, actual campaigns, source edits or subagents were used in this rereview. This file is its only authored artifact. The old core, E1/E2/E3, worker audit guard and strict numerical comparator were not reopened or changed. Actual production feasibility, selected-fit parity, cap sufficiency, scientific results and E5 replay remain unverified and unclaimed.

Disposition: approve E4 source through FIX2. This is source acceptance; it does not release E5 HOLD or authorize an actual campaign independently of Root's remaining integration and preregistration steps.
