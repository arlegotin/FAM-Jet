# Task 18 kernel Stage A execution-budget source stage — 18 October 2026

**Disposition: source implementation complete; execution HOLD.** This applies the [adopted common 384 MiB conservative sampled incremental execution-charge allowance](../amendments/2026-10-18-kernel-stage-a-execution-memory.md) to kernel Stage A source and a future static setup template. It neither allocates a run nor establishes native or scientific sufficiency. The stopped04 failure, consumed clock and historical 192 MiB seals remain unchanged. Source commit: `9322050`.

At clean base `df22a467bfb3c9ab60bc872e1ee5a5f931b656cb`, [pre-edit evidence](task18-stage-a-execution-budget-source-evidence/preedit.json) captured UTC, monotonic time, Git status, 63 file hashes and original snapshots before RED. `authority.LIMITS.incremental_worker_bytes` is now the literal `402653184`; the parent CLI passes that entry explicitly to `supervise`, so its unchanged generic `201326592` default cannot govern a sealed Stage A launch. The [new static setup template](task18-stage-a-setup-parent-384mib.py) is a byte copy of the reviewed `0ad8232b…` parent except its single `supervise` limit literal. It retains unresolved source/path placeholders and was never imported or executed. The [README](../../validation/kernel_stage_a/README.md) names the charge accurately and separates it from absolute tree RSS and startup memory.

The new [controlled tests](../../tests/test_kernel_stage_a_execution_budget.py) mock process creation and use synthetic sampler/clock boundaries. They check the recorded `286146560`-byte charge against both 192 and 384 MiB, equality at `402653184`, and one byte above; they check exact new seal acceptance, old seal refusal before `supervise`, explicit CLI propagation, template AST equality after the one literal change, and embedded worker SHA. This does not replay stopped04 or probe native memory.

TDD records are retained in [raw evidence](task18-stage-a-execution-budget-source-evidence/). Initial RED attempts `red` through `red4` failed from controlled-fixture mistakes (incomplete seal, owner polling before sampling, synthetic native identity, and a missing `ResidentTree` argument or overstrict kill assertion); all stdout/stderr/exit/timing records are retained. After correcting those tests, `red5` gave **2 intended failures, 4 passes**: old seal acceptance and absent new template. `green` gave **6 passes**. A controller pre-review concern found that the AST test referred to ignored scratch; it now uses the committed, byte-identical pre-edit template snapshot with reviewed SHA asserted. The justified focused rerun `green2` gave **6 passes**.

Exact final focused command (exit `0`, 6 passed, external `0.14584591693710536` s):

```sh
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python3.13 -m pytest -q tests/test_kernel_stage_a_execution_budget.py --basetemp=/private/tmp/task18-budget-green2-vw1i9e6d/pytest
```

Exact additional controlled cover command (exit `0`, 3 passed, external `0.1330172090092674` s):

```sh
/Users/artemlegotin/Documents/git_alter/FAM-Jet/.venv/bin/python3.13 -m pytest -q tests/test_kernel_stage_a_preflight.py::test_authority_refuses_null_unknown_mismatch_before_backend tests/test_kernel_stage_a_preflight.py::test_exact_synthetic_authority_detects_identity_release_and_deadline_mutations tests/test_kernel_stage_a_preflight_fix1.py::test_f2_real_worker_authority_phase_finishes_before_backend_and_refusal_blocks_it --basetemp=/private/tmp/task18-budget-cover-uvisbiew/pytest
```

`postedit-static.json` proves all five runtime/helper/native modules, `requirements.lock` and all `famjet/*.py` bytes equal both pre-edit and accepted `a718a25`; package digest remains `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`. Current monitor SHA is `044b6d0f76e11bc2a2f2d608d35f1e36e3bd85244e31fc063335124a0db5c473`; authority SHA is `89dc449619d8ef0e8b2b4f823c6bbba702b0fbe177c501968533eeb8c8c1bb50`; new template SHA is `a0f89038b48f041e668ab926ab5a7575b3ef9b74cdcada7e8a2b54c292f590b4`. Embedded worker remains exactly 6621 bytes, SHA `f768a8f98577653e81779f080bac27edddd854b173a3c221e3499b5d21ccc1b0`.

Source/JSON/Markdown staged diff whitespace check passes. Whole staged diff check flags trailing spaces in the verbatim pytest failure transcripts; those raw logs are retained byte-for-byte.

Only the listed controlled authority/entry tests ran beyond the focused file. Native controls, subprocess CLI tests, broad unchanged lifecycle suites, backend/model/factor/read work, and actual setup/Stage A were excluded under this source-only brief. Any later allocation requires its own fresh admission, review and release.
