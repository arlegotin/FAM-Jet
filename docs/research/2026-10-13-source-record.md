# Supplied research brief: evidence and provenance

The user supplied “Research and local proof-of-concept plan: query-conditioned exponential-moment memory,” dated 13 October 2026, with sections 1–16 and Appendix A. The specification and implementation plan are derived documents, not an unchanged archival copy of that brief. They retain its scientific contract and make implementation decisions explicit so execution can proceed without chat history.

The research cutoff remains **13 October 2026**. The local planning date is **16 October 2026**. This task has not repeated a literature review, inspected external repositories, downloaded assets, checked current licenses, executed the supplied NumPy script, or reproduced published systems. Descriptions of previous inspection and numerical results below are **reported by the supplied brief**, not independently verified in this repository. Asset verification remains WP00/WP05 work. Do not promote supplied claims into executed local evidence.

## Evidence classes

| Class | Record |
|---|---|
| Supplied research assessment | Withdraw broad function-valued architectural novelty; investigate repeated-pole versus distinct-pole allocation and full resource tradeoffs. |
| Analytical specification | Exact dimensionless moment recurrence, normalized derivative, invertible gamma/Laguerre control, and nonnested finite kernel spans. Must be verified by implementation tests. |
| Supplied executed checks | Python 3.13.5, NumPy 2.3.5, Linux x86_64 CPU, seed 20261013; 512 events, positive five-dimensional keys, three signed values, four rates from 0.001 to 1. |
| Executed during this task | Repository inspection and read-only Mac discovery recorded in the [environment snapshot](2026-10-16-local-environment.md). |
| Unexecuted | All training, dataset ingestion, MPS operations, native benchmarks, protected evaluation, and language integration. |

The supplied checker reported relative errors: FP64 recurrent/direct `Z` 1.0731e-15, `H` 1.8252e-15, equivalent-coordinate `H` 6.8016e-16; FP32/direct `Z` 6.9465e-7, `H` 7.8878e-7, equivalent-coordinate `H` 7.8502e-7; normalized derivative/FP64 central difference 2.4007e-11. These are fixture observations, not acceptance thresholds or Apple measurements. FP32 finite-difference moment errors increased from about 7.32e-4 at spacing 1e-1 to 1.31e-1 at 1e-6; a direct bank reader is not obliged to use differences.

The supplied positivity counterexample is one impulse of age 1: Hermite interpolation of `exp(-lambda)` in log-rate between 1 and 1000, with exact slopes, reaches about -0.135026 at rate 25.5623 while the true value is about 7.9147e-12. Reproduce this diagnostic; interpolation stays disabled in the core.

## Source ledger

All links and revision identifiers in this table are supplied references. Resolve accessibility, identity, revisions, and licenses before dependent use. A citation is neither a reproduced implementation nor commercial-use clearance. Licensing statements are provenance leads requiring verification, rather than a legal opinion from this planning task.

| ID | Supplied primary source | Relevance / execution obligation |
|---|---|---|
| R01 | [de Vries & Príncipe, gamma memory](https://proceedings.neurips.cc/paper/1990/file/6c524f9d5d7027454a783c841250ba71-Paper.pdf) | Repeated-pole equivalence; no novelty in recurrence alone. |
| R02 | [Shankar & Howard, scale-invariant time representation](https://doi.org/10.1162/NECO_a_00212) | Laplace-history context; brief reports metadata/abstract inspection. |
| R03 | [Laplace Neural Manifolds, v2](https://arxiv.org/html/2302.10163v2) | Symbol-conditioned temporal associations; later revisions were not fully compared. |
| R04 | [Time-Local Transformer](https://link.springer.com/article/10.1007/s42113-025-00253-9) | Reconstructed timeline via Gaver–Stehfest, distinct input semantics. |
| R05 | [HiPPO](https://arxiv.org/abs/2008.07669) | Polynomial history representation. |
| R06 | [HiPPO Zoo, v2](https://arxiv.org/html/2602.21340v2) | Closest continuum-scale and associative comparator; reproduce finite system. |
| R07 | [HiPPO Zoo repository](https://github.com/jackgoffinet/hippo-zoo/tree/04e38b3cf246f4c50cb6c6a7e10597e2e37eebc7) | Supplied commit `04e38b3cf246f4c50cb6c6a7e10597e2e37eebc7`; MIT labeling reported. Inspect `src/mpm/models.py`, `src/mpm/polynomials.py`, **`scripts/multiscale_hippo.py`**. Log-rate construction is in the last file; associative code uses scalar key/query locations. |
| R08 | [RetNet](https://arxiv.org/abs/2307.08621) | Distinct-decay context; the local bank is retention-style, not full RetNet. |
| R09 | [Gated Delta Networks, v3](https://arxiv.org/abs/2412.06464v3) | Overwrite-aware comparator. |
| R10 | [Gated DeltaNet-2, v1](https://arxiv.org/html/2605.22791v1) | Separate erase/write recurrence, KDA/GDN reductions. |
| R11 | [GDN-2 repository](https://github.com/NVlabs/GatedDeltaNet-2) | Brief reports NVIDIA Source Code License-NC. Wrapper `lit_gpt/gdn2.py` blob `4a0199c69b2097d2637bb8714d707bd53e67e91d`; license blob `d50677fec39f78e04515c615d30ad16741f8a29c`. These are **not commit pins**; resolve full revision before reuse. Keep licensed checkouts separate. |
| R12 | [Mamba-3, v1](https://arxiv.org/html/2603.15569v1) | Contemporary reference; scalar EMA is not a faithful reproduction. |
| R13 | [Mixture-of-Memories, v1](https://arxiv.org/html/2502.13685v1) | Routing context; count every stored bank. |
| R14 | [Adaptive Memory Decay for Log-Linear Attention, v1](https://arxiv.org/html/2605.06946v1) | Hierarchical growth differs from fixed state; separate memory–history curve. |
| R15 | [Function-space architectures, v1](https://arxiv.org/abs/2506.10973v1) | Broad context; brief did not fully inspect the journal article. |
| R16 | [UCI Beijing Multi-Site Air Quality](https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data) | DOI 10.24432/C5RK5G; reported CC BY 4.0, 12 sites, 420,768 hourly rows, March 2013–February 2017. Verify archive/schema/counts/license. |
| R17 | [LongMemEval, v2](https://arxiv.org/html/2410.10813v2) | Conditional language stage; official judges and licenses require separate checks. |
| R18 | [LongMemEval-V2, v1](https://arxiv.org/abs/2605.12493v1) | Experience/context gathering and strong file/search alternatives; no local benchmark claim. |
| R19 | [BABILong, v2](https://arxiv.org/abs/2406.10149v2) | Optional language benchmark; inspect constituent corpus rights. |
| R20 | [LongBench v2](https://aclanthology.org/2025.acl-long.183/) | Broad long-context reference, not the numeric core. |
| R21 | [Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B), [Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B) | Optional frozen decoders, Apache 2.0 labeling reported; verify revisions/assets/native path. |
| R22 | [Time-Local Transformer repository](https://github.com/cogneuroai/time-local-transformer) | `gaver_cell.py` blob `a380990b7add55b4f0109ad03a8d2d40ae5b3b31`; no license surfaced in supplied inspection. Do not vendor without established permission; blob is not commit pin. |
| R23 | [EP3935568A1, Legendre memory units](https://patents.google.com/patent/EP3935568A1/en) | Technical prior-art lead, no claim-chart/FTO/legal-status conclusion. |
| R24 | [PyTorch 2.14 MPS notes](https://docs.pytorch.org/docs/2.14/notes/mps.html), [API](https://docs.pytorch.org/docs/2.14/mps.html) | Documentation version reported in brief, not an installed wheel. Use installed-version official docs at WP00. |
| R25 | [PyTorch 2.14 MPS environment](https://docs.pytorch.org/docs/2.14/mps_environment_variables.html) | Disable CPU fallback for native timing; preserve allocator protection. |
| R26 | [How Linear Attention Remembers, v1](https://arxiv.org/html/2609.33093v1) | Supplied interference study; verify identity before reliance. Separate load from elapsed time. |

## Coverage and amendment rules

The brief reports searches spanning gamma/Laplace/Laguerre memory, polynomial/multiscale/associative HiPPO, recurrent/delta/routed models, temporal and language benchmarks, MPS documentation, asset licenses, and limited patent triage. This is not exhaustive novelty or patent clearance. A publication needs a new targeted search against the mechanism actually supported by results.

The derived documents preserve H0–H7 and WP00–WP10. Builder decisions are: package directly at repository root, immutable snapshots with an explicit timestamp contract, strict artifact schemas, staged confirmation that permits a narrow core result without every optional extension, and no executable stubs during this documentation task. A separate source, schema, precision, task, population, metric, baseline, budget, or stopping-rule change during execution needs a dated amendment and fresh protected data when interpretation changes.
