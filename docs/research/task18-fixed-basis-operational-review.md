# Task18 fixed-basis operational evidence and learning-config review

Reviewed BASE `e7565155c07638ff0367e9a12062c5c69be95ad5` → HEAD `2def54622c5d9a49c84145739792a084494fbbe9`, against the fixed-basis procedure and root-approved bounded learning allocation. This review covers new records, external procedures, artifact mappings and learning configurations. It does not reopen the accepted production-source review or grant whole-Task18 scientific acceptance.

**Spec compliance: APPROVED for the operational gate and exactly one fresh matched three-family STOP8192 allocation.**

**Artifact/config quality: APPROVED. No blocking or nonblocking defect found in the reviewed delta.**

## Evidence and identity

Read/parsed the review package once, using structured views for large JSON records. Independently checked all 32 current closure promotion entries against both original and promoted bytes, all 176 embedded numerical/preparation JSON records against original bytes and parsed content, all four archived manifest summaries against their original manifest SHA and content, and all 169 operational inventory mappings: no mismatch. These current counts are distinct from the promoter's historical 209-record verification boundary, after which three record-assembly helpers were added and separately verified. No cache-file sweep was repeated. The retained promotion verification records the earlier complete raw/feature file guards and actual policy applicability checks (65.085 s).

References: `docs/research/task18-fixed-basis-closure.json:1`, `docs/research/task18-fixed-basis-promotion-verification.json:1`, `docs/research/task18-fixed-basis-operational-summary.json:1`.

All three cold profiles record clean original Git source `e756515…`, package `ad542def…`, actual stop 2, potential horizon 32768 and no resume. The promoted calibration canonical hash independently recomputes to `98ef5c99fee4034d02e6fb5fb98b37aedb4d8e1b2ac10bc90649ecbe198ddf41`. Each new learning config differs from its actual measured calibration config only in mode and calibration path/hash. Raw corpus, family feature manifest, model, data seed, resource, optimizer and fit settings remain bound to the measured configuration.

References: `docs/research/task18-cpu-calibration-fixed-basis.json:1`; `configs/development/jet_fixed_cpu64_raw128_32768.yaml:92` and corresponding Bank/multiscale development sections.

## Numerical and saved-checkpoint applicability

Verified all 72 fitted records: three families × saved steps 0/2 × all 12 declared length/regime fixtures. Every summary/procedure points to the actual saved checkpoint SHA, original fixture summary SHA and candidate SHA, correct helper/common-helper SHA, identical history/raw hashes, common 768-fit target hash, and saved gradient artifact SHA. Every case records exact candidate/reference terminal replay. All active comparison metrics retain `atol = rtol = 1e-12` and pass; the inactive support-head gradients are explicitly classified rather than presented as measured active gradients. Worst pointwise ratios are Jet 0.000940768, Bank 0.000727751, multiscale 0.100467567.

The executed r2 fitted helper composes the accepted initial memory/reference evidence through unchanged fixed kernel, represented input, terminal and raw-feature identities. It checks saved fitted task predictions/loss and key/value/gate/common-reader gradients. It does not claim a new independent MLP/query-input implementation, a repeated stream/Decimal campaign, or fixed-rate logit gradients. Prepared but unused older helpers are not treated as executed gates.

References: `docs/research/task18-procedures/task18_fixed_basis_fitted_r2.py:26`, `:37`, `:49`, `:55`; `docs/research/task18-fixed-basis-operational-report.md:13`.

Independently decoded the six saved checkpoint envelopes without allocating models. They contain FP64 model parameters/buffers; step-2 AdamW moments are FP64 and six step counters are FP32 (24 B). Step 0 has no moments and sampler position 0; step 2 has sampler position 6 and no partial accumulation. Fixed kernel hashes remain constant across both steps/all fixtures. Model tensor totals are 243896/243928/243960 B: common 241736 B parameters plus 2160/2192/2224 B buffers. Each moment array totals 240704 B; inactive support parameters correctly have no AdamW state.

## Fairness, storage and cost

All three feature-manifest entry sequences match the raw manifest's complete 6144 ordered episode IDs, lengths and content hashes, with each feature entry bound to its raw SHA. Common fit provenance has 768 histories, 6144 feature rows, identical fit-history identity, target hash `0cebf5…`, and `t_ref = 1`. All three final cold evaluations have the identical 96 development histories/768 queries, with no fallback rows. The separate metadata transport does not enter the 97-wide reader features: an inspected irregular-revision cache record retains distinct feature/query/label/metadata fields, FP64 `[1,8,97]` values, and no raw-history feature payload. This agrees with the already accepted feature-delivery boundary; presence of provenance metadata is disclosed, not concealed.

Actual state is 9345 B for each family. Reader accounting records 30217 allocated parameters, 29448 objective-active **upper bound**, and 29952 MAC/query. Complete fitted-preparer ownership row sums independently reproduce 287111/287194/287605 B, including Python objects, distinct tensor storage and external configuration; the multiscale tuple taus are present, and no retained NumPy arrays are reported. Serialized configuration/export sizes and tensor ledgers remain separate from measured process RSS. These are explicit accounting boundaries, not an assertion that Python object totals equal RSS.

References: `docs/research/task18-fixed-basis-cache-identities.json:1`, `docs/research/task18-procedures/task18_fixed_basis_numeric.py:48`, `docs/research/task18-fixed-basis-operational-report.md:11`.

Cold additional peaks 168624128/169377792/167952384 B are all below the unchanged 201326592 B cap. Cached updates report zero encoded events but 2688 source events per update; full external feature preparation remains separately charged, including multiscale 10997098 FP64 exponentials and 703814272 cubic-work units. Repeated preparer/cold fitting is retained rather than silently amortized away.

The failed first preparation remains recorded at 166.389217 s with 97310428 B partial output. The 11.406564 s audit measured all 6144 serialized sizes and checked the 6105 retained real files' lengths and original file hashes; dummy feature values were used only for size measurement. Complete caches each total 97940032 B; the revised prospective bound is 24700 × 6144 = 151756800 B. Independently recomputed setup sum is 1975.0897380409297 s = shared raw + failed phase + sizing audit + successful driver. Nested fit/profile/fitted costs are not added twice. Earlier source/tests/numerical/probe costs remain explicitly additional. UTC/perf divergence and sleep evidence are retained without a thermal or comparative speed claim; verbatim pmset whitespace is not a defect.

References: `docs/research/task18-procedures/task18_fixed_basis_size_audit.py:8`, `docs/research/task18-procedures/task18_fixed_basis_close.py:19`, `docs/research/task18-fixed-basis-operational-report.md:15`, `:17`, `:19`.

## Exact next-run boundary

Approval covers fresh Jet4, Bank8 and logHiPPO4×2 runs under the new full Git identity, explicitly stopped at 8192; observations 0/128/512/1024/2048/4096/8192; all 12 endpoint fitted checks per family at the original tolerance; and one frozen 6144-record empirical TRAIN-risk pass per family through the declared feature/reader/loss path. No profile checkpoint resume, refit inside risk evaluation, omitted failures, extra interim experiment or automatic extension is authorized. The YAML horizon and later milestone entries remain 32768 potential configuration; execution must supply the approved 8192 stop. This distinction is explicit in the binding procedure and proposal, not an accidental authorization to run the full horizon.

References: `docs/research/task18-fixed-basis-procedure.md:55` and its final dated root ruling; `docs/research/task18-fixed-basis-learning-proposal.md:3`, `:5`, `:9`, `:17`; `configs/development/jet_fixed_cpu64_raw128_32768.yaml:58` and `:101`.

This is a separate fixed-basis family arm, with no freezing-only causal attribution, basis-win claim, convergence claim or protected-result claim. Broad baselines, learning-curve/convergence acceptance and whole Task18 remain OPEN. No models, numerical campaigns, test suites or full cache scans were rerun for this review; production source and Git state were not modified.
