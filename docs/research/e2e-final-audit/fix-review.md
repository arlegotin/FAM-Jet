# Single scoped rereview of the final fix wave

Review base: `ed7060b40b1c2b88239232819e2ef9d0e372d6d7`.
Reviewed HEAD: `4b21c7ac9b1289aba993dbad9b91c33375e96b58`.
Package: `.superpowers/sdd/2026-10-16-famjet/e2e-final-fix-review.diff`, three commits, 47 changed files.

**Gate verdict: PASS for the source correction; proceed to the one bounded actual v2 report-only check.** I1, I2, I3 and M1 are ADDRESSED. No new blocking defect or out-of-scope scientific change was identified in the fix diff. The actual v2 render is still outstanding and is not represented by this source verdict as already passed.

This is the exactly one scoped rereview requested after the original whole-branch review. I read the fix brief, adopted prospective amendment, full implementer report and the complete fix package in bounded passes. The large one-line migration manifest was parsed and its complete maps checked programmatically rather than printed as a wall of hashes. I inspected adjacent unchanged helpers only where necessary to understand changed behavior. No subagents, code/index/HEAD edits, scientific execution, report render, or test-suite reruns were performed. The only file written by this reviewer is this requested review.

## Disposition of every original finding

### I1 — ADDRESSED: ordinary report destinations are checked before writes

`famjet_poc/report.py:418` adds `_check_report_destination`, called at the start of `render_report`. It enumerates Markdown, implicit JSON, chart data, chart directory, all three SVGs, renderer receipt and invocation files, then resolves their paths before admitting output. This closes the release-JSON overwrite and scientific-stage inventory pollution described in the original finding, including parent and chart-child symlink aliases.

The guard protects the resolved run, its associated preparation tree, and the identified fixed project inputs. The only in-run exception is the pipeline's reserved `report/final.md`, with every planned path under that reserved directory, no existing planned outputs, and the latest ledger generation explicitly running the report stage. Ordinary external output remains supported. The unchanged atomic writer creates exclusive temporary files in the admitted destination parents; the plotting cache similarly uses a new temporary directory beside the admitted charts. No deterministic temporary path bypass was introduced.

The added tests cover direct release JSON overlap, scientific-stage descendants, parent aliases, chart directory and child aliases, preparation-child aliases, and the `.json` suffix collision. They assert unchanged input bytes on rejection. The existing reserved-stage/external replay test remains green. The captured initial four failures and subsequent preparation-child failure are preserved, followed by the final green evidence.

The required historical-source consequence is handled explicitly, under `docs/amendments/2026-10-25-final-report-output-safety.md`: a separate fixed `run06-report-safety-v2` admission binds original execution → witnessed v1 reporter → current guarded reporter. The ordinary frozen-executable API is unchanged. The v1-to-v2 file-map differences are exactly `famjet_poc/report.py` and `famjet_poc/report_inputs.py`; there is no general scientific-source waiver.

### I2 — ADDRESSED: affected unit tests no longer require ignored historical runs

`tests/test_measured_execution.py`, `tests/test_poc_report_inputs.py` and `tests/test_poc_report_recovery.py` now use compact public/temporary fixtures for normalization, public-stage metadata, frozen policy/anchor values, and controlled publication failures. The committed normalization is checked against the public selection baseline; the historical policy fixture is rebuilt from the committed freeze and admitted through the normal historical verification path before mutation.

Two tests that genuinely need the full copied run/prep archive are explicitly opt-in through `FAMJET_RUN06_INTEGRATION=1`, with an availability prerequisite and documented invocation. They still exercise real complete-archive admission, copied source, source-byte mutation, and forbidden scientific-work instrumentation. They were executed separately, rather than treated as covered by their ordinary-suite skips.

The affected suites passed with run04, run06 and the copied run06 archive roots unavailable: **131 passed, 2 intended integration skips**. The receipt records restoration of the same root inodes. This is direct evidence for the missing-workspace dependency that the original final run in an old workspace could not establish.

The archive mutation unit cases now reach the archived-source check before opening the temporary run's missing freeze. Their broad exception assertions are limited negative checks and do not independently establish successful full admission; the separately executed positive integration tests and exact committed-map test provide that evidence. No blanket skipping or production admission relaxation was introduced.

### I3 — ADDRESSED: stale monitor fixtures now reach their intended accounting cases

The four affected parameter cases in `tests/test_kernel_stage_a_preflight.py`, `test_kernel_stage_a_preflight_fix1.py` and `test_kernel_stage_a_preflight_fix2.py` now supply unique launch IDs, finite start times, valid unreaped/completed lifecycle states, and authority-phase ordering. The observer fixtures append declarations/completions instead of rewriting the journal; the delayed observer case uses a sampling handshake. The live-authority case establishes the phase before declaring its helper.

The expected 110-byte late-observer accounting, 90/110-byte final reconciliation, 130-byte authority accounting, and memory-cap/foreign-process outcomes remain asserted. Production monitor, lifecycle and authority source is unchanged. The four original failures remain documented; the final supported-environment suite is green.

The additional changed test in `tests/test_kernel_stage_a_native_process_fix2.py` is a justified consequence of full verification: the recorded first broad run exposed an 80-ms launch/cleanup fixture race. Its fixture-only outer allowance is now 0.5 seconds, and it explicitly asserts sampling occurred and, for the partial-journal case, that the malformed journal was actually written. It retains failure status, incomplete accounting, a captured return code, and the expected RSS total. This tests the intended journal failure rather than accepting a pre-scenario deadline failure. No production cap was relaxed.

README instructions now use the project `.venv` and run inference separately, preserving the real 256-MiB process-lifetime RSS assertion while avoiding Torch collection contamination.

### M1 — ADDRESSED: historical link corrected without changing canonical output

`reports/famjet-poc/README.md` now identifies the canonical report's relative-link erratum and links directly to `../../docs/research/e2e-laguerre-actual-diagnostic-report.md`. This is the acceptable historical-artifact correction requested by the original review. The canonical Markdown and all six other deterministic files remain byte-identical.

## New breakage and scope

**New Critical findings: none. New Important findings: none. New Minor findings requiring correction: none.**

The new v2 launcher was read in full and compared with v1. Its only differences are its description and the two fixed compatibility-ID literals. Publication isolation, new-attempt directories, input-tree exclusion, failure receipts, volatile plot-log capture and atomic directory publication retain the reviewed v1 behavior. The ordinary renderer guard is not invoked by that launcher; the launcher instead retains its separate new-directory/input-tree admission, so this does not bypass the repaired ordinary renderer path or allow output into the sealed run.

V2 admission separately verifies the unchanged v1 manifest/launcher pins, complete old/prior/current executable maps, independently pinned v2 launcher, reporting lock, original identity/index, run/prep inventories and original failure values. Recovery metadata distinguishes the current reporter and prior reporter. Old execution and current report provenance are not conflated.

The additional journal-test correction is within the requested test repair/verification scope, supported by a preserved concrete failure. The compact fixture and README changes are within I2/M1. No changed model, fitting, selection, data, protected execution, inference, plotting mathematics, scientific budget, release, or original-clock source was found in this wave.

## Verification evidence inspected

| Recorded check | Result |
| --- | --- |
| Supported project `.venv`, suite excluding `tests/test_poc_inference.py` | 1774 passed, 58 skipped, 2 subtests passed; 247.45 s; exit 0 |
| Isolated inference file | 22 passed; 0.64 s; exit 0 |
| Affected unit suites with all three historical archive roots unavailable | 131 passed, 2 intentional integration skips; 11.88 s; exit 0 |
| Opted-in complete-archive admission tests | 2 passed, 38 deselected; 4.21 s; exit 0; no rendering |
| Final report/recovery/native targeted tests | 56 passed, 2 intentional integration skips; 5.01 s; exit 0 |

The original red results, first post-fix broad-suite timing failure, isolated timing check and two interrupted intermediate broad runs remain in the evidence directory. Unknown intermediate timestamps are null, not reconstructed. The final broad/inference/archive-unavailable/integration receipts include argv, environment, UTC bounds, exit code and log hashes.

I independently performed these read-only checks during this rereview:

- All 74 original map entries match Git source at `f886e3c4`; all 74 prior map entries match the reviewed v1 source at `ed7060b4`; all 74 current entries match the working HEAD. Their canonical map digests match `b994b3ef…`, `1bd8aca2…` and `5d3b8e9f…`, respectively.
- The sole prior-to-current executable differences are the two reporting modules named above.
- All seven canonical output sizes/hashes match the unchanged actual-recovery index.
- All log sizes/hashes in the final-fix evidence index match their committed log files.
- The v1 manifest remains `881cf66a7a5b099e5620ab4e4d17699b1c1c005052e67dabb649ec1642b00e27`; the v1 launcher remains `9bcb1724fd16793314f5fcd5f8faef87d78fccfc70343705540ff92f206eb83e`.
- The v2 manifest is `e4a5b0942c4f9b8717660ada23416650b00117cbdde6d03b2aefe51ce94ae066`; its launcher is `35ef59c74a792fba1d34280ad647a9729aee3832e102cc7bbf68c14b565221bb`.
- Git comparison shows no changes to the original execution source/record, actual v1 recovery proofs, core `famjet` source, protected APIs, execution policy, main lock or reporting lock.

I did not independently rerun these suites, hash the entire multi-GB run/prep inventory, recreate the archive-unavailable exercise, or execute the actual v2 render. The tests and historical bulk-preservation outcomes above are the recorded evidence, not new executions by this reviewer.

## Explicitly outside this rereview

- The original scientific conclusions, older architecture implementations and unrelated historical gaps were not reopened; the original whole-branch review supplies their coverage and limits.
- Concurrent hostile filesystem changes between destination preflight and writing, arbitrary malicious modification of the validator itself, and general filesystem sandboxing are not claims of this local report-path guard.
- The exact v1 output bytes remain a historical result. A v2 report has different recovery provenance; full MD/JSON byte equality to v1 is neither asserted nor required. Scientific payload and chart preservation must be checked in the pending actual v2 run.
- Missing optional full-archive integration assets produce an explicit skip; this is not a claim that Git contains the bulk data. The documented opt-in tests were separately executed here by the implementer.
- General timing-test portability is not established by the fixture repair; this verdict is for the supported project environment and the changed tests.

## Final gate

**Source rereview PASS; all four findings ADDRESSED.** The executor may perform the already authorized single bounded actual v2 report-only verification in a fresh output directory, preserve its separate receipt, compare the scientific payload/charts with v1, and confirm old canonical/proof/input bytes remain unchanged. That execution is the remaining handoff gate, not another review or scientific run. No further implementation/review loop is requested by this scoped assessment.
