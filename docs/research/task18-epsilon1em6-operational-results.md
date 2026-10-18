# Epsilon1e−6 operational gates passed; learning remains held

18 October 2026. Both families completed fresh preparation, cold two-update profiles and every fitted numerical check. All seven allocated phases passed on the first attempt. There was no timeout, retry, resource violation or numerical failure. The process has stopped.

This supports a fresh learning experiment with epsilon1e−6. It does not establish accuracy, convergence or an advantage for Jet. The original epsilon1e−8 fitted8192 gate remains **FAILED**. No scientific8192 run or next-stage config/helper has been prepared.

Executed source: `c71547932e2875468752db09e6f0a1e02c3e5650`; package: `57c0920f360e47f2c3978f056437143c4262b8ab9653b753df1321402ade9717`. Both stayed frozen. Seal `53fc2cc2e2af15ad915abd4a0f5db90035760e898d5eae81d66a322e6abe93c1`; timeout wrapper `92b5bcdf395638aa496314b7e8ccbdc1fe9a5b64450cdf5679209a3081508001`, archived before launch. All previous caches and failed evidence remain intact.

## Actual execution and resources

| Phase | Full driver time (s) | Main result |
|---|---:|---|
| shared / raw | 342.622063 | 6,144 histories; all seven prior-cache comparisons passed |
| jet / prepare | 161.441796 | 93.747s fit +66.507s cache;101,085,760 payload bytes |
| jet / cold | 170.013848 | 168.800s internal;139,018,240B net peak; exactly2 updates |
| jet / fitted | 33.667281 | 24 cases passed; worst ratio0.679760;88,113,152B peak |
| bank / prepare | 159.389933 | 93.577s fit +64.624s cache;104,231,488 payload bytes |
| bank / cold | 170.356834 | 169.138s internal;138,854,400B net peak; exactly2 updates |
| bank / fitted | 33.781338 | 24 cases passed; worst ratio0.217247;82,690,048B peak |

Total outer execution was **1,072.038467s**, with **1,072.047092s UTC elapsed**, versus the1,080–1,210s forecast. The1,800s process-group cap was not reached; exit0 and no signals. Driver time was1,071.953126s. Phase, fit and case timers are nested inside these totals and must not be added again. AC100% snapshots were retained; no power override or material clock divergence was observed. The preparer helpers retain an inherited~0.039s summary-assembly offset between their internal timers; outer phase clocks cover the complete boundary.

Each family used exactly two768-history fits: one for feature preparation and one in its cold profile. Cold-fit times were94.217903s Jet and94.859668s Bank. Both reproduced the common target-statistics hash `0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21` and `t_ref=1`. Feature statistics were freshly fitted at epsilon1e−6. There was no third fit for numerical ordering.

The shared raw payload is953,874,048B. All6,144 ordered IDs, lengths, regimes, event/query/oracle hashes, serialized bytes and file hashes match all seven sealed prior complete caches. The new canonical raw manifest hash is `c18c09aa22127efb6ee56851cbde76a5bb0dd1bb1ef6218abfca6128ab62a43f`. Actual fitted feature identities are version2, with epsilon1e−6/support floor1e−8, source, raw manifest, schema, fit and dtype bound. Feature manifest hashes are Jet `1a606013ae4f65f81086d22b53c88f10c4f11be8cede6bc9ef9dd0d959507eab` and Bank `399040693be4795147f7690f0add7a3154a09082c44bfa55fc6524926588e592`.

Both cold profiles included the actual cache integrity scans, common96 exposed development histories, and exactly2 updates under the configured32768-step policy. Saved previous/current checkpoints were verified at steps0/2 before reconstruction. Numeric state, parameters, reader, buffers, gradients and AdamW moments areFP64; optimizer step counters areFP32. Measured optimizer-state bytes were480,152/478,392. State is9,345B per history. Allocated parameters are30,134/30,021, MAC/query29,875/29,768, and post-fit primary-active **upper bounds**29,008/28,800. There is no padding. Support calibration remains untrained/unavailable.

All48 fitted cases passed528 original pointwise checks at `atol=rtol=1e−12`, plus96 explicitly inactive support-parameter entries. Exact checkpoint/config/source identities, fixed kernels and initial1e−6 features composed the accepted memory evidence. The package is byte-identical across the metadata-only9aca→c715 change; original source records remain unchanged. Shared query construction and the production MLP are not independent oracles. Passing steps0/2 does not certify a later trained8192 endpoint.

## Complete fitted-case table

| Family | Step | Cell | Status | Maximum ratio | Net peak B | Internal seconds |
|---|---:|---:|---|---:|---:|---:|
| jet | 0 | 0 | PASS | 0.00229964349 | 71565312 | 0.399513 |
| jet | 0 | 1 | PASS | 0.00467067888 | 78675968 | 0.422532 |
| jet | 0 | 2 | PASS | 0.00246828584 | 82575360 | 0.509942 |
| jet | 0 | 3 | PASS | 0.0319093215 | 71630848 | 0.389943 |
| jet | 0 | 4 | PASS | 0.00732154371 | 74678272 | 0.414283 |
| jet | 0 | 5 | PASS | 0.679760031 | 82640896 | 0.514153 |
| jet | 0 | 6 | PASS | 0.00630666261 | 75988992 | 0.389253 |
| jet | 0 | 7 | PASS | 0.00161722478 | 74727424 | 0.429418 |
| jet | 0 | 8 | PASS | 0.0159572101 | 82575360 | 0.514956 |
| jet | 0 | 9 | PASS | 0.0079182106 | 71696384 | 0.392575 |
| jet | 0 | 10 | PASS | 0.00532181306 | 74760192 | 0.415761 |
| jet | 0 | 11 | PASS | 0.00621886365 | 82788352 | 0.513631 |
| jet | 2 | 0 | PASS | 0.00183802844 | 73416704 | 0.389586 |
| jet | 2 | 1 | PASS | 0.0110843496 | 74891264 | 0.413867 |
| jet | 2 | 2 | PASS | 0.0031857633 | 83755008 | 0.512039 |
| jet | 2 | 3 | PASS | 0.0677928341 | 79462400 | 0.390053 |
| jet | 2 | 4 | PASS | 0.00545415127 | 74825728 | 0.414976 |
| jet | 2 | 5 | PASS | 0.0830780239 | 83558400 | 0.522547 |
| jet | 2 | 6 | PASS | 0.00134943148 | 73334784 | 0.391060 |
| jet | 2 | 7 | PASS | 0.00434971863 | 74743808 | 0.418043 |
| jet | 2 | 8 | PASS | 0.0462339096 | 88113152 | 0.517514 |
| jet | 2 | 9 | PASS | 0.00570330381 | 73154560 | 0.389957 |
| jet | 2 | 10 | PASS | 0.00441424547 | 74825728 | 0.417120 |
| jet | 2 | 11 | PASS | 0.00256190106 | 83836928 | 0.516161 |
| bank | 0 | 0 | PASS | 0.00288799037 | 71499776 | 0.390062 |
| bank | 0 | 1 | PASS | 0.00538189256 | 73138176 | 0.414218 |
| bank | 0 | 2 | PASS | 0.00672189223 | 81575936 | 0.507934 |
| bank | 0 | 3 | PASS | 0.00444704557 | 72613888 | 0.389464 |
| bank | 0 | 4 | PASS | 0.00162771162 | 72941568 | 0.417324 |
| bank | 0 | 5 | PASS | 0.0948969058 | 81805312 | 0.511098 |
| bank | 0 | 6 | PASS | 0.00306359509 | 71434240 | 0.409239 |
| bank | 0 | 7 | PASS | 0.00109904288 | 77348864 | 0.422070 |
| bank | 0 | 8 | PASS | 0.0019068462 | 81641472 | 0.519835 |
| bank | 0 | 9 | PASS | 0.0038155331 | 71483392 | 0.389023 |
| bank | 0 | 10 | PASS | 0.00177193554 | 73203712 | 0.415867 |
| bank | 0 | 11 | PASS | 0.00113505768 | 81608704 | 0.510923 |
| bank | 2 | 0 | PASS | 0.00422179766 | 76382208 | 0.390017 |
| bank | 2 | 1 | PASS | 0.00482502215 | 74350592 | 0.424772 |
| bank | 2 | 2 | PASS | 0.00234334687 | 82591744 | 0.510715 |
| bank | 2 | 3 | PASS | 0.0704152195 | 72908800 | 0.391965 |
| bank | 2 | 4 | PASS | 0.0523790565 | 74252288 | 0.416757 |
| bank | 2 | 5 | PASS | 0.217247368 | 82313216 | 0.516095 |
| bank | 2 | 6 | PASS | 0.00212246643 | 72777728 | 0.391086 |
| bank | 2 | 7 | PASS | 0.000581016293 | 74219520 | 0.419811 |
| bank | 2 | 8 | PASS | 0.00231074748 | 82427904 | 0.515471 |
| bank | 2 | 9 | PASS | 0.00412171582 | 77578240 | 0.388804 |
| bank | 2 | 10 | PASS | 0.00632369053 | 73990144 | 0.413639 |
| bank | 2 | 11 | PASS | 0.00224031205 | 82690048 | 0.511356 |

The new raw+feature payload totals **1,159,191,296B**, below the1,343,108,736B conservative bound and2.5GB stage reserve. Existing prior raw/features7,515,644,229B remain retained. Post-run free space was **23,409,127,424B**; this is a snapshot, not future allocation.

Complete summary: `artifacts/task18-evidence/epsilon1em6-fullprep-execution-c715479/complete-summary.json`, SHA `d0e8470fa4793df363c6a5cabfc8be54d458f85d1e07b41d4eedc7128fcd708a`.

Complete inventory: `artifacts/task18-evidence/epsilon1em6-fullprep-execution-c715479/complete-inventory.json`, SHA `3ae2e0cb40afe0251683a7fbb053a1045befe3235f102cc50c357699cc1fe674`. It contains18,786 files/1,249,228,955B and excludes itself. All18,432 raw/feature payload hashes come from actual construction and full cold production integrity scans; reporting rechecked manifest identities and actual lengths without rereading the1.16GB corpus solely for paperwork. Other artifacts, all48 gradient captures and stage/case summary mappings were rehashed. The inventory includes resolved configs, manifests, source/dependencies, helpers, checkpoints, gradients, static/fit ledgers, journals and power/timing records.

Post-run aggregation took0.509s of metadata work, separate from execution. An initial reporting script failed to parse because of a mismatched prose quotation before any aggregation ran; the administrative note and original script are retained. No experiment was repeated. Root's separate read-only list-versus-dictionary inspection correction likewise did not change outputs.

## Proposed next allocation: one fresh matched8192 pair

Propose fresh step0 Jet then Bank runs, each stopping at8192 under the existing potential32768 policy. Keep the seven milestones0/128/512/1024/2048/4096/8192, constant LR0.001, zero weight decay, fixed writer and full rate grids, epsilon1e−6, structured widths125/122, CPUFP64/four threads, chunk32, microbatch1/accumulation3. Keep the common768 fit, `t_ref=1`,96 exposed development histories,6,144-history corpus, shared seed/order and four corpus passes. Do not resume a calibration or old epsilon1e−8 checkpoint.

For each family the sequence must be: fresh8192 training; all12 trained endpoint checks at original1e−12; then one frozen6,144-history TRAIN-risk pass using the actual fixed fit/features and `eval/no_grad`. Bank starts only after Jet's full sequence passes. A failed endpoint stops both risk and the later family, preserving the failed row and costs. Use reviewed checked-sequence plus source/config/checkpoint/hash/count/status checks. The proposed trained endpoint has24 cases total; the completed calibration had48 across steps0/2. TRAIN risk remains a diagnostic empirical objective, not independent central-development evidence.

The prior simple scores remain applicable to the same population and target statistics: shared buckets0.136495 and reservoir0.281477. No simple or raw-corpus rerun is proposed. Their large advantage over prior neural results and the still-moving curves prevent a convergence or practical-utility claim. The numerically failed old structured Jet loss0.365645 is retained as failed evidence.

A results/config/procedure-only commit can keep package57 unchanged while a new runner pins the actual post-promotion Git HEAD. Existing raw and feature identities are package-bound, and the actual v2 read policy, preprocessing and full-file guards passed here. Calibration execution shape binds model, data, seed, lengths, fit/eval counts, device, threads, microbatch and both cache hashes. Valid reuse must still be demonstrated through actual `resolve_policy`, execution-shape and production cache guards when config preparation is separately authorized. Derive only learning mode and the actual new calibration path/hash; never re-sign old manifests, weaken source guards or resume across changed config/source. Current cold checkpoints remain historicalc715 evidence. No next config or aggregate calibration file has been prepared now.

Forecast **900–1,100 execution seconds** for both fresh8192 runs,24 endpoint cases and two frozen TRAIN-risk passes, including full identity/scan/checkpoint/ledger overhead. The main anchor is the prior same-graph Jet8192 run at411.535s; current cold profiles are slightly faster than prior178.6/176.4s, fitted24-case drivers are~33s/family, and prior cached TRAIN-risk passes were~21–25s/family. Bank structured8192 was never executed in the failed old arm, so its estimate is inferred from the matched graph. Refine the forecast at the declared128 milestone without extra evaluation. This is a forecast, not a proposed hard cap.

8192 is a bounded exploratory allocation, not a convergence criterion. If the trained endpoint fails, investigate before any further learning. If both pass, use full curves, length/task slices and frozen risks against simple controls to decide the next allocation. No automatic16384+, broader grid, whole-Task18 acceptance, statistical qualification or protected phase. **Hold for root ruling.**
