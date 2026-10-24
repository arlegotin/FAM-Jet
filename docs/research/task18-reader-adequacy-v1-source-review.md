# Task 18 reader adequacy v1: first source component review

## Spec Compliance

**SPEC NO.** The six requested source and test files are present. The closed `ReaderSpec` and actual MLP ledger implement D=92/1172, C128=29,448, C558=368,288, F256=368,136 parameters, with CPU FP64 tensors and no support head or rank factorization (`validation/reader_adequacy_v1/contract.py:42`, `validation/reader_adequacy_v1/reader.py:84`, `tests/test_reader_adequacy_v1.py:29`). Fixed kernel resolution checks retained rates/statics, writer hash, target metadata and t_ref (`validation/reader_adequacy_v1/contract.py:73`). Feature order, mask-aware support, failure, copy advancement, frozen target inversion and explicit static records are implemented (`validation/reader_adequacy_v1/reader.py:36`, `validation/reader_adequacy_v1/reader.py:141`, `validation/reader_adequacy_v1/reader.py:168`). The production feature-fit provenance requirement is incomplete; see Important issue below.

**Cannot verify from this task diff:** Root owns independent whole-tree byte pin/evidence verification. The source report records 15 passing focused tests and ten retained invocations (`docs/research/task18-reader-adequacy-v1-source-report.md:12`); I did not rerun tests. Numerical equivalence, 16-key reconstruction, gradients, tiny fit, original768 feature fitting, worker isolation, feasibility and development are later gates, so their absence is not a source finding and source acceptance would not release experiments.

## Strengths

The implementation reuses existing kernel advancement and contractions, keeps the reader outside `TaskModel`, checks target statistics against pinned metadata on export/load, and preserves separate fixture statistics (`validation/reader_adequacy_v1/reader.py:36`, `validation/reader_adequacy_v1/reader.py:168`, `validation/reader_adequacy_v1/reader.py:178`). The tiny tests assert actual parameter counts, ordered feature values, masks, snapshot/query immutability and static round-trip (`tests/test_reader_adequacy_v1.py:29`, `tests/test_reader_adequacy_v1.py:46`, `tests/test_reader_adequacy_v1.py:76`). The deterministic fixture constructs all 16 keys at two times without fitting (`validation/reader_adequacy_v1/fixtures.py:16`). Evidence logs show the final focused invocation passed cleanly (`docs/research/task18-reader-adequacy-v1-source-evidence/10-green.log:1`).

## Issues

### Critical

None.

### Important

- `validation/reader_adequacy_v1/reader.py:101`, `validation/reader_adequacy_v1/reader.py:119`, `validation/reader_adequacy_v1/reader.py:132`, `validation/reader_adequacy_v1/reader.py:196`: An `original768` fit checks a separately supplied list of 768 IDs and a count of 6,144 supported feature rows, but each row contains only `split`, `values` and `supported`. No check binds those values, their query order, or their training split to the claimed histories. A caller can supply the pinned ID list alongside arbitrary training-tagged rows and export/load a static with `require_production=True`. This defeats the promised training-only production provenance and can contaminate the controlled comparison. Require row-level history/query identity and validate the complete ordered inventory against the frozen training metadata, or keep the production fit/static path unavailable until that binding exists. Add a focused rejection test using mismatched row identities.

### Minor

- `validation/reader_adequacy_v1/reader.py:74`: A schema-valid zero-query batch reaches `kernel.features`, which returns empty diagnostics, then indexes `diagnostics['failure']` and raises `KeyError`. Return an empty `FeatureBatch` with empty support/failure diagnostics, consistent with the kernel's zero-query behavior. This is outside the fixed Q8 campaign but affects the public adapter contract.

## Assessment

**QUALITY NEEDS_FIXES.** The reader architecture and fixed-source validation are coherent, but production feature statistics can acquire the original768 identity without being derived from those histories. The zero-query edge case is a smaller robustness gap. Focused cross-interface checks inspected `famjet/memory/_fixed_writer.py:223` for query advancement/empty diagnostics, `famjet/memory/jet.py:125` and `famjet/memory/expbank.py:92` for contracted fields/support, and `famjet/eval/oracle.py:83` for fixture window semantics. No tests or source/Git changes were run or made.
