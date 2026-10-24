# Conditional-history inference for end-to-end delivery

24 October 2026; updated to root's 12-stratum decision. Prospective protocol: no simulation, import, test, protected access, or source/Git mutation executed. The methodological amendment and accepted implementation must adopt these semantics before execution. References: original Tasks19–22, `famjet/analysis/statistics.py`, statistical protocol, Task19 failure/handoff records, and prior UNADOPTED fixed-reader design.

## Estimand and allocation

Condition on C: actual completed Jet/Bank fits, training statistics/draws/seeds, development selection, writer/rate/budget choices, preprocessing, numerical/fallback policies, and executable artifacts. For paired history loss d_gh=L_Bank−L_Jet:

`Delta(C)=sum_g w_g E[d_gh | C]`; `D=sum_g w_g mean_h(d_gh)`.

Each history's loss averages mean and contrast tasks equally, retaining every query's v2 normalized loss and fallback. Histories are independent within and across synthetic strata; within-history queries are never independent sample units. This target excludes uncertainty from retraining, development selection, and training-statistic estimation. Convex fitting does not remove those uncertainties unconditionally. Repeated frozen fits are not training replicates. Old crossed S4/S16 failures remain FAILED.

Use one selected Jet/Bank pair and byte budget. Primary population: lengths128/512/2048 × regimes piecewise_stationary/trend_reset/periodic_impulses/irregular_revisions, in that length-major order, with all12 weights1/12. Recommend fixed H1536,128/cell. Reserve a fresh H1536 same-fit replication panel, execute regardless of confirmation direction, and report separately. A replicated positive conclusion requires both lower endpoints>0. No selective pooling. Other configurations/budgets are descriptive; secondary inference family is empty.

Nuisance H192,16/cell, estimates paired variability, fallback/tails and actual evaluation cost before freeze. Never choose sample size from favorable mean advantage. H768 is not selected or qualified here: introducing64/cell would require its own prospective allocation/calibration before confirmation. Thus this protocol has no hidden search over H768/H1536.

## Exact analysis

Implement a distinct `conditional_history_welch_v1` manifest/engine; do not reuse crossed `evaluate_gate` or fabricate replicate columns.

`s_g²=sum_h(d_gh−mean_g)²/(H_g−1)`; `a_g=w_g² s_g²/H_g`;
`Vhat=sum_g a_g`; `nu=Vhat²/sum_g[a_g²/(H_g−1)]`.

Interval=`D ± t_(nu,.975)*sqrt(Vhat)`; two-sided p=`2*Pr(t_nu>=abs(D)/sqrt(Vhat))`. This Welch–Satterthwaite approximation has no universal exact-coverage guarantee. A qualified interval excluding zero permits directional rejection; superiority requires its lower endpoint>0. Missing histories, nonfinite/nonrepresentable quantities, or Vhat=0 block inference. Explicit identical-method A/A may return[0,0], never superiority.

Endpoints and p-values use deterministic numerical evaluation: draws=0; endpoint-MC/p-MC=`not_applicable_analytic`, never inherited `met`. Independent numerical-reference checks require endpoint discrepancy<=1e-10×max(1,|reference|); numerical failure is separate from population calibration.

## Fixed calibration fixtures and streams

Freeze N=20,000 independent datasets per eight laws, H_g=128, exact source/fixture hashes and PCG64/version before outcomes. Define independent Z~N(0,1), B~Bernoulli(.02), and T~t_5 across every history/stratum:

1. X=Z.
2. X=(exp(Z)−exp(.5))/sqrt(exp(2)−exp(1)).
3. Negative of law2.
4. X=T*sqrt(3/5).
5. X=(B−.02)/sqrt(.02*.98), rare-fallback stress.
6. Negative of law5.
7. X=Z with heterogeneous scales below.
8. Law2 with heterogeneous scales and signs below.

All X have mean0/variance1. Laws1–6: d=.25X. Laws7–8: d=.25a_gX, with a=(.5,1,1.5,2)/sqrt(1.875), repeated for each length. Law8 additionally uses signs(+1,−1,+1,−1), repeated for each length. All have true D=0 and Var(D)=.25²/H. Evaluate shifts0,+.05,−.05 on each dataset through the production interval; deviations may be reused after verifying translation equivariance. Delta=.05 is a **fixture-specific sensitivity target**, not a user-utility threshold or observed Jet effect. Stress fixtures may fail and must remain included.

Public RNG roles/root seeds:

| Role | Root | Namespace |
|---|---:|---|
| Calibration attempt1 |2026102401901|e2e-inference-calibration-v1|
| Nuisance |2026102401902|e2e-inference-nuisance-v1|
| Calibration revision |2026102401903|e2e-inference-calibration-v2|
| Confirmation |2026102401904|e2e-inference-confirmation-v1|
| Replication |2026102401905|e2e-inference-replication-v1|

Calibration counter seed is `derive_seed(root,namespace,canonical_hash({'fixture':f,'outer':r,'stratum':g,'draw':'history_effect'}))`, f=1..8,r=0..19999,g=0..11. Draw H_g independent variates in history-index order. Scientific generator/query seeds use their frozen production derivation under the separate listed root/namespace, with complete history/query IDs committed before execution. No bootstrap stream exists.

## Acceptance, controls, and cost

K=32 required rates: coverage at zero, null rejection, positive directional power, negative directional power for each law. Shifted coverage equals null coverage by translation; verify and retain that check. Invalid calculations count as noncoverage, potential false rejection, and nondetection. Require simultaneous Clopper–Pearson lower coverage>=.94, upper null rejection<=.06, and both lower powers>=.75. Tail error=.005/(2K); freeze exact integer pass boundaries before outcomes. Overlap with a threshold is unresolved and does not qualify. These are disclosed approximate simulation tolerances, not established exact95%/.05 guarantees.

Controls before scientific calibration: independent hand-calculated mean/variance/df; identical-method A/A; sign reversal swaps/negates endpoints; duplicated queries preserve H and intervals; collapsed query-as-history input is rejected; missing paired histories/changed weights are rejected; deliberately corrupted endpoint/seed/fixture commitments fail validation. Controls do not count as qualifying Monte Carlo trials. Retain rate counts, per-dataset D/V/nu/endpoints/status, RNG identities and all failures.

First attempt:245,760,000 scalar history variates,480,000 interval evaluations, zero nested bootstrap calls. Process<=64 datasets together, never allocate N×H; one worker, aggregate memory<=256MiB, artifacts<=128MiB. These are exact operation/allocation limits, not invented throughput. Freeze wall-time allocation from measured implementation throughput before launch; incomplete runs cannot qualify.

## Freeze, failure, and limits

Fixture success cannot prove the actual unbounded squared-loss distribution lies in a valid domain; H192 cannot certify tails. Document independent applicability evidence and assumptions; implausible applicability blocks strong inference. Before protection freeze all fit/source/dependency/data/selection hashes,12-stratum inventory, weights, both panel allocations, seeds, metrics/fallback/stability, measured resources, calibration evidence, and sealed complete-run release policy.

If necessary, permit one prospective H3072 revision,256/cell, using unchanged laws/N/thresholds, revision seed above, and remaining .005 calibration error budget. It costs491,520,000 history variates and480,000 intervals under unchanged memory/artifact caps; reprice time and freeze both scientific panels before opening either. No fixture deletion, threshold relaxation, extra retries or protected enlargement. A second failure yields a complete scoped inconclusive report and retained evidence, not a false qualifying label. Adding inferential secondaries requires a newly frozen Holm(.05) family and joint all-/partial-null calibration at its thresholds.

For frozen2015–17 nonoverlapping14-day real histories, report finite-period paired losses/native errors, actual counts and failures, for both transfer modes. Approximately52 histories yield26/13 blocks at28/56days; verify actual boundaries/counts. All stations/queries travel together. These block bootstraps are dependence sensitivities, **not primary population confidence intervals** or future-period guarantees. Synthetic conditional qualification does not transfer to real dependence.
