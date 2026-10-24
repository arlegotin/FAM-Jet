I1 — ADDRESSED. SPEC NO — QUALITY NEEDS FIXES because the fix introduces the qualified-candidate closure regression below.

## Finding verdicts

- **I1: E3 candidate storage schema mismatch — ADDRESSED.** `famjet_poc/report_inputs.py:486` now projects and validates the actual `active_static_bytes`, `wire_static_bytes` and `numeric_parameter_bytes`; `famjet_poc/report.py:85` supplies wire bytes to chart data. `famjet_poc/plots.py:94` explicitly labels the plotted storage representation. The producer-shaped regression at `tests/test_poc_report_scientific.py:62` checks both fitted families' chart values. The former unconditional `None` chart failure is removed.
- **I2: Terminal numerical subset failures rejected — ADDRESSED.** `famjet_poc/report_inputs.py:523` accepts the precise terminal numerical failure form with an error and absent score/model/rows/costs, preserves null fields, and still rejects unfinished/infrastructure cases. `famjet_poc/report.py:231` renders unavailable loss and recorded error safely. `tests/test_poc_report_scientific.py:62` covers a failed subset; `:126` covers refusal of an unfinished subset.
- **I3: Omitted E4 semantic closure — ADDRESSED.** `famjet_poc/report_inputs.py:164` invokes E4's complete selected-reference validator. `:175` invokes the measured-probe validator, with mode-probe/allocation commitments restored in `_verify_frozen_science` (`:430`). `:146` checks shared per-cell count hashes, and `:159` is called on both real normalized/native batches (`:712`). Tests at `tests/test_poc_report_scientific.py:150`, `:171`, `:208` exercise hash-valid malformed reference, forecast, counts and method identity. The temporary probe-input approach is permitted by Root's explicit clarification recorded below.
- **I4: Incomplete reader-facing report and omitted adaptation evidence — ADDRESSED.** `famjet_poc/report.py:205` renders full selected configuration identities/parameters and separate active/wire storage; `:275` renders synthetic eligibility/fallback counts; `:304` renders adapted-fit costs/candidates; `:328` renders actual robustness summaries. `famjet_poc/report_inputs.py:466` retains the real development ledger, selected adapted refs, selected reference, measured probe and cache/allocation/elapsed costs, and `famjet_poc/report.py:155` includes that transfer evidence in machine output. The projection/render/machine retention regression is `tests/test_poc_report_scientific.py:62`.
- **Minor: Unreachable CLI import assertion — ADDRESSED.** `tests/test_poc_cli.py:12` now catches the expected help `SystemExit(0)` before checking the imported modules.
- **Minor: Hard-coded plot-test interpreter — ADDRESSED.** `tests/test_poc_plots.py:9` uses the same documented `_plot_python()` selection as reporting; the retained gate explicitly supplies the installed separate environment.

## New breakage in the fix diff

### N1 — Resolved by explicit Root clarification: temporary derived validator input is permitted

`famjet_poc/report_inputs.py:175` constructs an adjusted probe with rebased nested references, serializes it to temporary `resolved-probe.json` (`:186`), computes a new content hash, and gives that derived reference to E4. I raised its compatibility with the earlier “no serializedrefrewrites” wording. Root explicitly clarified during this rereview that the restriction protects original frozen artifacts/commitments and permits a transient derived JSON solely as a runtime validator argument when original parent/nested bytes are checked first, only securely resolved I/O refs differ, original bytes/SHA remain authoritative, the derived SHA is neither retained as original evidence nor used to authorize data, and no archive write occurs. The helper meets those conditions: `paths.ref` validates the original parent and both nested refs, temporary storage is outside the archive, and the helper returns the original probe. **No open finding remains for this approach.** This is an explicit controller ruling, not an inferred exception.

### N2 — Important: Qualified candidates can now omit model/row evidence and bypass closure

`famjet_poc/report_inputs.py:581` and `:583` change model/row verification to optional key-presence checks for every candidate. The new projection (`:486`) checks qualified candidates' storage and loss but never requires `fit_ref` or `rows_ref`. Consequently a qualified entry with both references absent is accepted and skips both model and row validation, whereas the previous qualified branch directly indexed and verified both. This regresses the fail-closed requirement for the candidate ledger; the positive fixture happens to include the refs and does not exercise their omission. Require complete, correctly typed model/row references on qualified entries (and complete paired references for any post-fit scored failure), leaving absence legal only for the explicitly admitted pre-model numerical-fit failure. Add focused hash-consistent missing-reference cases for the production projection/verification boundary.

## Out-of-scope observations

None. This rereview does not reopen unchanged E4/E3 implementation or the earlier complete E5 review.

## Evidence and checks

- `docs/research/e2e-task5-fixround1-evidence/final-fix1-pytest-02.log:1` records 20 passed in 22.26 seconds with no warnings. Its receipt includes all five covering test files, the explicit report-interpreter environment, exit 0 and raw-output hash. `final-fix1-compile-02.json:1` records successful compilation with zero output. Earlier failed fixture iterations remain retained and are explained in `docs/research/e2e-task5-fixround1-report.md:19`.
- Read the complete fix package sequentially and checked changes against all six prior findings. Used a metadata-only diff pass for line anchors. No tests, protected data access, fit, benchmark, Git operation, or source mutation was performed. Only this review report was written.
- Producer-shaped public fixtures now cover the repaired schema/semantic boundaries; they still do not constitute an actual complete scientific `render_report` or copied production-run replay. Those remain Root's next validation gates after the Important issues are resolved.

## Verdict

**Fix round: Findings remain open — N2 only. SPEC NO; QUALITY NEEDS FIXES.** The four original findings and both minors have concrete repairs. Root explicitly permits the transient validated probe argument; optional qualified candidate refs still introduce a new fail-open path and require a focused repair before acceptance.
