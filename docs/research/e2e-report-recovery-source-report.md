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

## R7 review repair, round 1

The independent review at `.superpowers/sdd/2026-10-16-famjet/e2e-report-recovery-review.md` returned **SPEC: NO; QUALITY: CHANGES REQUESTED** for five findings. Source repair commit `42940514` (base `3056df79`) addresses R7-R1 through R7-R5. The earlier source identities and evidence above describe the first submitted gate; the following identities supersede them for review of this repaired gate:

- Current detached migration SHA-256: `881cf66a7a5b099e5620ab4e4d17699b1c1c005052e67dabb649ec1642b00e27`.
- Current reporter full executable SHA-256: `1bd8aca2d561f7412995c87dd183f908918c5f0ad0aef2006c75f3362f3c0703`.
- Current launcher SHA-256: `9bcb1724fd16793314f5fcd5f8faef87d78fccfc70343705540ff92f206eb83e`.
- Original execution aggregate remains `b994b3ef7b770fb50db7adba3a9125f75c7c5dc1a4cd3dc3d85843d3177e1260`; its complete 74-file archived map, all frozen science, original clocks, exit 1, and failed report remain unchanged. Only `famjet_poc/report_inputs.py` differs within the existing executable inventory.

### Resolution by finding

| Finding | Source repair and reproducing fixture |
| --- | --- |
| R7-R1, preparation write guard | The launcher resolves the preparation sibling before any output directory creation and rejects output under run, preparation, or archived source. Six cases cover both `run`/`prep` and `run-name`/`run-name-prep`, checking that all sentinel files and directories remain unchanged. |
| R7-R2, independently trusted launcher | `report_inputs.py` now pins the reviewed launcher digest in code, independently of the detached manifest. A copied launcher with changed bytes and a consistently rewritten manifest launcher hash is rejected by the production admission helper. The reporting lock has the same independent fixed-pin test. |
| R7-R3, failure and publication truth | The launcher records `admission_state=unverified` until exact full source/run/prep admission succeeds, then records the verified identities and original failure before downstream work. Failures retain admitted provenance, partial output hashes, renderer evidence, error, clocks, and RSS. A pending-publication receipt precedes the directory rename; only a successful rename is followed by `completed`. Controlled post-admission and publication failures both leave failed receipts. |
| R7-R4, fixture matrix | Added scientific-source/lock, added/missing executable, reporter-byte, altered target-map, freeze/release/ledger, policy schema/type/deadline/source and coordinated lock/launcher mutations. A copied-run preflight blocks all opens under the original run location and instruments protected run/freeze/release calls as forbidden. Controlled output fixtures cover human/machine success provenance, failure receipts, repeated publication, and deterministic output inventory. Existing targeted report tests cover row/count/paired history and CLI behavior; existing protected/scientific validators remain unchanged. |
| R7-R5, volatile plot metadata | The unchanged plotting helper still writes its invocation JSON and log during rendering. The launcher moves both into the separate recovery receipt, including raw log bytes, hashes, command, and elapsed time, then removes them from the published report directory. A fixture compares two complete output inventories with different invocation metadata and requires exact equality; an orphan log from partial plotting is also captured. |

### Recorded RED and GREEN

`docs/research/e2e-report-recovery-source-evidence/fixround1/red.json` records an actual pre-fix run of ten finding-focused cases: **6 failed, 4 passed, 15 deselected**. The raw `red.log` contains the preparation-root failures, missing independent launcher verifier, absent admitted failure provenance, false completed publication receipt, and nondeterministic invocation files. The later orphan-log and reporting-lock cases were also observed failing individually in the session before their fixes; their session outputs are not represented as separate raw files.

`fixround1/green.json` records exact commands, UTC start/end, elapsed time, exit status, log lengths and hashes. The final targeted suite of report inputs, recovery, report composition, scientific report fixtures, CLI, and measured execution policy passed **98 tests in 17.07 s**. Compilation, fixed-ID launcher help, `git diff --check`, and source preservation all exited 0. The preservation log confirms both original and copied run/preparation inventories and the sole changed file among 74 source paths.

The corrected renderer was **not** run on the complete scientific artifacts in this source repair. The controlled output fixtures isolate launcher orchestration and preservation; they do not claim full scientific validation, real SVG hash equality, or a complete original-locations-unavailable report replay. Root's actual recovery and independent replay remain gated on review of this repair. No fitting, data generation, grant creation, resealing, or scientific pipeline execution occurred in the fix round.
