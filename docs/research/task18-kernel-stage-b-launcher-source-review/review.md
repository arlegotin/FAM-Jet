# Task 18 runtime launcher source review

**SPEC: YES. QUALITY: APPROVED.** Base `08ba541aa32cc8f1ea83833cccb9962291f0d625` to head `c4bee4bee52114427bfb07ab9d4a04d5280e20dc`.

## Spec compliance

- `validation/kernel_stage_b/authority.py:120`: `project_launcher` constructs canonical `ROOT/.venv/bin/python`, checks root, venv, bin, cfg, resolved executable target and target-byte SHA, and returns the lexical launcher. It preserves the canonical Runtime executable and image identity.
- `validation/kernel_stage_b/authority.py:909`: qualification requires the fixed lexical launcher in bound/current worker and parent vectors. `validation/kernel_stage_b/authority.py:1326` retains exact Runtime comparison, checks active `sys.executable`/prefix/base-prefix, and validates literal worker/parent vectors and their hashes at lines 1382–1390.
- `validation/kernel_stage_b/authority.py:854` and `:880`: the adopted amendment is required in the source inventory and is the one new compatibility addition. The manifest diff adds that row and changes only the authority row; the prospective Plan diff changes only its source Ref. `tests/test_kernel_stage_b_launcher.py:105` checks 88 rows and historical-row compatibility.
- The full package changes no protected `famjet/`, Stage A, lock, binding01 witness/archive, native timing, helper lifecycle, or scientific source path. `docs/research/task18-kernel-stage-b-launcher-source-evidence/protected-material-proof.json:1` records the 53/15/lock pins, 79 historical rows, 88 current rows and null prospective approval/execution/release. Root's separate custody check should confirm those on-disk claims.
- No binding02 witness or native release is included. The final focused log at `docs/research/task18-kernel-stage-b-launcher-source-evidence/10-final-covering.log:2` records 58 passed; earlier failed invocations remain recorded in the index and logs.

## Strengths

- `tests/test_kernel_stage_b_launcher.py:24` exercises lexical symlink success, wrong target/hash, missing/escaping cfg and symlink loop. `tests/test_kernel_stage_b_lifecycle.py:146` exercises inactive environments and literal parent/worker argv. The tests directly exercise the production authority functions with controlled fixtures.
- The source inventory and prospective Ref are tightly scoped; no schema or unrelated production source edits appear in the package.

## Issues

- **Critical:** none.
- **Important:** none.
- **Minor:** none.

## Focused checks and assessment

- **Risk: qualification could accept an unhashed current argv.** Checked the call site at `validation/kernel_stage_b/authority.py:1414` and the preceding live checks at `:1382` and `:1389`; the current six/five vectors are compared to the lexical launcher and `vector_hash` before qualification. Bound plan validation occurs at `:1412`.
- **Risk: the large one-line JSON diff could conceal other mutations.** Parsed only its old/new JSON lines: the manifest changes are the new amendment row plus authority bytes; the prospective Plan changes only `evidence.source.bytes` and `evidence.source.sha256`.
- **Task quality: APPROVED.** The implementation is small, fail-closed for the specified launcher conditions, and covered by the reported focused final run. This review makes no native or dependency-installation claim.
