# Reader adequacy v1 source component

This external diagnostic implements the adopted Task 18 primary numeric reader. It is not registered with `TaskModel` or the inference worker. It does not run preprocessing, training, or evaluation.

## Public API

- `ReaderSpec(family, access, width)` accepts Jet or Bank with `C128`, `C558`, or `F256` only. `input_dim`, `parameter_count`, `dense_macs`, and `feature_order` expose the analytic ledger. Actual `PrimaryReader` parameters are counted separately in the tests.
- `load_pinned_kernel(family)` resolves the first panel04 candidate for that family. It checks every retained family candidate's static export bytes and rate reference, verifies the frozen training metadata SHA, reconstructs the fixed kernel, and compares the represented writer hash. Ridge values do not select the reader kernel.
- `features(kernel, snapshot, queries, spec)` validates the fixed CPU FP64 writer, snapshot hash/layout, public queries, primary tasks, and history identity. The existing kernel advances temporary payload copies and supplies contracted diagnostics. `C` flattens `[u(8),h(8),z,b]` for each Jet anchor, or `[u(8),z]` for each Bank anchor. `F` flattens the full `[B,1,J,16,9]` `z` state, then Jet `h`, in existing axis order. Both append `[p(16),mean,contrast,age_start/t_ref,age_end/t_ref]`. Feature widths are 92/1172. Invalid derived numbers are zeroed with an explicit failure flag; support comes from the existing finite normalization/floor diagnostics, outside the learned vector.
- `PrimaryReader(spec)` owns two biased SiLU hidden layers and a biased eight-output head. Every `nn.Linear` is constructed directly in CPU FP64, so initialization draws FP64 values rather than converted FP32 values. `read(kernel,snapshot,queries)` applies frozen column statistics and inverse task target transforms. It returns `ReadResult` with `numeric_supported`, `prediction_valid`, `failure`, and deterministic support 0/1. Padded and unsupported rows never become prediction-valid. Central v2 scoring, including unconditional fallback, belongs to later orchestration.
- `fit_feature_statistics(training_rows, provenance=...)` accepts a tuple/list of ordered records `{split:'training', values: CPU FP64 [N,D], supported: bool [N]}`. It uses ordered Welford population variance and maps zero SD to 1. It rejects one-shot iterators, development rows, nonfinite data, and refitting. `unit_training` is the default for tiny source tests. Fixture fitting requires `{'scope':'fixture_only','fixture_id': nonempty_string}`. These scope markers are preserved in statics. **`original768` fitting is unavailable in this component:** the row records have no verified history/query identity, so a separate list of 768 IDs would not bind them to the frozen training inventory. A later dedicated row builder must establish that binding before production fitting can be added. No original histories are generated here.
- `export_static(require_production=False)` and `PrimaryReader.from_static(record, require_production=False)` use explicit numeric tensor records, never pickle. They enforce exact keys, tensor dtype/shape/finite state, target statistics, a separate hash of the four component Python files, and feature-fit provenance. Both reject `require_production=True`, and the loader rejects even a manually forged `original768` fit marker. Unit and fixture statics remain usable for source/numerical checks. Snapshot serialization remains in existing `state_io`. The static record carries no snapshot or raw history. `make_two_age_fixture()` returns four deterministic histories, their 256 mean/contrast queries, and independently calculated event-oracle targets; it does not fit a model.

## Scope and cost

| Arm | D | Width | Active parameters | Dense MAC/query |
| --- | ---: | ---: | ---: | ---: |
| C128 | 92 | 128 | 29,448 | 29,184 |
| C558 | 92 | 558 | 368,288 | 367,164 |
| F256 | 1,172 | 256 | 368,136 | 367,616 |

The high tier differs by 152 parameters (0.042%) and 452 MACs (0.124%). Dense MACs exclude feature standardization, kernel advancement/contractions, activation/bias work, and full-state bandwidth. No parameter or support head is padded or silently factorized.

Source tests only check bounded contracts and tiny examples. The separate numerical, fixture fit, 768-history preprocessing, feasibility, and development gates are not established by these tests.
