# Task18 narrow native process compatibility report

Status: **DONE_WITH_CONCERNS**. Implemented source is ready for root's scoped SPEC+QUALITY review; it is not self-accepted. No scientific release, complete native Stage A integration verdict, six-factor construction, model read, fixture/reference campaign, fit, training, dataset/corpus/panel/calibration/bootstrap or protected execution occurred. Actual scientific factor constructions and reads: **0 / 0**. Synthetic setup-ledger fields in the pre-existing authority tests are test inputs, not actual constructions.

Dispatch BASE was clean current main `691a9a0bb686ba3ba4aa708df28f7ef74aed9277`. Source commit: `8ece30b70c56fc26e1e212f1e33c4637741e6354` (`Support macOS process identity in external Stage A monitor`). Source/evidence delivery is a separate subsequent commit; its full hash is reported in the delivery message to avoid a self-referential committed hash. No branch, worktree, push or subagent was used. The existing six findings were not reopened. Existing accepted preflight source evidence is unchanged; this adapter requires its own root review.

## Implementation and contract

Only `validation/kernel_stage_a/authority.py`, `commands.py`, and `monitor.py` changed executable behavior. The README, new focused external tests, and a three-line controlled-observer artifact injection in the existing fix1 timeout test accompany them. The timeout control still launches/kills/reaps a sleeper; its changed observer vector now has a matching test artifact descriptor instead of bypassing the new production artifact check.

`authority.py` binds fixed `/usr/lib/libproc.dylib` `proc_pidpath` with explicit `c_int`, `c_void_p`, `c_uint32` arguments, `c_int` result, and 4096-byte bounded buffer. Installed SDK `libproc.h:102` and `sys/proc_info.h:749` were read; the supplied max4096 ruling is adopted. Binding, call, return/errno, path/NUL/length and file-hash failures stay structured, with actual lookup interval. No subprocess fallback or guessed framework path exists. The seal-comparable runtime retains the resolved launcher/hash separately from this interpreter's successful own-image path/hash and fixed ps/Git descriptors, without transient PID/time. Helper files are rehashed immediately before source launch. Git witness-write failures now also kill/reap the exact owned child.

Launch vectors and their hashes are unchanged. Expected native Python display replaces only element zero with the observed image path. Reader bootstrap, flags, event path and canonical finite positive bounded deadline remain exact. Native raw `comm`/`args` are retained as display strings; native samples do not present an invented `argv` vector. Source witnesses alone contain declared vectors/hashes.

The numeric table is parsed before selected root/descendant/owned-observer image lookups. Missing identity text retains RSS. Duplicate PID rows retain maximum RSS and every possible parent edge, then fail ambiguous identity instead of dropping a descendant. Each selected sample keeps its raw strings, RSS, parent, sample interval, lookup outcome, and resolved evidence kind. Live native Python needs its own applicable successful exact image, parent and display. Every exact helper also needs its declared artifact, launch instance, lifetime and permitted phase. Contradictory successful image/hash, other native errors, wrong phase/parent/display, unknown helpers and ambiguous generations fail closed.

Only exact source-owned already-exited ps/Git with compatible samples and completed/reaped witness may use `image_evidence=unavailable_exited` plus `launch_evidence=source_owned_launch` for ESRCH. This is source-launch attribution, not unavailable per-PID proof being invented. A successful lookup after the declared reaping bound is ambiguous and fails. A successful live Git sample remains fully charged if the monitor kills the run before its end event, preserving fix2.

Root separately authorized the evidence gap fix: “record_baseline may emit one bounded observer_sample for its actual selected root/descendant+owned-ps sample, preserving inner ps RSS/lookup/launch provenance for late reconciliation.” `record_baseline` emits that one sample batch separately from helper launch/end witnesses; no reader request or numeric response protocol changed. Late inner evidence missed by outer sampling remains charged. Per-PID maxima avoid charging a duplicated retained sample twice; recognized authority Python is counted once with Git, and conservative outer/inner observer peaks are added. Event parsing failures retain full native RSS with baseline zero. Final missing baselines are fully charged.

Python history has deliberately conservative semantics: earlier successful applicable image samples remain in `process_samples`; a later ESRCH sample stays a separate unresolved record and stops the run without borrowing PID-only proof. A worker exiting after its last successful sample, with no later unresolved sample, retains that historical proof for that sample. A never-proved exited Python always stops unresolved. No new self-image protocol, PID cache, generic process family or generation carry-forward was added.

## Exact verification commands and outcomes

New-control RED/GREEN command `N`:

```sh
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_native_process.py
```

Focused covering command `C`:

```sh
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_native_process.py tests/test_kernel_stage_a_preflight_fix2.py tests/test_kernel_stage_a_preflight.py tests/test_kernel_stage_a_preflight_fix1.py -k 'native or monitor or authority or observer or baseline or f3 or f5 or same_interpreter or prospective'
```

All attempts, including failed implementation attempts, are retained here. Raw saved outputs are durably preserved in `docs/research/task18-kernel-stage-a-native-process-evidence/` (the original ignored copies also remain beside this report); intermediate covering summaries overwritten by the final run are listed verbatim below. The full scientific suite was intentionally not run, following the brief.

| Order | Command | Exit | Actual output / seconds | Saved output |
|---|---|---:|---|---|
| 1 | N initial RED | 1 | `8 failed in 0.06s` | first terminal output; missing APIs/identity behavior |
| 2 | N saved equivalent RED | 1 | `8 failed in 0.05s` | `red.txt` |
| 3 | N GREEN attempt1 | 1 | `2 failed, 6 passed in 0.05s` | `green-attempt1.txt` |
| 4 | N GREEN attempt2 | 0 | `8 passed in 0.04s` | `green-attempt2.txt` |
| 5 | C first covering | 1 | `2 failed, 24 passed, 24 deselected in 1.40s` | `cover-attempt1.txt` |
| 6 | N late-event controls | 0 | `10 passed in 0.23s` | `late-red.txt` (existing implemented behavior passed) |
| 7 | N retention/call RED | 1 | `2 failed, 10 passed in 0.26s` | `retention-red.txt` |
| 8 | C second covering | 0 | `30 passed, 24 deselected in 1.63s` | `cover-attempt2.txt` |
| 9 | N inner-sample RED | 1 | `1 failed, 12 passed in 0.26s` | `inner-red.txt` |
| 10 | C inner-sample GREEN | 0 | `31 passed, 24 deselected in 1.64s` | `cover-attempt3.txt` |
| 11 | N generation RED | 1 | `1 failed, 14 passed in 0.29s` | `generation-red.txt` |
| 12 | C generation GREEN | 0 | `33 passed, 24 deselected in 1.65s` | terminal output |
| 13 | N duplicate-row RED | 1 | `1 failed, 15 passed in 0.30s` | `duplicate-red.txt` |
| 14 | C duplicate-row GREEN | 0 | `34 passed, 24 deselected in 1.76s` | terminal output |
| 15 | N native-charge RED | 1 | `2 failed, 16 passed in 0.37s` | `charge-red.txt` |
| 16 | C charge GREEN | 0 | `36 passed, 24 deselected in 1.76s` | terminal output |
| 17 | N witness-cleanup RED | 1 | `1 failed, 18 passed in 0.37s` | `cleanup-red.txt` |
| 18 | C final covering | 0 | `37 passed, 24 deselected in 1.67s` | `final-focused.txt` |

Initial failures were expected missing native APIs and behavior. Attempt3 found a test fake's bound-function signature mistake (fixed with staticmethod) and completed-but-unreaped helper handling. Covering attempt5 found that enriched source witness fields needed an exact core projection for the explicit synthetic sampler seam, and that the controlled fake observer needed its matching artifact injected. Later RED failures proved RSS survived event parsing failure, native call errors were structured, late inner samples were consumed, post-reap successful lookup was ambiguous, duplicate parents could not drop RSS, authority RSS was counted once, final missing baselines were fully charged, and witness-write failure reaped its child. All those named failures are resolved in the final covering output. Existing fix2 live/cap/foreign controls pass.

Also exit0, with no output:

```sh
.venv/bin/python -m py_compile validation/kernel_stage_a/authority.py validation/kernel_stage_a/commands.py validation/kernel_stage_a/monitor.py tests/test_kernel_stage_a_native_process.py
.venv/bin/python -m py_compile .superpowers/sdd/2026-10-16-famjet/task-18-native-process-check.py
git diff --check
git diff --cached --check
```

During evidence packaging, `git diff --cached --check` reported trailing whitespace in the verbatim pytest RED output. A separate explicit `git diff --check 691a9a0bb686ba3ba4aa708df28f7ef74aed9277 HEAD -- docs/research/task18-kernel-stage-a-native-process-evidence` returned exit2 for those exact raw lines. They are intentionally preserved byte-for-byte, with matching original/durable hashes. The source-only `git diff --check 691a9a0bb686ba3ba4aa708df28f7ef74aed9277 HEAD -- validation/kernel_stage_a tests` returned exit0. This packaging check does not represent a source/test failure; the final test output remains37 passed.

The fixed installed-header reads, frozen-byte comparison, package hash calculation, source-commit operations and artifact validation are read-only or source management, not scientific execution. The selected tests use controlled samplers and fake Git/sleeper children; some existing authority tests also observe their own runtime mapping/hash. No native ps launch is hidden inside the selected tests: the existing observer-timeout control replaces it with its bounded Python sleeper.

## Bounded native functional sequence

Exactly one sequence was run via approved `require_escalated` execution; no rejected or failed native attempt and no favorable-race retry occurred. The shell execution returned exit0; the native JSON reports PASS and **0.867311832960695 seconds**, within aggregate30s. Stage/reader each have a watchdog at most10s, ps at most1s, exact Git at most5s; the aggregate deadline is absolute. Explicit small cleanups remain charged. Reproducer command:

```sh
TASK18_SOURCE_COMMIT=691a9a0bb686ba3ba4aa708df28f7ef74aed9277 TASK18_SOURCE_DIFF_SHA256=e54105e540129e17dab0b55c8940a7388773475f07e191054c8feaf68c18ae19 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 .venv/bin/python .superpowers/sdd/2026-10-16-famjet/task-18-native-process-check.py /tmp/task18-native-process/native.json
```

Exact output:

```text
{"status": "PASS", "seconds": 0.867311832960695, "report": "/tmp/task18-native-process/native.json"}
```

The durable copy is `docs/research/task18-kernel-stage-a-native-process-evidence/native.json`. The exact executed check body is durably copied as `task-18-native-process-check.py` in that directory, with original→durable equal-hash mappings in the verification JSON. The original ignored script/logs are retained. The durable harness uses the same directory depth, so its repository-root resolution remains valid; no native controls were rerun during packaging. Native execution used the dirty source at BASE plus tracked diff SHA256 `e54105e540129e17dab0b55c8940a7388773475f07e191054c8feaf68c18ae19`. Its additional then-untracked test SHA256 was `1c15a60eb95f011d3cce4ca1b7231010ce2f778bc8d9e8beffb7aa68da435c69`; harness SHA256 `1b8ebf8ef0a6d991e85459ad848dfa5ecd13157798b004eb7f60c053cbf48518`. These are preserved in `native-source.json`. Final source subsequently added duplicate-row retention, final/authority charge corrections, witness-write cleanup, their controls and README. Those later branches passed synthetic controls and were not native-rerun; do not present this native snapshot as accepted final source authority.

| Exact native launch | PID | Time / disposition | Actual evidence |
|---|---:|---|---|
| `commands.stage_command` | 9196 | 0.15266412496566772s; SIGKILL -9, reaped | Incomplete FIFO seal held without EOF; exact parent/image/native display; no authority/backend entry; empty stdout/stderr |
| `commands.reader_command` | 9198 | 0.688252666965127s; SIGKILL -9, reaped before stdin close | Zero request bytes; ordinary imports/post-import baseline reached; exact parent/image/display; empty stdout/stderr; no request deserialization/profile/read |
| outer ps during stage | 9197 | reaped by communicate | RSS1851392; exact display/parent/source witness; ESRCH explicitly absent per-PID kernel proof |
| inner reader baseline ps | 9199 | reaped by communicate | RSS1851392; exact display/parent/source witness; ESRCH; preserved `observer_sample` |
| outer ps during reader | 9200 | reaped by communicate | RSS1851392; exact display/parent/source witness; ESRCH |
| exact `git -C ROOT rev-parse HEAD` via authority | 9201 | 0.008171957917511463s; exit0, reaped | Successful live kernel image/hash; exact vector/witness; returned BASE |
| exact `git -C ROOT status --porcelain` via authority | 9202 | 0.014034291030839086s; exit0, reaped | Successful live kernel image/hash; exact vector/witness; dirty-source output retained |

No scientific supervisor verdict was completed. Git's raw ps display was **not sampled**; the source vector/witness and live native image are established, and exact display matching/exit races are covered synthetically. This is an explicit native coverage limitation; no alternate display policy was introduced to hide it. Stage and reader `comm` were actually truncated `/opt/homebrew/Ce`, while raw args began with the exact observed long Python.app image. The exact stage seal flags/bootstrap/FIFO path and reader bootstrap/event path/deadline matched the single declared display form.

Observed stage RSS22167552; reader baseline225984512; later reader sample226459648 bytes. These are descriptive compatibility observations, not a scientific peak/memory forecast. Actual reader baseline event stream had four rows; reconstructing emitted default-JSON bytes from the saved rows (removing harness-added identity annotations) yields2242 bytes, of which1385 bytes are the one observer_sample row. The monitor adds these event/report bytes to ordinary charged output. There is no new sampler process: the event exposes the existing baseline sample. Saved raw verification artifacts total54309 bytes; records/report add documentation overhead outside any scientific allocation.

## Runtime, artifacts and preserved boundaries

Stable runtime mapping (complete object in the verification JSON):

- Resolved launcher `/opt/homebrew/Cellar/python@3.13/3.13.5/Frameworks/Python.framework/Versions/3.13/bin/python3.13`, SHA256 `a1f6d9dc20d4787a84dc2fe782094a7bac5946f49a962aa0af48a02f0e8d5bc5`.
- Observed image `/opt/homebrew/Cellar/python@3.13/3.13.5/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python`, SHA256 `619a54258d9057844c176bfb41b56501ee8d00966929c899c2aae73c7ddac506`.
- `/bin/ps`, SHA256 `16d273739778797145fd22cba76113d2aaa99c759313d56ef87ed56a16bca083`.
- Resolved Git `/opt/homebrew/Cellar/git/2.49.0/bin/git`, SHA256 `03d4a6c5328d4a1ce84eba2765664284b1fb2414d9e657358733056a89a95954`.
- CPython3.13.5 arm64; Decimal1.70/libmpdec4.0.1. `_decimal` extension SHA256 `012ccc5fc549ca1da531e00957e6f1807e364971fcd55209f51d5545d788e585`.

`docs/research/task18-kernel-stage-a-native-process-verification.json` binds final source paths/hashes, runtime mapping, raw artifacts/hashes/byte counts, exact native source snapshot, final tests and remaining nulls. Its inventory covers the three source files, README, focused new tests, modified controlled timeout test, reproducer and raw evidence directory. This full report is also durably copied as `docs/research/task18-kernel-stage-a-native-process-report.md`. This report and that JSON are new evidence; old records remain byte-for-byte unchanged.

Production package independently rehashed to unchanged `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`. No `famjet/` file changed. No lock/dependency, fixture definitions, cache/source guard, numerical reader/request protocol or frozen input changed. Byte comparison to dispatch BASE confirms:

- `requirements.lock`: `2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1`.
- `fixture-descriptors.json`: `44501a0e469f72cdf14d24d3c622ba3c611590cf96e7dd875bd391c324c4d5f0`.
- `frozen-training-metadata.json`: `9ca422cc04f35de1a94bf65a579f37be5122a382cb635c47e7d39d49fa92509c`.
- Prospective seal: `6d331f63a24415b2675ef9aeb6ee9f3e54c6f1b214b44a977b0c228bbdfa3230`.
- Existing preflight source acceptance: `a843920bbf5dd7e1dbe792da2b2d404e1a8648ea288fba58e64e1a2aa72d38f5`.

Remaining scientific nulls are unchanged: `implementation_review`, `represented_rate_records`, `static_exports`, `resource_measurement_boundary_seal`, `fresh_launch_snapshot`, `output_directory`, and `root_stage_A_release`. Source-owned launch attribution assumes trusted exact direct helper launch; path-file hashes do not certify all mapped bytes, observations do not certify arbitrary argv byte boundaries or continuous/adversarial image identity, and RSS sampling does not establish allocator peaks. Other-platform native binding, missing proof, unknown processes and ambiguous reuse fail closed. Root owns review, source acceptance, fresh seal and any later scientific release.
