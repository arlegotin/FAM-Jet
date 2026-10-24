# E3 worker integration correction review — 24 October 2026

**SPEC: YES**  
**QUALITY: APPROVED**  
**Fresh-worker lazy-import failure: ADDRESSED**

Reviewed the scoped patch from BASE `0862f5f89b2d784a1eb32a45546eae0134a9f4f3` to HEAD `66f426e8486f4a6d59c35adefb70d1fd221e95ec`, the complete appended worker-fix report, the changed worker/wire-test hunks, and the supplied diagnostic and verification evidence. Earlier accepted E3 corrections remain accepted; unrelated implementation was not reopened.

## Root cause and correction

The supplied `docs/research/e2e-task4-evidence/latest-lru-audit-probe.log` traces `np.unique` through `_unique1d`, NumPy's lazy `__getattr__`, importlib loading and a denied `open`. The RED fresh-worker regression independently identifies the `latest_lru` constructor in the failed request and reports `PermissionError: isolated read forbids disk/network/process access`. These support the stated dependency-initialization cause rather than a missing query result or numerical failure.

At `famjet_poc/worker.py:27–30`, `_prewarm_static_dependencies` invokes `np.unique` on the literal uint64 array `[0, 1, 1]` and checks the fixed expected cardinality. At `worker.py:96–100`, `worker_main` calls it before reading even the request frame prefix. It therefore receives no history, query, label, caller path or request-controlled payload. Numerical thread settings still precede numerical imports.

The strict audit guard at `worker.py:33–38` is unchanged. The patch introduces no allowlisted filesystem path, conditional bypass, guard suspension, retained training data or request-dependent initialization. `_read` continues to install the guard before method reads and to verify snapshot/query and method identity afterward. The change resolves a trusted numerical dependency before entering that existing guarded boundary, as permitted by the brief's trusted-import/source-check initialization phase.

The new test `test_fresh_worker_reads_all_registered_controls_after_strict_guard` uses separate fresh workers for exact, recent, latest LRU, reservoir and shared buckets on a tiny K16/V8 population. It compares predictions with zero tolerance, compares support/failure masks, checks the caller snapshot hash and checks successful journals. The modified guard test warms the dependency, successfully performs `np.unique` after guard installation, and still requires file and socket operations to raise `PermissionError`. Process denial remains unchanged in the inspected guard; this patch does not claim a new process-operation test.

## Findings

Critical: none. Important: none. Minor: none identified in the scoped patch. No information-boundary or I/O-guard relaxation was found.

## Supplied verification and scope limits

The targeted GREEN record reports **2 passed**, exit **0**. The covering `workerfix/wire-covering-final.json/.log` records **15 passed**, pytest **7.99 s**, wrapper **8.282597 s**, exit **0**; all five recorded numerical thread settings equal 1. `workerfix/compile-workerfix.json` records compile exit **0**. These are supplied results, not reviewer reruns. The RED guard-test failure is the expected missing-new-helper import error; the RED fresh-worker test is the reproduction of the actual guarded-read failure.

The supplied source identity is E3 `bbd4772c341de2b1b25d63dae195b3a2a3f2456dbe3f79af76ed31726dada39e`; E1 remains `f78761891876540011e577293e31a89c7661ef66adbb522d2cbcd36c331d8475`. Future E4 requests must use the corrected E3 pin. Root separately verifies raw evidence bytes and preservation of the 142 paused E4 WIP files. This review read only the named E4 causal trace and did not modify, stage, clean or otherwise change E4 work.

No tests, Git commands, benchmarks, actual campaigns, protected-data access, source edits or subagents were used in this review. This report is its only authored artifact. Actual readiness under the new source pin, production feasibility, whole-tree memory monitoring and scientific outcomes remain separate Root allocations; the existing lifetime-peak proxy is not evidence of current whole-tree RSS or inference workspace.

**Disposition:** approve the scoped worker source correction. No additional fix round is required for this finding; fresh actual readiness remains unclaimed until Root's separately allocated check.
