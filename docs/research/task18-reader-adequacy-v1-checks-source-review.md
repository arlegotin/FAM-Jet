# Task18 numerical/fixture source review

**SPEC: NO. QUALITY: NEEDS_FIXES. HOLD.**

Reviewed the supplied three-commit diff, BASE `ed47d5cc577e24060686a3fae1ff03bfb2b4059e` to HEAD `3cd19e3caa2094388c37cd95f1668ccaec6dc151`, against the checks-source brief, dated numerical-checks adoption, and referenced design/source fixture requirements. Also inspected the prospective run01 witness. This is a bounded component review, not whole-branch acceptance or a campaign result. Root independently completed custody/preservation verification. No tests, numerical panel, training, or Git operations were run by this reviewer.

## Strengths

- `validation/reader_adequacy_v1/checks.py:39`: independent event-level exponential sums respect observed shared-mask writes; raw C/F ordering, ratio/derivative checks, signed cancellation, absent/padded selectors and all-key two-age reconstruction are substantive checks rather than copies of the propagation implementation.
- `validation/reader_adequacy_v1/checks.py:127` and `:258`: exported-weight explicit SiLU chain checks all three weight gradients and input gradients; physical outputs use the frozen target inverse. The complete unit-transformed reference and actual canonical timestamp shift preserve the canonical-only adapter boundary. Fixture initialization uses isolated RNG state.
- `validation/reader_adequacy_v1/checks.py:457` and `:579`: terminal cells preserve the requested generator namespace/seed/IDs and promotion semantics; the six closed arms use the specified optimizer, cyclic batches, update ceiling and evaluation schedule. Fixture features never become production statistics.
- `validation/reader_adequacy_v1/check_run.py:63`: fresh output, closed CLI, launcher thread checks, separate current/highwater RSS, explicit admission, source/lock/environment identities and atomic ordinary completion paths are appropriate. The witness supplies literal combined-mode arguments, four pre-import thread variables, an original-start external 1200-second wait, and actual return-code/timeout observation. Its expected-HEAD placeholder correctly prevents release before binding.

## Issues

**Critical:** none found.

**Important 1 — Wrong fixture normalization changes the experiment.** `validation/reader_adequacy_v1/checks.py:149`, `:156`, `:170`, `:572`. The adopted amendment explicitly requires fixture-only **per-task population scales**. The code reduces `pooled[task,row,coordinate]` over `(0,1)`, yielding eight coordinate scales shared by both tasks. Both training and all 32 group losses use that vector. The required convention is a coordinate mean within each task and a population scale pooled over that task's rows/coordinates; tasks must retain separate scales. Consequently the present loss weighting and `1e-4` stopping test implement a different finite procedure. Return/index separate task scales consistently in optimization and evaluation; add a small hand-calculated unequal-task-variance test. Keep production inverse buffers unchanged.

**Important 2 — External timeout discards completed evidence.** `validation/reader_adequacy_v1/check_run.py:119`, `:129`, `:138`; `.superpowers/sdd/2026-10-16-famjet/task-18-reader-adequacy-run01-witness.py:45`, `:48`. Progress, completed cells, arms and checkpoint observations exist only in memory until normal return or a caught exception. The external timer starts earlier than the child's internal timer and kills it directly; SIGKILL cannot enter the exception handler. Thus the specifically supported timeout path can leave no child status/result and lose all completed observations. The exit witness accurately records death but cannot recover them. Persist atomic bounded progress/status at meaningful checkpoints and preserve a terminal failed/timeout observation through the controller. Do not extend the allocation or retry to recover evidence.

**Important 3 — Failure inventory and costs are incomplete.** `validation/reader_adequacy_v1/checks.py:557`, `:613`, `:633`. Failed-arm records omit actual optimizer-step count, frozen/first/last counts and static/writer identity fields recorded on normal completion. A failure between evaluations loses the number of completed updates. Arm setup and its admission check occur outside the arm handler; resource abort rethrows with remaining closed arms absent. Initialize the six-arm inventory with explicit unattempted/blocked states, register the active arm before setup, increment the successful-update counter, and retain available identities plus explicit unavailable reasons on every failure. This is necessary to meet failure-complete outcomes and charged-work reporting.

**Minor:** none separately raised.

## Verification boundaries

Named external interface checks were limited to `PrimaryReader`/`ReaderSpec` feature, export and inverse shapes; fixture row ordering; `generate_episode` seed/metadata and `move_episode` promotion; snapshot fields; Jet derivative diagnostics; oracle arithmetic; atomic JSON; and the existing per-task pooled-statistic convention. These reads resolved concrete caller/arithmetic risks. The retained focused suite's 15 passes support only its small cases; none exercises these three failure/normalization requirements adequately.

Cannot verify campaign arithmetic across all cells, convergence of any arm, or actual resource consumption without the separately authorized campaign. After corrections and source re-review, recommend exactly the separately released bounded campaign, not an expensive review-time rerun. No allocation is approved here.
