# Epsilon 1e−6 fresh paired learning — preparation only

Status: **prepared, not executed; waiting for controller inspection and release.** No scientific process, model construction, fit, cache scan, numerical case or test ran during this preparation.

The accepted operational evidence was promoted in `60fbcc5b32931f483ceac2bb327ed8d699f62313`. A suffix-filter oversight included two `.pt.previous` checkpoints; authorized follow-up `76e5f8cea0c4bfc763ecefcd35184950562caeb3` removes only those durable copies, retaining the original ignored files and complete hash inventory. This clean HEAD is the actual proposed execution source. Package remains `57c0920f360e47f2c3978f056437143c4262b8ab9653b753df1321402ade9717`.

The corrected promotion contains 296 byte-exact copies / 15,434,383 bytes. Its manifest is `docs/research/task18-epsilon1em6-operational-promotion-manifest.json`, SHA `9e089259804f70667b66d7bb084e1c7c74af54d9d8c55f398ec2503121d7e215`; verification SHA `38b39c0dc21481fc4613c23073a82650ed07302947b812a702aca2633fde24c6`. All five design/review documents are explicitly UNADOPTED. The executed operational source remains c715479, not the new metadata HEAD.

## Sealed preparation

Directory: `artifacts/task18-evidence/epsilon1em6-learning-preparation-76e5f8c/`.

- `preparation-seal.json`: `22f50f711ed56e3da77c1cf7c55c518798182057a92bd78536f2a6df2be69b4d`.
- `preparation-verification.json`: `229d897ce4183a37bb667017d5549a53e46f538e803b6f1db1c4644087d2df85`.
- Ten executable helper sources are byte-identical to their archives; 95 dependencies and all 51 package-file hashes are bound. `helper-delta.patch` records the full changes from the reviewed historical helpers.
- The reused independent structured equations, numerical metric/static helper and `task18_checked_sequence.py` are unchanged. The config shim binds actual new source/config paths. New driver/gate code is external phase orchestration only.
- `procedure.json` fixes scope, counts, ordering and limits. `jet-learning.yaml` / `bank-learning.yaml` and the genuine operational `calibration.json` are immutable preparation artifacts.
- Outer wrapper `/tmp/task18_epsilon_learning_timeout.py` equals its archived copy, SHA `cee305a21fae4d41fdf029135258d6e24fc98ad3b9bb361db0f4bf118222fe72`. `launch-allocation.json` binds wrapper and seal. It retains the reviewed process-group timeout body: TERM, three-second grace, KILL all surviving group members even if the parent has exited, preserve timeout/error/timing, no retries.

The wrapper is prepared, not launched. Proposed command after explicit release:

```sh
.venv/bin/python /tmp/task18_epsilon_learning_timeout.py
```

Underlying driver: `/tmp/task18-epsilon-learning-76e5f8c/task18_epsilon_learning_driver.py`. Output roots must not exist: `artifacts/task18/epsilon1em6-learning-76e5f8c/` and `artifacts/task18-evidence/epsilon1em6-learning-execution-76e5f8c/`.

## Exact run and failure boundaries

1. Fresh Jet from step 0, stop at 8192; no checkpoint resume.
2. All 12 actual trained Jet endpoint cases at unchanged atol=rtol=1e−12.
3. Only after all endpoint cases pass, one frozen 6144-history empirical TRAIN-risk pass.
4. Only after all Jet stages pass, fresh Bank8192, its 12 endpoint cases and one 6144-history TRAIN-risk pass.

Each dependent phase requires fresh output, exit code, accepted full status, exact source/config/cache/checkpoint hashes, counts and memory bounds. The reviewed checked-sequence function prevents shell-newline fallthrough. Endpoint helpers independently check actual saved step8192 and exact source/config/data/lock/policy through `load_checkpoint` before reconstruction. Failure, missing/failed summary or provenance mismatch blocks risk and the later family. A nonzero failure/support/prediction flag in the completed TRAIN-risk record blocks later work; no histories are silently dropped. All raw rows remain retained.

Same fixed full-grid bases/writer, structured Jet125/Bank122, epsilon1e−6/support floor1e−8, CPU FP64/four threads/chunk32/microbatch1/accumulation3/LR.001/wd0. Persistent state9345 bytes each; allocated parameters30134/30021, MACs29875/29768; prior post-fit primary-active upper bounds29008/28800 remain upper bounds. No padding or exact active-budget equality is claimed.

The shared training fit is768 histories, t_ref1, target hash0cebf5f59f3b44f44875b73d582e6cb3c21a0ade54867edfabaebcab220dad21. Evaluation uses all96 exposed histories with equal128/512/2048 lengths and four regimes. Both consume the identical6144-history finite corpus four times in unchanged balanced order:24576 logical draws,8192 updates. Seven observers:0,128,512,1024,2048,4096,8192. The existing potential policy horizon32768 is not allocated beyond8192. Reuse existing common-stat simple scores; no simple or old memory/reference campaign rerun.

## Actual production applicability checks

Both new configs have exactly three changes from their actual cold configs: `development.mode`, `development.calibration_path`, `development.calibration_hash`. Actual `load_config`, `resolve_policy` and canonical `execution_shape` equality passed. Model/data/seed/reader/epsilon/precision/fit/eval/count/cache identities are unchanged. Calibration retains actual c715 origin, actual2/configured32768 and initial/fitted0/2-only applicability; it does not guarantee trained endpoints.

Raw manifest canonical hash is `c18c09aa22127efb6ee56851cbde76a5bb0dd1bb1ef6218abfca6128ab62a43f`. Feature canonical hashes are Jet `1a606013ae4f65f81086d22b53c88f10c4f11be8cede6bc9ef9dd0d959507eab` and Bank `399040693be4795147f7690f0add7a3154a09082c44bfa55fc6524926588e592`. Genuine v2 identities bind package57, exact read policy, actual frozen preprocessing and schemas. No manifest was rewritten or re-signed; metadata HEAD equality is not asserted. Production `TrainingFeatureCache` after each actual fresh fit must recompute exact v2 identity and perform its full raw/feature integrity scans. Preparation checked canonical manifests and existing cold scan evidence only; no redundant corpus read or synthetic fitted identity.

Numerical endpoints retain exact fixed-kernel/event/terminal/raw/new-feature replay against accepted initial1e−6 captures at9aca/package57, with the old e756 memory evidence composed through unchanged dependencies. Actual trained reader task/input/reader gradients are newly checked. The shared production MLP/query-input mapping is not an independent MLP oracle. Original epsilon1e−8 failure remains FAILED; no reduced-scope or tolerance waiver is used.

## Resource allocation proposed, not consumed

External whole-process-group cap1800 seconds; unchanged net201326592 bytes; at least4GiB free before every phase. No power override, retry or automatic extension. Phase and outer UTC/perf boundaries and power observations are retained separately. Forecast900–1100 execution seconds, based on the earlier same-graph Jet8192 run411.535s, new accepted cold timings, endpoints~16–20s/family and frozen risks~21–25s/family. The inherited risk helper retains its older25–40s forecast; actual timing will be reported rather than overwritten. First128 milestone refines the uncertain paired forecast. Civil completion time can differ with host sleep/power conditions.

Static preparation verification parsed helper ASTs and checked bytes/hashes/paths/config policy only. No passing test suite was repeated. Both output roots are absent and Git is clean. Task18 remains open; no convergence, practical advantage, broader family acceptance, statistical qualification or protected phase is authorized by this preparation.
