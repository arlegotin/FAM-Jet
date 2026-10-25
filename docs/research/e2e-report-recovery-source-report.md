# Run06 report-only recovery source gate

**Decision: HOLD for independent source review.** The sealed scientific run completed its 36 synthetic cells, 16 real stages, releases, and stored inference. Its original CLI exited 1 during report assembly because the report reader compared the frozen Jet/Bank run-ID roster to the same unique receipt IDs in a different order. This source task corrects the roster predicate and adds an explicit, registered path to report the historical run. No full recovery render or scientific pipeline work was performed in this gate.

## Source and authorization

- Source commit: `5b3d3123` on current main, based on `6caddb3e`.
- Registered migration: `run06-report-order-v1`, committed at `docs/research/e2e-run06-report-migration.json`, SHA-256 `d8c2383dba7240b15f525af549a991280417a304fe86ed8e8b0840b59af721b9`.
- Original source commit: `f886e3c41517fd935a642cb83233dd72faf083b0`; original full executable identity: `b994b3ef7b770fb50db7adba3a9125f75c7c5dc1a4cd3dc3d85843d3177e1260`.
- Corrected reporter full executable identity: `786a5f03cb60bf152401c1294bd24196a97607876bf9b13ab687577dcd2bef60`. The sole changed existing executable path in the 74-file identity is `famjet_poc/report_inputs.py`. All 73 other executable and lock files match the archived originals byte for byte.
- Recovery launcher SHA-256: `c0d4503795d50899d453b6cb9ad46f48b5e3caf10d57349a4219c6ea33aa0563`. The reporting lock is pinned separately. The full old/new maps, original run index, freeze, synthetic/real releases, inference, ledger, policy/anchor, failed report guard, stderr, and exit witness are bound by the fixed manifest and code constants.

The ordinary `FrozenStudyRef.read`, `verify_run_policy`, `bind_run_policy`, `render_report`, run/resume, and all scientific implementation remain unchanged. Compatibility is accepted only by `load_report_inputs(run, compatibility_id='run06-report-order-v1', archived_source=...)`. It verifies the complete archived source and current source inventories, all 4,813 indexed run files and four indexed preparation files, and the historical policy and clock semantics before opening score rows. The original execution identity remains the freeze identity. The corrected identity is labelled reporter identity in recovered outputs. The launcher reuses existing report composition, plotting, and write helpers and keeps the original ledger and failed report untouched.

For copied-root replay, preparation is resolved beside the supplied run (`run/prep` as siblings in the archived layout, or `e2e-core-run-06-prep` beside the original). This closes the original archive index without requiring the original run location. Source byte hashing is required; “no scientific source access” for the later guarded replay means no data factory, fitting, execution, grant creation, resealing, or pipeline admission.

## Tests and source-only evidence

The first RED run of `tests/test_poc_report_inputs.py tests/test_poc_report_recovery.py` showed three expected failures: the reordered-roster helper, run-ID binding helper, and transition validator were absent (`3 failed, 8 passed`). Separate RED runs showed the launcher absent and, later, the repeated-destination helper absent. The affected tests then passed after implementation. These initial RED observations were captured in the session output; no retroactive raw RED log is claimed.

`docs/research/e2e-report-recovery-source-evidence/checks.json` records exact UTC starts/ends, elapsed seconds, exit codes, raw log byte lengths, and SHA-256 values. Its raw logs show:

| Check | Result |
| --- | --- |
| Targeted report inputs, recovery, report, scientific report, CLI, and execution-policy tests | 68 passed; 11.46 s test time |
| Compile changed Python files and tests | Exit 0 |
| Recovery launcher `--help` | Exit 0; only the fixed migration ID is selectable |
| Source preservation and original/copied-run admission preflight | Exit 0; 74 archived files exact; one changed path; both run roots admitted before score access |
| `git diff --check` | Exit 0 |

The tests cover reordered and malformed rosters, duplicates, missing/unknown IDs, swapped cell/method bindings, exact source transition rejection, a consistently rewritten policy/anchor, strict old execution APIs, fixed launcher CLI, failed attempt retention, and repeated publication destinations. Existing report and policy tests cover row/count and semantic validations on small fixtures. The copied-run preflight checks the full indexed byte inventories; it does not render or recompute the full scientific report.

## Preservation and remaining gate

The source gate did not edit the original run, its preparation, its failed report, source archive, or their clocks. The original CLI exit remains 1 and the full run duration remains 25,786.649 seconds. The separately timed future recovery cannot be attributed to that original execution. The sealed primary inference was unblinded only after all comparisons closed; this migration contains no new inferential configuration or scientific choice. External Beijing arrays retain the existing `verified_inventory_not_rehashed` status.

Independent review should inspect the exact source diff and migration admission before Root performs one actual artifact-only recovery. Full recovered Markdown/JSON/chart determinism, downstream scientific validation on the entire sealed run, and a replay with original run/source locations unavailable are deliberately pending that gate. A later unrelated downstream validation failure must be diagnosed separately rather than absorbed into this migration.
