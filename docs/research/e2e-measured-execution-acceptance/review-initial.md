# R6 independent scoped SPEC + QUALITY review

Reviewed 2026-10-25. Scope: R6 source before actual native public qualification, not the final whole-branch/scientific completion review.

**SPEC: NO. QUALITY: NOT APPROVED.** Keep native qualification and fresh protected execution on hold pending the corrections below and scoped re-review. No scientific result verdict is made.

## Reviewed material and boundary

Requirements: `.superpowers/sdd/2026-10-16-famjet/e2e-measured-execution-brief.md`; adopted `docs/superpowers/specs/2026-10-25-evaluation-budget-design.md`, `docs/superpowers/plans/2026-10-25-evaluation-budget.md`, and `docs/amendments/2026-10-25-measured-evaluation-budget.md`. The independent resource design was consulted as context only; its discarded import/parallel options were not treated as requirements.

Reviewed source range: `17ce406d596c1a50a306c6af0d0f08769eca7c07..54427142`, including the substantive changed source, tests, preregistration, source report, and recorded evidence. Supplied review package: 142,881 bytes, SHA-256 `a925c4ad1686746830f314b800ce354d5e4c318e8a9f55c1aada845585919c86`.

This review ran no tests, fitting, benchmark, native qualification, or experiment. It did not open run04's ledger, private rows, summaries, predictions, confirmation/replication artifacts, or private data. Checks were source inspection, Git read-only comparisons, and stdlib hashing of committed source/evidence. No tracked file or Git state was written. Only this ignored review file was created.

## Findings requiring correction

### R6-1 — P1: Qualification omits production's nested samplers; serialization is per guard

References: `famjet_poc/resources.py:45`, `:90`, `:190`; `famjet_poc/pipeline.py:140`, `:918`, `:923`; `famjet_poc/protected.py:614`; `docs/research/e2e-guard-cadence-public-check.py:183`–`:218`; `tests/test_measured_execution.py:72`.

`StageLedger.stage(..., monitor=True)` creates an outer guard, then the protected action calls `evaluate_cell`, which creates a second inner guard. Both run background observations. Every `LiveStageGuard` creates its own `_sampling_lock`, so an outer observation can execute concurrently with an inner background or foreground observation. The new concurrency fixture only creates one guard and therefore does not test the actual topology. The public driver also creates only one guard and calls its `check()` from the history factory; neither E3 `evaluate_panel` nor `evaluate_equivalent_control` creates a second live guard.

Scope judgment: I interpret the brief’s serialized expensive observations to cover the simultaneously active nested guards in this one serial process, because both observe the same process tree and the original diagnosis explicitly identified the outer sampler. This does not require cross-process synchronization or reusing a disk measurement across different roots. Even under a narrower per-instance reading, the missing nested qualification is independently a spec gap.

Consequently, a passing driver receipt would not qualify the production outer-plus-inner observer contention/cost, and the source still permits concurrent expensive process-tree observations/walks in the path the amendment addresses. This conflicts with the requested serialized expensive observation and protected-like outer/per-history qualification semantics.

Correction: make production observation serialization cover simultaneously active guards (while preserving each root's full disk accounting, its allocation, forced entry/exit observations, deadline and sticky failures), and exercise the same nested structure in the public driver. Include a two-guard fixture with foreground and background calls, bounded blocked-observer behavior, and assertions on maximum simultaneously active observations. Do not change transfer/E3 bytes to obtain the coverage.

### R6-2 — P1: Public-only input boundary allows references into private run04 directories

References: `docs/research/e2e-guard-cadence-public-check.py:96`–`:106`, `:116`–`:142`.

`_rebase_ref` accepts any path beneath `artifacts/e2e-core-run-04`, rather than restricting row inputs to the public development study. `row_refs` come from a journal whose current hash is recorded but not compared to an independently committed expected journal/reference inventory before reads. A changed control or candidate `rows_ref` can therefore name a confirmation/replication row file within the old root; `load_score_rows` opens it before any scientific comparison can reject it. The within-root symlink check also allows a public-looking row path to resolve to a private location inside that root. The initial journal/cache paths are opened without a public-subtree resolution check.

This is a boundary-validation defect, not a claim that the existing journal currently contains such references. The strict instruction is that the driver is safe public-only and old private outputs remain unopened; checking the whole old run root is insufficient for that guarantee.

Correction: validate resolved inputs against the exact public development subtree or a committed public-file allowlist before every open; reject traversal and symlinks that leave the allowed public area. Bind the expected cache/journal or row-reference inventory to public provenance as appropriate. Add fixtures redirecting a row ref and a public path/symlink toward a forbidden sibling and prove the forbidden file is never opened. Fixtures must use synthetic temporary files, not real private artifacts.

### R6-3 — P2: Scientific comparison silently ignores surplus observed histories

Reference: `docs/research/e2e-guard-cadence-public-check.py:63`–`:86`; `tests/test_guard_cadence_public_check.py:25`.

The same `indexed()` function filters both expected and newly observed rows using `if row.get('history_id') not in ids: continue`. Filtering the larger archived development panel is necessary, but filtering new output permits a result containing all expected 128 rows plus arbitrary extra histories to pass and report `history_count: 16`, `row_count: 128`. The current positive and missing-coverage fixtures do not exercise this case.

Correction: permit subset selection only on archived expected rows; require the entire observed inventory to equal the declared 16-history × eight-query set, including method binding and duplicate rejection. Reject malformed/duplicate declared history IDs. Add an extra-observed-history fixture and preserve the current exact selected-configuration-label comparison.

### R6-4 — P2: Pre-freeze resume does not bind the original run's execution source

References: `famjet_poc/execution_policy.py:38`–`:82`; `famjet_poc/pipeline.py:536`–`:555`; `famjet_poc/study.py:153`–`:163`; `famjet_poc/contracts.py:158`–`:166`; `famjet_poc/protected.py:47`–`:52`, `:291`–`:301`.

The new run-policy and its byte anchor bind the policy JSON, study manifest, and clocks, but no complete execution-source identity. The manifest includes E1 and E3 identities; those exclude `resources.py`, `pipeline.py`, `protected.py`, `report_inputs.py`, and `execution_policy.py`. Therefore a pre-freeze interrupted run can resume after an execution-source change while `verify_run_policy` and the anchor still pass, reusing stages computed with the prior runner. The complete executable identity is first committed by the later freeze. Existing frozen runs do reject executable changes; the gap is the public pre-freeze part of a new run.

The adopted plan explicitly requires original new-run source/config/start/reserve matching on resume, and the brief calls for source-tampering coverage. The current source does not establish that earlier source boundary.

Correction: bind the complete relevant execution identity at initial run-policy creation, anchor it with the original clocks, and verify it before completed-stage reuse or any resumed stage action. Keep E1/E3 identities unchanged. Add a source-change resume fixture before freeze as well as a no-change resume case; do not use a source-compatibility exception.

## Requirements supported by the inspected source

- The strict dated JSON values are correct: policy ID `e2e-measured-execution-v2-20261025`; 28,800 global seconds; 1,800 synthetic-cell seconds; 1,800 completion-reserve seconds; 1,610,612,736 RSS bytes; 34,359,738,368 output bytes; prefix `budget-v2-20261025`. Integer/string types and key sets are checked. The original start/global/work deadlines are anchored; an old-policy run cannot be silently accepted as the new version.
- Normal `pipeline.run` passes scientific policy admission to probes, development, timing, transfer fitting, stress, synthetic cells, and real methods. Admission occurs before a new scientific stage action/data factory and requires its declared ceiling to fit before the work deadline. Monitored retries retain the first stage clock. Real per-method ceilings remain 1,200 seconds. Release/report retain access to the reserve. The external owner witness remains independently necessary for hard termination.
- Full protected IDs receive the new dated prefix. The exact validator retains phase roots 2026102401902/1904/1905, 16/256/256 per stratum, 36 cells, K16 shape, eight query IDs and all eight methods. Confirmation and replication remain 3,072 histories each. Old unprefixed inventories fail the new validator. No changed training/development inventory generation, targets, weights or inference was found.
- The six-role gate recomputes model numerical identity, shape, family and reader specification, including Bank, and exact canonical real normalization against the committed baseline. It runs after public fitting and before freeze. Freeze revalidates it. Report loading rechecks gate bytes/result and stage/freeze reference agreement. Runtime gate code uses the committed baseline and new selected references; it does not load old ignored private outputs.
- Within one guard, expensive observations are serialized, reuse is bounded to 0.25 seconds, background observation remains 0.1 seconds, entry/normal exit force observations, and each check inspects sticky failure and monotonic expiry. Failed or blocked observations latch failure and teardown is bounded. Whole-tree current RSS and full scanned output values remain the cap inputs. Cancellation remains confined to suspects intersecting a fresh descendant observation; no new foreign-process termination path was introduced. The multi-guard limitation is R6-1.
- The driver uses the intended 16 development IDs (four per regime), K16 archived selected checkpoints, five simple controls plus Laguerre, fixed worker limits and seed, original E3 evaluator calls, explicit 180-second work allowance and 200-second total alarm, one-thread environment, and exact scientific projections. Selected Jet/Bank old configuration labels are explicitly bound before mapping to logical method names. Laguerre coordinate/state audit validation is invoked without converting an existing strict-prediction failure into success. Its input/whole-output and topology defects are listed above.
- Normal CLI commands remain unchanged. No cross-root public import, evaluator parallelism, scientific-grid/model retuning, or completed native/scientific result claim was introduced.

## Recorded verification and preservation audit

I independently hashed the raw logs referenced by all four `commands*.json` inventories: every byte count and SHA-256 matched. The final recorded affected-suite log contains `124 passed in 13.09s`; its command receipt reports exit 0, elapsed 13.367191334 seconds, 181 log bytes, SHA-256 `9a5b6c2dfb2d1b44cdf4cf175ed14ff1211a25c7850e7e9323a30cba7285e4c3`. These are verified recorded results, not tests rerun by this reviewer.

The recorded compile, diff-check, help and preservation commands also have matching logs. All changed/preserved file byte counts and hashes in `source-hashes.json` match current source. A read-only range diff for the core tree and listed preserved files returned exit 0 and zero bytes. This confirms preservation of `famjet/**/*.py`, E1 contracts/data/models, E2 inference, all six E3 modules, transfer, both locks, study config and Beijing manifest in this range. The committed baseline is exactly 6,593 bytes with SHA-256 `dd49488b03f78fb7b0818ed837fd53b6272304c0f8497030b4a239c78c5abe43`.

The report honestly discloses that interactive RED attempts lack captured raw UTC/byte/hash receipts. Those attempts cannot independently be reconstructed from the committed report; no fabricated evidence is asserted. Existing copied-replay tests use the older unit-test report fixture and do not directly demonstrate the newly added scientific gate/policy relocation path. The new gate tests validate a gate reference directly, but do not exercise the full run orchestration's mismatch-before-freeze/protected-factory boundary. These are coverage limitations relevant to the correction suite, even where the inspected ordering is sound.

## Cannot verify at this gate

Actual native parity, resource peaks, contention, useful cadence cost, 180-second qualification feasibility, six freshly recomputed identities, full-run budget feasibility, complete protected coverage, inference/report success and scientific copied replay remain unverified. Native qualification is explicitly NOT RUN. Nothing in the recorded unit tests substitutes for those future gates.

After correction, rerun only appropriate affected fixture/source checks, refresh exact evidence/source hashes, and obtain scoped source re-review before Root's single bounded public qualification. Preserve all old private outputs unopened/excluded and all original clocks. Final whole-branch review remains a separate step after actual completion.
