# Planning audit — 16 October 2026

This audits the requested documents, not a finished implementation or scientific outcome. It is not an independent literature review, license clearance, hardware benchmark, trained-model evaluation or execution audit.

## Reviews

The Superpowers brainstorming builder check read the spec in a fresh agent context. It raised query-time policy, unspecified secondary labels, and valid absent-key features. Those were resolved in the spec and plan; the final response was **“Nothing important left.”** The author performed the writing-plans self-review; the plan itself received no separate external scientific review.

The plan self-review corrected statistical-code ordering before preregistration/unblinding, defined approximate crossed-bootstrap/Holm calculations and endpoint precision, removed an early dependency on not-yet-implemented training statistics, and clarified executable-source versus manifest commit hashes. A wrong small-N Gaver test draft was corrected to `[2*log(2),-2*log(2)]` using an independent standard-library evaluation of the supplied factorial equation.

## Verification scope

Documentation checks cover local Markdown links, balanced code fences, final newlines/trailing whitespace, 25 consecutively numbered tasks, explicit file/interface/test/verification/commit fields, all 127 unchecked execution steps, WP00–WP10 and R01–R26 coverage, inference-before-pilot-before-freeze ordering, and the supplied-equation Gaver N=2 fixture. These checks inspect documentation and a small equation fixture; they do not run the PoC. Git staged whitespace checks and final branch/status/log checks verify the requested commits and clean handoff.

The documentation inventory is README, spec, implementation plan, supplied source record, local discovery record, PROGRESS, DECISIONS and this audit. Requirements were checked against the source brief: exact old-Z dimensionless recurrence/derivative, equal bytes and full costs, prior-art limits, fixed/learned writer separation, query-independent state and read isolation, exact event-level targets, temporal versus interference stress, missingness/units, baseline fidelity, protected/clustered statistics, failures/resume, conditional extensions and honest negative/inconclusive reporting all have named specification sections and plan tasks.

The final document check passed for eight Markdown files, 19 local links, 25 ordered tasks, 127 unchecked steps, WP00–WP10/R01–R26 coverage, analysis-before-pilot-before-freeze ordering, the supplied-equation Gaver N=2 fixture, and documentation-only scope. Git whitespace checks passed for the staged specification milestone; the plan/handoff milestone receives the same staged check before its commit.

## Remaining limits

All experimental verification is pending, including original-source identity/revision/license checks, a generated dependency lock, numerical/gradient tests, CPU/MPS compatibility, real archive ingestion, baseline positive controls/convergence, pilot precision, protected outcomes and replication. The preliminary local snapshot does not complete WP00. The supplied Linux figures never enter a locally measured result table. No trained-model result or laptop performance claim is supported by these planning documents.

## Task 1 execution addendum — 16 October 2026

The earlier sections describe the historical planning audit. Task 1 now adds actual environment evidence: hash-checked native installs into `.venv` and a clean temporary environment, 13 passing tests, a successful full doctor, clean `pip check`, and 72 CPU / 36 MPS passing ordinary bounded operation/gradient cells. See the [executed gate record](docs/research/2026-10-16-environment-gate.md) and linked JSON artifacts for exact commands, failures, resources and scope.

The initial normalization failure is retained; tolerances were not widened. Tests also caught thermal output that reports errors despite exit zero, battery identifier exposure, unsafe workspace shapes, missing dependency metadata, and CPU RNG seeding that otherwise changed the MPS stream; the corresponding fixes were verified. A first oversized-workspace guard test was interrupted after exposing the missing guard, then changed to block fixture allocation and rerun red/green safely.

This is an implementer self-review, pending controller review. No full native GPU kernel profiling, full-training resource envelope, model throughput, data ingestion, model/baseline correctness, protected analysis or scientific outcome is certified. Source verification is read-only metadata/source inspection, with no source-result reproduction or general license clearance.

## Task 2 execution addendum — 16 October 2026

Implementer self-review checked the Task 2 brief and spec §§3/5/12 against the public contracts. The initial focused red run collected 53 tests and failed all on missing contract modules. Subsequent focused verification passed; a resolved-JSON reload initially failed because YAML interpreted JSON scientific notation as a string, corrected by using the JSON parser for `.json`. An added provenance aliasing test failed before copying input identities and passed afterward. Final complete suite: **70 passed, 1 skipped, 2 subtests passed**. The existing `test_cpu_probe_preserves_existing_mps_rng_stream` skipped because native MPS is not exposed to this sandbox process; no GPU result is claimed by this run.

Coverage includes subprocess seed/hash goldens, unknown and duplicate config fields, phase-aware blocking nulls, nonfinite/rate/time/mask rejection, checked integer subtraction overflow, independently observed channels, full uint64 key IDs, atomic write failure preservation/cleanup, and provenance identity separation/input copying. Existing doctor tests are included. No new dependencies, lock changes, data preparation, recurrence, model behavior, snapshot serialization or protected scientific execution is included. Independent review remains pending.
