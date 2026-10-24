# Actual selected-Jet Laguerre failure: quantitative diagnosis

2026-10-25. Diagnosis only; no production source, test, fit, selection, tolerance, lock, configuration, or protected data changed. The original strict failure remains a failure.

The actual failure is cancellation when recovering a very small first moment as `(L0-L1)/2`, followed by amplification in the reader's `H/(mass+epsilon)` feature. It is not a state-parity or support-parity failure in the inspected history. Independent 70-digit Decimal direct sums agree closely with the canonical Jet result and identify the recovered Laguerre moment as the source of the prediction discrepancy. This is a measured coordinate-conditioning issue; the evidence does **not** establish that the fitted normal matrix is poorly conditioned.

## Scope, provenance, and execution

Applied the systematic-debugging workflow: traced the original traceback and deterministic selection, reproduced the unchanged comparator, compared passing neighboring histories, then tested the cancellation explanation against independent direct sums. No fix was attempted.

Original full invocation session 67155 ended exit 1 after 1728.763838625 seconds, according to the parent execution witness. Its 36 main candidates and four prefix fits completed, and exact/recent/latest/reservoir/buckets controls completed. Failure occurred before protected freeze/data generation or Beijing test access. This diagnosis does not reclassify that run as complete or successful. Original logs and study files were not overwritten.

The diagnostic used existing `.venv` CPython 3.13.5, the installed locked NumPy/Torch libraries, CPU FP64, and OMP/MKL/OPENBLAS/VECLIB thread variables all set to 1 before imports. One cold scientific process ran for **1.1086095 seconds including startup**, exit 0 (diagnosis succeeded while preserving the caught comparator failure), peak child RSS **239,517,696 bytes**. The initial evidence output was **677,469 bytes**, below the 300-second / 1.5-GiB / 32-MiB budget. Subsequent work inspected saved evidence with stdlib only; no further model evaluation, generation, fitting, or scientific-library process ran. NumPy `longdouble` has only **53 mantissa bits** here, so it was not used as a higher-precision reference.

The exact scientific argv, environment, original monotonic and epoch start/end clocks, exit, budget, raw-log bytes and SHA-256, and artifact byte commitments are in [invocation.json](e2e-laguerre-actual-diagnostic-evidence/invocation.json). [diagnostic.log](e2e-laguerre-actual-diagnostic-evidence/diagnostic.log) retains the original `ArithmeticError` traceback. [result.json](e2e-laguerre-actual-diagnostic-evidence/result.json) contains all quantitative results and input byte hashes; [first-failure-arrays.npz](e2e-laguerre-actual-diagnostic-evidence/first-failure-arrays.npz) contains original/recovered states, L0/L1, raw/design features, predictions, and unchanged coefficients. [summary.log](e2e-laguerre-actual-diagnostic-evidence/summary.log) records the affected channels and verifies all original invocation file hashes. The stdlib-only analysis invocation is recorded separately.

## Actual selected model and first failure

Selection was recomputed with the existing `select_candidate` rule from the actual candidate ledger, then checked against both `selected.jet` and `controls.laguerre.equivalent_to`:

- Configuration: `78d5f023a56f7eb040976507012ae80a9edbed16bfeeb8da26a43a6321c467f0`; Jet K16/V8, query width 16, ridge `1e-6`, alpha_min `1/5224`, alpha_max `0.5`, epsilon `1e-6`, support floor `1e-12`.
- Selected manifest SHA-256: `8d65aa42d217e957950eae2becfa5e326d88f9e692815f3fff37337ad8ba1d2b`; measured development loss `0.17049114230344803`.
- Coefficient norms: L1 `1998.8181297425722`, L2 `184.0757395521545`, maximum absolute `44.98291581336909`. Minimum feature/query scales `0.10962812793976216` / `0.5`. Persisted scaled normal residual `2.5936514995722857e-14`.
- The normal matrix/eigenvalues were not persisted. Its condition number is unavailable; no training rescan or refit was made to manufacture one. The small solve residual alone is not a condition-number estimate.

Public history order came from the actual development manifest and hash-verified cache. The first three histories passed. The first failure is sequence index **3**, `development_fit-128-irregular_revisions-000`, 128 events. The predeclared immediate following history, `development_fit-512-piecewise_stationary-000`, passed. Evaluation then stopped: **five histories total**, not another 192-history scan.

| First failing history quantity | Maximum absolute difference | Maximum original tolerance ratio |
|---|---:|---:|
| Z | 0 | 0 |
| H | 7.66053886991358e-15 | 0.005143230225140821 |
| Raw reader features | 7.597617012243729e-11 | 75.9761282002824 |
| Standardized interaction design | 2.3588117570305656e-11 | 23.388971820452824 |
| Predictions | 9.070078021977679e-12 | 3.838424320571808 |

Tolerance ratios are `abs(left-right)/(1e-12 + 1e-12*abs(right))`, matching the unchanged comparator orientation. Nine prediction scalars fail. Finite masks, support, failure, `prediction_valid`, and `numeric_supported` are all exactly equal. Every inspected state's Z/H passes the original state tolerance; it is the prediction predicate that raises.

First failing and worst-ratio scalar: query **1**, key **3**, value coordinate **3**, contrast, T=292, age interval `[23.332722204852427,156.7830822107067]`. Direct prediction `-0.17292306254769851`, Laguerre `-0.1729230625522007`, delta `4.502176409459935e-12`, tolerance ratio `3.838424320571808`.

Maximum absolute prediction delta: query **4**, same key/value, mean, T=292, interval `[69.36654426549846,75.32640007132626]`. Direct `1.576239032893465`, Laguerre `1.576239032884395`, delta `9.070078021977679e-12`, ratio `3.5206663303376344`.

## Independent reference and error propagation

For those two affected reads, 70-digit Decimal independently summed the eight contributing observed events for the queried key, at terminal/query time, using the exact binary64 event values, rates, keys, gates, and timestamps. For each rate it computes `sum(exp(-rate*age)*impulse)` and `sum(rate*age*exp(-rate*age)*impulse)`, without calling either recurrence. It then computes features, standardization and the fixed fitted readout in Decimal. Both the original rounded query basis and an independently calculated Decimal query basis are reported. Reference state comparisons in the table-like JSON metrics round the Decimal state once to FP64; full Decimal numbers and exact Decimal affected-channel errors are retained separately.

At highest-rate anchor index 3, key 3, value 3:

- True H from Decimal: `5.5170486700394902769253006560e-13`.
- Canonical H: `5.517048670039495e-13`; absolute reference error **4.7732160424e-28**.
- L0=`1.2169475990662066`, L1=`1.216947599065103`; recovered H=`5.517808432387028e-13`; absolute reference error **7.5976234754e-17**. Recovering a roughly 5.5e-13 moment from order-one coordinates loses relative accuracy through cancellation.
- Mass H is only `4.1038882806102800654951e-13`; recovered mass error `6.0624142892e-17`. The fixed epsilon `1e-6` dominates the ratio denominator.
- Raw feature index 16 changes from `5.517046405905285e-7` to `5.51780616760651e-7`: **7.5976170122e-11** difference. Dividing the small absolute moment error by approximately `1e-6` explains this amplification.

The largest canonical and recovered keyed-state errors against Decimal are both only `1.2434497875801753e-14` (on other channels). Those global state maxima therefore conceal the relative loss in this tiny H channel. The recurrence algebra is correct (`L1=Z-2H` with old-state L0 in its update); measured reference discrepancies identify finite-precision recovery, not a missing write, key, rate, or support transition in this case.

| Read | Canonical error to Decimal prediction | Laguerre error to Decimal prediction | `sum(abs(beta * delta_phi))` |
|---|---:|---:|---:|
| Query 1/value 3 | +4.6716774e-15 | -4.4975047e-12 | 2.0180059e-10 |
| Query 4/value 3 | +1.4500509e-14 | -9.0555775e-12 | 3.6197520e-10 |

The exact Decimal dot of the saved binary64 design perturbation with the fitted coefficients is `4.5003563061e-12` / `9.0587168147e-12`, respectively. Measured separate dot-rounding residuals account for the remaining `1.8201033427e-15` / `1.1361207306e-14` of the observed differences. Adding the absolute residuals to the displayed bounds gives `2.0180982226e-10` / `3.6198801207e-10`, covering the observed deltas without choosing a new tolerance. These are observed-case perturbation bounds, **not** universal recurrence bounds or an amended acceptance predicate.

For the same two scalars, prediction deltas divided by training task scale are `1.6889823548e-12` / `1.4450331938e-12`. The induced normalized scalar squared-loss differences are bounded by `3.4067287166e-13` / `1.3766461224e-13`, using `abs(delta)*(abs(left-target)+abs(right-target))/scale^2`. These are tiny at the measured task scale, but do not establish a full-panel score bound or excuse the original strict failure.

## Minimum honest completion route and artifact implications

**Recommended route:** after a dated root methodology amendment and review, retain original strict Laguerre parity as an explicit diagnostic that can report failure without blocking the independent primary Jet/Bank comparison. Keep selected fits, data, primary state precision, reader, selection rule and original tolerance unchanged. Continue to treat support/failure/nonfinite discrepancies as substantive failures. Expose finite coordinate disagreements and their state/readout sensitivity; do not convert this observed-case bound into a blanket pass. The eventual report must say the original equivalent-coordinate prediction criterion failed, and must not claim successful FP64 Laguerre equivalence. Only the inspected case is explained here; later public/real histories still need their own diagnostics under the amended contract. This preserves the scientific primary comparison while removing an unsupported implication that an invertible coordinate transform is necessarily well-conditioned at every recovered small moment.

If successful strict independent-coordinate equivalence is indispensable, the alternative is a separately reviewed compensated or higher-precision **diagnostic** Laguerre recurrence/recovery, followed by bounded public validation. Primary Jet/Bank fits can remain unchanged, but that control changes its numeric representation/cost and cannot be described as the original FP64 control or assumed to pass before measurement. No such implementation or validation is included here.

Current E1 model source identity is `f78761891876540011e577293e31a89c7661ef66adbb522d2cbcd36c331d8475`; E3 identity is `bbd4772c341de2b1b25d63dae195b3a2a3f2456dbe3f79af76ed31726dada39e`. The selected model loads under unchanged E1 identity, and all inspected input byte hashes were rechecked after execution. A production comparator/study edit would change E3/full executable identity; existing E3 cache/source and resume checks cannot simply be bypassed or the old run marked complete. Reuse of completed public models/rows would require an explicit, reviewed source-transition/lineage mechanism preserving old hashes/files, revalidating every reused artifact, and separating diagnostic/source changes from primary model identity. This report authorizes no migration.

The original development allocation started at epoch **1792878115.614666**, clock kind `continuous_wall_since_first_development_invocation`; it remains unchanged. Elapsed diagnosis/review time does not disappear, and neither this successful diagnostic invocation nor reused public artifacts restart the scientific run or replenish allocations. Any continuation must account for the original clock and obtain a concrete dated resource amendment if its original allowance is exhausted. No protected access, new allocation, resume, migration, or completion claim was performed here.
