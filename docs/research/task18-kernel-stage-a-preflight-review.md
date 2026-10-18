# Independent external Stage A preflight source review

**SPEC: CHANGES_REQUIRED.**

**QUALITY: CHANGES_REQUIRED.**

Six Important findings require correction before source acceptance. No scientific execution was performed or released by this review. Pending scientific identities and native integration are reported separately from the source defects below.

## Scope and strengths

Reviewed the supplied source/test diff for BASE `62456be3e6e6cbe3b2a058bd38ade744edc3c628` to HEAD `93be808f488ef5237121dcdcf75b7ba6903d4712`, the complete brief/report, proposed invocation/seal and relevant verification records. The task-reviewer template and prior adopted contracts governed this scoped review; accepted kernel mathematics/source were not broadly re-reviewed.

- `validation/kernel_stage_a/descriptors.py:39` encodes the fixed fixture definitions, with marker/tie semantics and exact represented boundary neighbors. `:73` and `:78` preserve candidate/group/row order and the four excluded O slots. The applicable inventory remains744 reads within the768 total ceiling, with no replacement mechanism.
- `validation/kernel_stage_a/reference.py:18`, `:42`, `:55` and `:75` separate the standard-library Decimal context, endpoint integrals, pivoted solve and canonical ridge factors from production arithmetic. Exact float conversion, deterministic magnitude ordering and independent event/advance formulas are appropriate foundations.
- `validation/kernel_stage_a/authority.py:94` blocks null authority before backend work and binds source/runtime/helpers, setup inventory, release, original deadline and output/resource conditions. The prospective seal explicitly leaves execution fields null rather than manufacturing evidence.
- `validation/kernel_stage_a/production.py:115` transports U rates/time metadata and preserves the original parent through `authority.unit_metadata`; it reuses dimensionless factors rather than refactorizing. `reader_worker.py:9` imports the accepted isolation path and monitoring helper, not the event/reference orchestration module. Its request schema excludes raw histories and labels.
- `validation/kernel_stage_a/driver.py:26` preserves a complete stopped/nonapplicable inventory and retains source/end-to-end failures. `reader_worker.py:20` counts actual calls and flushes trace entries. These are useful mechanisms, but the gaps below prevent trusting the complete gate/resource result yet.
- The final supplied log records20 passed in1.00s, with explicit exit0 in the checks record. Earlier RED evidence and the obscured early wrapper exit-status limitation are disclosed. Those tests provide meaningful component evidence but do not cover the failing paths identified here.

## Important findings

### F1 — An unused mass-sign threshold defeats the decisive floor short circuit

**Locations:** `validation/kernel_stage_a/reference.py:118` and `:241`.

`decode` records `margins['nonnegative_mass']=mass` whenever the normalizers contain any nonzero value, before evaluating the mass floor. `validate_pair` then applies the uncertainty-radius test to every recorded margin, including this sign margin after a decisive floor failure. A positive mass far below1e-60 consequently becomes an unresolved threshold even when it is unambiguously below1e-8 at both precisions.

This is directly relevant to the complete-decay fixture: direct Decimal event kernels need not underflow when their FP64 counterparts do. A tiny positive direct-event mass must not turn its decisive floor failure into a whole-stage uncertainty through an unused sign test. This is a source-derived consequence, not a claimed execution of row04.

**Remedy:** implement the adopted eligibility decision order and applicability explicitly. For a decisive floor rejection, retain the actual mass/category but do not require stability of an additional unused sign or cancellation threshold. Keep both80/160 decisions and every applicable finite comparison. Do not change the radius, tolerances, fixture endpoints, magnitudes or fallback policy.

Specifically, do not collapse the existing negative-mass code4 into floor code5, skip any P/A/B failure-code comparison, or accept an80/160 code disagreement. Deferral applies only after the floor failure is decisive and the retained failure decisions agree; it is not a blanket waiver for sign ambiguity. Root has confirmed that unused sign/cancellation margins must not defeat a decisive floor failure. If the proposed fix instead changes failure-category semantics or the treatment of a genuinely required sign decision, obtain that additional policy clarification before implementing it.

**Focused verification:** a one-channel synthetic Decimal result with a positive mass much smaller than1e-60 must retain a stable floor rejection without raising threshold uncertainty. Separately retain the existing true near-floor/near-cancellation ambiguity checks. No scientific fixture is needed.

### F2 — Worker authority verification creates subprocesses rejected by its own resource policy

**Locations:** `validation/kernel_stage_a/__main__.py:16`; `authority.py:35`, `:105`, `:108`; `monitor.py:22` and `:157`.

The launched stage worker calls full `authority.verify` again. That invokes `git rev-parse` through `observe` and `git status` directly, before the worker records its baseline. The monitor's closed classifier admits only the expected Python workers and exact declared ps observers. A sampled Git subprocess is therefore retained as an unaccounted descendant and prevents completion. This is a conflict in the actual launch path, not merely uncertainty about native ps formatting.

In addition, unknown identities are currently allowed to remain through the run and are rejected only at finalization. A known foreign executable is already a failed common resource/identity prerequisite; it should not silently coexist with continued scientific work while awaiting the final status.

**Remedy:** establish an explicit reviewed phase boundary that eliminates these authority subprocesses from the monitored scientific worker, or separately accounts the legitimate authority phase without exempting its cost. Preserve exact clean-source/HEAD/package checks and revalidation before backend work. Do not broaden the ps exception into a Git/basename/non-Python allowlist. Distinguish a known expected Python worker awaiting its baseline from a definitively unknown executable/parent, and stop promptly on the latter.

**Focused verification:** drive the real launch/verification control path with controlled process observations and no production backend. Prove that legitimate authority work produces no unexplained descendant and that an unknown executable/parent still stops the stage, even if it emits a baseline.

### F3 — Final resource reconciliation can undercount observed peaks and persist a stale success

**Locations:** `validation/kernel_stage_a/monitor.py:120`, `:127`, `:145`, `:162`.

Incremental RSS is updated only while iterating a currently sampled PID whose baseline is already available. If a baseline is consumed after that worker's last sample or exit, finalization merely fills `baseline_bytes`; it never recomputes the increment from the already retained absolute peak. The same finalization gap applies when an observer declaration is first consumed by the final `read_events`: its full already-observed RSS is labeled as an observer but is not added to the recorded overhead peak or rechecked against the cap. These are omissions of sampled evidence, distinct from the disclosed inability to observe between-sample spikes.

The persisted result has another finalization inconsistency: `monitor.json` is written before checking whether that report itself exceeds the output cap. The returned object can subsequently become STOPPED while the durable file still says COMPLETED.

**Remedy:** use one reconciliation step after every event ingestion and at finalization. Reconcile all retained observations with resolved identities/baselines, charge all declared observer RSS at baseline zero, re-evaluate the cap, and retain unresolved identities as failure. Finalize the resource verdict before persisting it; reserve/account the final report and ensure the durable and returned statuses agree without an unbounded rewrite loop.

**Focused verification:** controlled cases where a worker baseline and an observer declaration arrive only during finalization, with already-sampled peaks that exceed the cap when correctly charged; also a final-report output-cap case asserting the returned and on-disk statuses match. No native numerical allocation is necessary.

### F4 — Missing required finite evidence can silently compare as PASS

**Locations:** `validation/kernel_stage_a/reference.py:153`, `:168`, `:173`.

`compare` skips missing/None scalar fields and traverses coefficient, window-vector and window lists with `zip` without validating their outer lengths. An eligible code0 production result with empty coefficient/window records can therefore compare as PASS against a complete reference with the same final prediction. This does not fulfill the requirement to retain and compare all applicable finite fields even when eligibility agrees.

Some missing records are legitimately unreached, such as the empty-snapshot fast path or a window after an earlier failed contrast guard. They require explicit applicability, rather than making every missing record acceptable.

**Remedy:** define and validate reached/applicable fields and window counts for each scope. Require matching presence, shapes and values for eligible/reached evidence; permit absent evidence only for explicitly justified unreached paths. Incomplete trace/reference evidence must remain failed or unresolved, never an arithmetic PASS. Keep the intended unavailable per-window prediction handling and final fallback comparison.

**Focused verification:** eligible records with a missing coefficient block, missing window, truncated vector, or missing finite result must fail closed; the explicitly unreached empty/fallback/second-window paths must retain their intended status.

### F5 — An unbounded observer call can disable the outer timeout

**Locations:** `validation/kernel_stage_a/monitor.py:38` and `:44`.

The monitor synchronously waits for native ps using `probe.communicate()` with no timeout. The outer and candidate deadline checks run in the same thread. If ps stalls, the supervisor cannot enforce either deadline or stop the scientific process group. Its own ps child is also outside the fresh scientific process group, so killing only that group does not clean up the observer.

**Remedy:** bound every native observer invocation by the remaining applicable deadline, or use nonblocking observation under the same deadline controller. On observer timeout/failure, terminate and reap that exact observer and the owned scientific group, retaining a resource/common failure. Do not extend the original600s/90s budgets or introduce a memory/identity exemption.

**Focused verification:** a controlled hung-observer process must lead to bounded termination/reaping of both the observer and worker group. This needs no native ps or scientific execution.

### F6 — Candidate Gram arithmetic failure is incorrectly escalated to a common failure

**Locations:** `validation/kernel_stage_a/production.py:138`; `driver.py:36`.

After successful reference construction/precision checks, a production-versus-reference Gram mismatch raises `CommonFailure`. The driver therefore stops the entire stage. That mismatch is a candidate production-arithmetic gate failure; the adopted policy stops that candidate and preserves the remaining candidates while common/reference prerequisites remain valid. A reference engine or precision failure is correctly a whole-stage stop, but a comparison failure is a different outcome.

**Remedy:** retain the actual Gram comparison evidence and route this failure through the candidate-arithmetic failure path, leaving its production slots unexecuted and the overall result failed. Preserve whole-stage stopping for reference/precision/identity/resource failures. Do not substitute factors or rerun the failed comparison.

**Focused verification:** controlled failed candidate Gram evidence should leave that candidate unexecuted and permit the next fixed candidate; a controlled reference failure must still stop all candidates.

## Review checks and verification limits

- All external helper and test source was assessed through the supplied diff, with relevant authority/schema/log records. No changed file was separately reread in full. File/line anchors were located in the diff.
- The sole focused outside-diff API check addressed concrete integration risks: inspected `famjet/eval/state_io.py:144` to confirm `_decode` accepts the optional expected hash, and `famjet/eval/isolation.py:312` / `:321` to check the actual worker request, source/model identity checks, installed I/O guard and result-return contract. The code does use those existing APIs as declared; no API mismatch is alleged.
- No tests or scientific calculations were rerun. Each finding follows from the implementation's control/data flow; the proposed tiny controls identify the missing regression coverage without requiring the32-row campaign. Root's69-file/hash/package/runtime verification is acknowledged as supplied evidence, not repeated here.
- Actual rate records, six static exports, final setup/source seals, native ps parser/lifecycle behavior, clean-worker integration on the actual fixtures, independent80/160 scientific results and measured resource feasibility remain pending. Their deliberate nulls are not source defects. A read-only native ps availability observation does not certify parsing, descendant classification or the scientific lifecycle.
- The accepted production package and prior design/amendment/source decisions remain unchanged. Fixes should stay in the authorized external helper/tests/records scope; any changed phase authority needs a concrete root ruling. No Stage A, panel, fit, corpus, training or protected release follows from this review.
