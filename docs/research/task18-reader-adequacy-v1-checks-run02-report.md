# Reader adequacy check02 — memory sufficient, learning gate failed

The single bounded diagnostic completed in66.85seconds of observed process invocation time. Numerical checks passed; **all six readers failed the predeclared fixture-learning gate** after4096updates each. Larger development remains blocked. [Independent diagnosis](task18-reader-adequacy-v1-checks-run02-diagnosis.md) identified no label, loss, update or indexing defect; this is a valid failure of the specified finite procedure, not evidence that either memory lacks the fixture information.

The fixture has four histories,16keys, two observation ages and256queries. Exact2×2reconstruction recovered all old/recent values from both retained states within2.23e-16 absolute error. Independent fixture sums, reader forward/analytic gradients, unit reference, timestamp shift, masks and query/state semantics passed. All12generated length/regime cells also passed terminal chunk32 versus streaming state and C/F input comparisons for both families at atol=rtol=1e-12. Their largest absolute discrepancy2.000888e-11 is allowed by relative tolerance; those cells are equivalence checks, not independent generator-wide oracle validation. None of this repairs historical extreme-cancellation failures.

The learning gate required every task/key group's normalized MSE≤1e-4, alongside finite activity and key-selection conditions. The following are training diagnostics, **not a Jet/Bank benchmark or a selected-model comparison**. “Best saved” is descriptive; it was not substituted for the endpoint or used to qualify a reader.

| Family / reader | Final worst group MSE | Best saved worst group MSE | Gate |
| --- | ---: | ---: | --- |
| Jet C128 | 0.0029689154 | 0.0024089518 | FAIL |
| Jet C558 | 0.0034684432 | 0.00096434707 | FAIL |
| Jet F256 | 1.381755 | 1.3803602 | FAIL |
| Bank C128 | 0.0040924814 | 0.0019384389 | FAIL |
| Bank C558 | 0.00054600193 | 0.00054600193 | FAIL |
| Bank F256 | 1.1814552 | 1.146938 | FAIL |

C reads query-contracted state; F reads the flattened full state. C128 has29448parameters, C558368288, F256368136. All32endpoint groups failed in every arm. Contracted readers learned substantially but fluctuated; full-state readers stayed near unit average normalized loss. Public and cached predictions matched exactly. The answers remain recoverable, so this does not establish an information limit, an optimal-reader result, convergence or a memory-family advantage. Gradient flags were cumulative nonzero booleans; no magnitude/clip-frequency trajectory or full per-parameter activity proof was retained.

The unchanged procedure used fixture-only feature/task scales, frozen production output inverse, seed2026102402, AdamW LR.003, clipping1 and cyclic batches64. Each batch contains one complete history, and every row was exposed1024times. The complete198observations and24576successful/attempted updates are retained. No retry, extra seed, step extension or posthoc threshold relaxation occurred. Child statusFAIL/complete and actual return1 report the scientific gate failure; no timeout or resource stop occurred.

Fresh admitted free-plus-speculative RAM was6.159GiB. Across1796samples, maximum additional processRSS was382.11MiB, absolute sampledRSS594.98MiB; process-lifetime highwater was598.75MiB, a separate measurement. These stay below the1GiB incremental cap. Raw records plus executed wrapper occupy782601bytes. CPU ran with one thread; no cache purge, unrelated-job termination or hardware change was used. These are diagnostic costs, not deployment latency.

[Raw evidence](task18-reader-adequacy-v1-checks-run02-evidence/index.json), [scalar summary](task18-reader-adequacy-v1-checks-run02-summary.json) and [Root custody proof](task18-reader-adequacy-v1-checks-run02-root-proof.json) identify execution source `c60f37a2fb5543da151133965773d11b58786557` and all originals. The separate [run01](task18-reader-adequacy-v1-checks-run01-report.md) remains its pre-admission sandbox permission failure; host permission corrected that boundary without changing code or caps.

The proposed next step is one no-update JetF256gradient audit to inspect history-batch conflict and relative memory/query gradients. It is not released by this report. Production original768fitting remains blocked pending ordered row binding; protected and larger development remain closed. The latest completed fixed-reader development evidence still favors the ordinary exponential bank; the overall research decision remains open.
