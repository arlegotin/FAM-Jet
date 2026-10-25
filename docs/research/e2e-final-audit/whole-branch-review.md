# Final whole-branch review

Reviewed range: `78f7ba8..ed7060b40b1c2b88239232819e2ef9d0e372d6d7` (295 commits). This is the single final whole-branch review, read-only except for this requested review document. No subagents, source/index/HEAD changes, experiments, scientific reruns, or old run04 private-outcome inspection were performed.

**Ready for handoff: With fixes.** Three Important issues and one Minor issue are consolidated below. I found no basis in the inspected paths and evidence to reject the completed narrow scientific result or the successful registered recovery. Ordinary report output safety and the test suite need correction before an unqualified handoff. This is not an assertion that every changed line or every historical mechanism has been independently revalidated.

## Strengths

- The delivered claim is appropriately narrow. Both independent synthetic intervals include zero; the report calls superiority inconclusive. It shows the stronger bucket mean losses, the poor frozen-transfer results, and the real-trained Bank advantage. It does not turn a fixed-reader result into a learned-writer, all-family, agent, or novelty claim.
- The reviewed memory update uses the previous state in the coupled Jet recurrence. Snapshot advancement and the reader interface preserve causal isolation. Observed-event masks, stable target sums, training-only normalization, and scale-only contrast inversion are represented explicitly rather than hidden in aggregate scores.
- The finite ridge fitting and selection path records objective, configurations, feature scaling, model identity, static storage, cache costs, and recurrent state separately. Equal persistent-state budgets do not conceal static reader storage or deployment timing. Laguerre is correctly a numerical control with no invented deployment latency.
- Conditional inference uses paired history-level differences and the declared stratified estimator, not queries as independent replications. Report admission verifies the paired roster, cell identities, score rows, release and stage inventories. Invalid labels and prediction failures have explicit treatment.
- The report recovery is unusually careful about historical truth: original CLI exit 1, original clocks and original source remain intact; the corrected reporter has separate identity. The fixed migration validates complete old/new executable maps and sealed inputs rather than granting a general exemption to changed code. The external recovery launcher protects input trees and separates volatile attempt receipts from deterministic outputs.
- The actual portable replay evidence goes beyond a second render in the same directory: original run, prep, and archived-source locations were made unavailable. Seven deterministic outputs matched, while original inventories were restored and checked. The human documentation clearly says that the bulk archive and prepared arrays are local/ignored rather than pretending the Git checkout contains them.

## Findings

### Critical

None identified in the reviewed scope.

### Important I1 — Ordinary report output can overwrite sealed scientific inputs

**Locations:** `famjet_poc/report.py:418`, `famjet_poc/report.py:435`, `famjet_poc/report.py:440`; inventory consequence at `famjet_poc/report_inputs.py:295`.

`render_report` validates inputs, then writes derived JSON, Markdown, chart data and plots without first checking whether their destinations overlap the sealed run. For example, the documented ordinary command with `--run RUNROOT --out RUNROOT/release/release.md` writes its machine report over `RUNROOT/release/release.json`. The hidden sibling `.json` is especially problematic: the user selected a Markdown destination, but the command can destroy the release needed to replay the run. Even a new output inside a sealed non-report stage changes that stage's exact file inventory and makes subsequent admission fail.

I verified the destination behavior with a no-write, in-memory mock of input loading and `_write`: the ordinary renderer accepted this destination and issued writes to both `release/release.json` and `release/release.md`. The source has the same unguarded final writes for scientific reports, preceded by additional plot writes. No actual run was modified. This finding concerns the ordinary report path/future current-source runs; the registered run06 recovery launcher already has an input-tree guard, and its completed canonical outputs are not affected.

**Why it matters:** an artifact-only report command should not invalidate or overwrite the evidence it has just accepted. Input validation before publication is insufficient when publication itself can alter those inputs.

**Fix:** preflight every generated path before any output write, resolving aliases/symlinks and rejecting overlap with sealed input files or scientific-stage inventories. Preserve the pipeline's deliberate reserved `report` stage (`famjet_poc/pipeline.py:997`) and legitimate external output directories. Add a small regression proving rejection leaves input bytes unchanged, including the implicit JSON/chart destinations. The smallest behavioral fix belongs at the renderer entry, before input/output side effects; changing only documentation leaves the destructive ordinary command available. Since `report.py` is in the exact 74-file identity, use an explicit dated report-only amendment and preserve the already approved historical reporter and recovery provenance. Do not silently replace the R7 map or rewrite canonical results to make new source look like the old reporter. Any additional transition must enumerate exact source differences and preserve strict scientific-source checks, rather than broadly ignoring reporter hashes.

### Important I2 — The ordinary test suite requires ignored historical run archives

**Locations:** `tests/test_poc_report_recovery.py:58`, `:82`, `:109`, `:294`, `:311`, `:335`, `:356`; `tests/test_poc_report_inputs.py:171`; `tests/test_measured_execution.py:398`, `:422`, `:470`. User-facing command: `README.md:102`.

These tests read `artifacts/e2e-core-run-06`, `artifacts/e2e-run06-original-archive/run`, or public metadata from `artifacts/e2e-core-run-04` unconditionally. None of those trees is tracked (`git ls-files` returned no entries). There is no archive prerequisite fixture or skip around the positive admission/publication tests. A clean checkout following the documented environment/test instructions therefore gets missing-file failures; the complete run06 archive alone also does not supply the older run04 paths. A fresh interpreter inside the existing developer workspace does not test this condition.

Some tests nominally checking archive mutation accept `FileNotFoundError`, so absence can also make a negative case pass before the intended mutation is reached. That should not be mistaken for coverage of a complete positive admission.

**Why it matters:** maintainers cannot run the documented test command from the delivered source, and important regression coverage silently depends on the original operator's local history. This is distinct from the correctly documented requirement to possess bulk data for historical scientific replay.

**Fix:** make small unit tests use committed compact fixtures or explicit temporary fixtures: policy/anchor bytes, public normalization, and public stage metadata do not require a 2-GB run. Keep genuine complete-archive admission/replay tests as explicit integration tests with a clear availability prerequisite and documented opt-in command; skip only those integration cases when the verified archive is absent. Publication failure/receipt tests can isolate admission with an explicit fixture while retaining a separate real admission integration case. Do not blanket-skip mutation guards or weaken the admission checks. Verify fixture independence with the ignored archives unavailable, without rerunning science or unblinding old private outcomes.

### Important I3 — Four retained monitor tests no longer reach the accounting behavior they claim to cover

**Locations:** `tests/test_kernel_stage_a_preflight.py:360` (assertion `:381`), `tests/test_kernel_stage_a_preflight_fix1.py:147` (assertion `:172`), and both parameters of `tests/test_kernel_stage_a_preflight_fix2.py:11` (assertion `:32`). Current contract: `validation/kernel_stage_a/source_lifecycles.py:25` and `validation/kernel_stage_a/monitor.py:321`, `:796`.

The supplied fresh broad-suite log reports all four cases failing with `monitor common failure`, before their expected memory-cap/foreign-process verdicts. Inspection explains why: their synthetic observer/git helper declarations omit the required unique launch identity and lifecycle fields. `SourceLifecycles.declare` requires a nonempty `launch_id`, finite `launch_start`, and a valid unreaped/completed state; the authority helper must also have a launch time inside the authority phase. The old minimal dictionaries do not satisfy that contract.

Evidence read: `artifacts/e2e-handoff-validation-01/full-suite-except-inference.log`, the four fixture bodies, and the current source-generation/phase validation. The run completed with 9 failed, 1757 passed, 56 skipped and 2 subtests; five other failures concern lexical project-interpreter expectations in the temporary environment and are not attributed to this defect. The executor subsequently reported a targeted project-`.venv` result of 4 failed/14 passed: all five interpreter-path failures disappear and the same four malformed-fixture failures remain. This review did not rerun the suite.

**Why it matters:** the ordinary suite is red, and these regression tests no longer establish late-declaration accounting, final reconciliation, or live-authority helper charging. The monitor's rejection of malformed fixture evidence is not a reason to relax the monitor.

**Fix:** update these fixtures to emit valid, ordered, unique lifecycle metadata under the current schema, preserving their intended late arrival/stop conditions and expected accounting amounts. Prefer controlled clocks/handshakes over adding more tight wall-clock thresholds. Keep separate malformed-lifecycle rejection coverage. Verify the affected tests under the supported project environment, then finish the required suite checks. Update the README test instructions to use project `.venv` and run `tests/test_poc_inference.py` separately from the rest of the suite: its 256-MiB process-lifetime RSS ceiling is otherwise affected by Torch collection. That split is an environment requirement, not permission to omit the inference tests. Preserve all historical executable snapshots and scientific evidence.

### Minor M1 — The historical conditioning-diagnosis link is broken in the published report

**Locations:** `famjet_poc/report.py:168`, `:188`; rendered link at `reports/famjet-poc/final.md:486`.

The link target is `docs/research/e2e-laguerre-actual-diagnostic-report.md`, a repository-root-relative string used as a Markdown-relative link. From `reports/famjet-poc/final.md` it resolves under `reports/famjet-poc/docs/research/`, which does not exist. The underlying diagnosis file exists, but a reader cannot reach it through this link.

**Fix:** give future reports a destination-correct or stable link. Because the present report bytes are canonical recovery evidence, a working direct link and explicit erratum in the bundle README is an acceptable correction for this historical artifact; do not rewrite the seven canonical files merely for link polish.

## Requirements alignment and scientific assessment

The binding adopted completion is the fixed-writer CPU64 study in the October 24 core-delivery design, its linked model/data and conditional-inference contracts, the October 25 evaluation-budget design, and the sealed-report-recovery design. It supersedes the expectation that every originally envisaged architecture and training regime must produce a competitive result. The current claims respect that narrowing.

- The entered eight-method roster, Jet4/Bank8 state sizes (9345 B for K16/V8 and 1665 B for K12/V1), finite candidate selection, shape-matched transfer, real-trained mode, and separate reporting of static/resource costs align with the adopted scope.
- Saved evidence supports completion of all 36 synthetic cells and 16 real method stages, releases, inference, and public fitting, followed by the preserved original report-order failure. It supports a successful report-only recovery and portable replay, not a successful original CLI exit.
- Extracted canonical primary values agree with the human claim: confirmation Bank-minus-Jet effect `0.03535376646223771`, interval `[-0.019711263002521226, 0.09041879592699664]`; replication `0.03968307886432539`, interval `[-0.012747850914834755, 0.09211400864348554]`. Neither establishes superiority. H=3072 per panel, with 12 strata of 256 histories, matches the adopted allocation.
- The conditional interpretation excludes variation from retraining, reselection, alternative corpora/preprocessing and unentered models. Beijing clustering keeps all stations together; 28-/56-day sensitivity is finite-period descriptive evidence. Native RMSE/MAE and contrast inversion are distinguished from standardized losses.
- The observed real-trained Bank advantage and stronger simple summaries are plainly disclosed. Failed earlier gradient/MLP/bootstrap/calibration/coordinate attempts remain failed. Current successful ridge/conditional inference is not evidence that those older failures were repaired.

## Deferred-observation triage

The supplied deferred/parked ledger was read as historical context, not automatically treated as an unresolved defect list.

| Observation | Review disposition |
| --- | --- |
| Task 1 default-device FP64 fixture | Current `famjet/ops.py:37` explicitly builds on CPU, then transfers. The identified source defect is closed. Broader environment/profile gates are not inferred from that fix. |
| Task 2 and other entries saying review/implementation pending | Historical workflow states; later completed adopted study/recovery evidence supersedes those pending labels. They are not fresh defects by themselves. |
| Task 6 Task21-only wording versus Task20 pilot | Later adopted completion explicitly includes the 192-history pilot and independent confirmation/replication allocation. No current authorization gap identified. |
| Task 8 extreme cancellation and padded reduction | Current exact-target source uses stable sums with overflow fallback; the rational/padding cases are present in `tests/test_target_arithmetic.py`. This closes the reference-arithmetic concern for the entered v2 path; it does not erase historical learned-state cancellation failures. |
| Task 9 required-interval zero-sample diagnostic | Current reservoir code handles both required intervals for contrasts/change-sign; dedicated target-arithmetic coverage exists. No continuing recent-interval-only defect identified. |
| Tasks 14/15 FP32, neural and full-mixer caveats | Retained as implementation/qualification limits. Current study does not claim those families were scientifically defeated or validated by fixed-writer results. No broad architecture rereview asserted. |
| Task 16 Gaver/associative controls | Bounded Gaver component acceptance and unsuccessful associative reproduction remain explicitly distinct. Deferred supplementary competitors stay unentered. |
| Task18 deferred plots | Canonical report includes three SVG figures plus chart data and renderer receipt. Requirement satisfied. |
| Task18 native per-phase attribution fix | Later targeted regression source for post-authority/failed-copy attribution was inspected; historical acceptance evidence exists. This is not a fresh certification of the entire native supervisor. Newly observed stale fixtures are I3. |
| Task18 tight 0.5-second tests/report-clock wording | Tight real-clock fixtures remain a portability/flake risk, not evidence of a current scientific time-budget violation. I3 asks for deterministic fixture timing where feasible. No broader timing-test rewrite is required without a concrete failing contract. |
| StageB preparation/buildability/native classification and input-dtype entries | Historical staged gates, not claims of unrestricted production readiness. Final documentation preserves narrowed scope and intervening failures. The current CPU64 selected study does not certify all StageB execution paths. |
| E3 lower requested LRU ignored | Current cache attachment/caller checks reject incompatible limits; no silent lower-LRU override identified. |
| E3 prefix preparation costs | Current costs include fit/evaluation/persistence and shared cache preparation, with explicit amortized fields. Conservative standalone charging is disclosed; no continuing omitted preparation-cost finding. |
| E3 actual matrix/E4 execution deferred | Actual run06 completion evidence supplies the later execution; source acceptance alone is not being substituted for actual results. |

## Risk-based coverage and verification

The complete 525,371,029-byte original-base diff package was available, and the 3,214,686-byte source/test/config package and changed-file index guided direct final-source inspection. I did not dump or claim line-by-line coverage of the complete raw package. Review concentrated on paths that can change the result, violate causal/state contracts, admit invalid evidence, or prevent handoff.

**Read in full or near-full relevant passes:** adopted core/evaluation/recovery specifications; model/data, inference, delivery and execution contracts; PoC data/contracts/cache; fixed-writer and Jet memory; exact oracle; execution policy/resources/worker; the report admission module; the canonical human report; primary README, bundle README and completed-result note; baseline adaptation/license declarations; focused report/recovery/target-arithmetic tests; actual recovery/replay index, proof, harness and owner summaries. Full/near-full here describes the named focused documents/modules, not all their transitive dependencies.

**Read in selected critical sections:** model feature construction/fitting/persistence checks; study scoring, fallback, development/prefix accounting and causal evaluation; synthetic inference estimator/validation; real transfer fitting, inversion, evaluation and release; pipeline stage/resource/release/report orchestration; wire loading and limits; deployment timing/comparator capacity; Beijing preparation; report composition/chart data; core metrics and ExpBank; measured-execution tests; native monitor lifecycle/authority-phase paths and the newly failing fixtures. Qualification tails, some orchestration helpers, and older architecture/training implementations were not comprehensively reread.

**Direct read-only checks performed:**

1. Reviewed HEAD matches the requested `ed7060b4` identity; initial checkout state was clean.
2. Rehashed the seven canonical output files and matched their recorded sizes/hashes.
3. Compared all 74 archived execution-source files and current reporter files with the migration maps; only `famjet_poc/report_inputs.py` differs among those existing paths. Verified the actual recovery/replay receipt and witness references against their recorded hashes/sizes.
4. Parsed only selected fields from the 45-MB canonical JSON to check the primary panel values and claim alignment; did not dump or manually inspect every raw prediction.
5. Confirmed all six archived public selected models use `t_ref=1.0`, consistent with the selected real/synthetic time convention. No nonidentity time-scale transport defect affects these selected fits.
6. Confirmed ignored-archive test dependencies, checked the broken relative link, and performed the in-memory no-write report-destination check for I1.

**Evidence inspected, not independently regenerated:** original execution inventory/failure record; recovery and portable replay receipts/witnesses; prior 98-test R7 acceptance evidence and earlier entered/inference verification records. The portable proof records 4813 run files, four prep files and 74 source files unchanged, with seven identical outputs. I did not independently rehash all 4813 bulk files or extract/rebuild the tarball in this review. No experiment, fit, inference calibration, report replay or unchanged test suite was rerun by this reviewer.

During review the parent supplied a new broad-suite result (9 failed/1757 passed/56 skipped/2 subtests) and separately reported 22 isolated inference tests passed. I inspected the broad failure log for I3. The parent subsequently reported 4 failed/14 passed in targeted project-`.venv` reproduction, isolating the four stale fixtures and clearing the five temporary-environment interpreter-path failures. Final post-fix suite verification remains an executor obligation; this document makes no blanket green-suite assertion.

## Explicitly declined to judge

- **Every historical implementation line and raw prediction:** the branch includes a 525-MB evidence-heavy diff. Risk-based source/evidence passes were used; unread code is not certified defect-free.
- **Universal architecture novelty or all-family competitiveness:** excluded by the adopted claim boundary, and not established by the entered fixed-writer experiment. No external literature audit was performed.
- **Learned writers, dense keys, generic full-state readers, language/agent tasks and multi-budget frontiers:** unentered in the adopted finite completion; their absence is disclosed rather than treated as a defect in this result.
- **Repairs of historical neural/gradient/coordinate/bootstrap failures:** those failures are preserved and cannot be declared resolved by a different selected reader or inference method.
- **Independent full scientific replication and all raw-data rehashing:** forbidden/unnecessary for this final read-only review; conclusions rely on inspected source and the preserved actual execution/replay evidence, with direct checks noted above.
- **Old run04 private outcomes:** deliberately not opened; only source references and permitted public model/normalization metadata were considered.
- **A nonidentity time-scale transfer API:** all selected public fits have identity `t_ref=1`. General transport outside that selected configuration was not certified and is not required to validate these numbers.
- **Universal finite-sample confidence coverage or future-population Beijing significance:** not claimed by the adopted conditional Welch/finite-period analysis; no new statistical calibration was performed.
- **Other hardware/OS/interpreter combinations and native kernel execution:** the delivered lock and native gates are platform-specific. This review does not generalize them to Linux, arbitrary venv paths, cloud/GPU systems, or every native supervisor branch.
- **Independent legal/license and upstream-source fidelity audit:** read the repository's baseline adaptation/license declarations and data attribution, but did not independently audit every upstream codebase or provide legal clearance.
- **Public hosting of the bulk sealed archive:** local ignored retention and portability are the adopted delivery scope; documentation explicitly states that Git alone cannot replay it. That disclosure does not excuse I2's undeclared unit-test dependence.

## Final assessment

**With fixes.** The inspected implementation and actual evidence support a completed, carefully bounded PoC and an honest inconclusive primary result. Address I1–I3, record the final supported-environment test outcome, and correct M1 without rewriting canonical recovery evidence. No new scientific run, retuning, expanded comparison or historical outcome relabeling is called for by these findings.
