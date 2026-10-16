# Source verification reconnaissance — 16 October 2026

Read-only inspection for specification §§7–8/11 and source-record R06/R07/R10/R11/R16/R22/R24/R25. This report is the only file written by this task. No repository checkout, source vendoring, package installation, dataset download, numerical reproduction, training, or benchmark was performed. Dates below are source metadata, not scientific results. Research cutoff remains 13 October 2026.

## Verified sources and outstanding gates

| Source | Verified evidence | Remaining gate / scope implication |
|---|---|---|
| UCI Beijing | Official metadata, DOI, archive name, schema descriptions, license label accessible. | Actual archive hash, members, station identities, CSV headers, row counts, missingness, timestamp coverage/order/duplicates remain WP02 checks. No real-transfer result yet. |
| HiPPO Zoo | Supplied commit exists; pinned MIT text and relevant source inspected. Log-rate script agrees with specified finite matrices and Bessel coefficients. | Dense/diagonalized propagation, quadrature and task positive controls still require execution. Keep event-impulse adaptation distinct from source ZOH reproduction. |
| GDN-2 | Paper exists; official repository revision resolved; supplied wrapper and license blobs match. | Native implementation and tied-gate/mixer fidelity checks unexecuted. Source reuse has noncommercial restrictions; do not silently copy into general project code. |
| Time-Local | Article and repository identity verified; supplied Gaver blob resolves to a complete commit. | No repository license or permission statement found. Do not vendor. Equation-based adaptation and a licensed source reproduction are separate obligations. |
| PyTorch MPS | Official current guidance and backend source inspected. | Installed-version docs and actual operation support remain WP00 work; no wheel/version or MPS execution certified here. |

## UCI Beijing (R16)

[UCI dataset 501](https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data) identifies DOI [10.24432/C5RK5G](https://doi.org/10.24432/C5RK5G), 12 monitoring sites, 420,768 hourly records, 1 March 2013–28 February 2017 and `NA` missing values. It lists `PRSA2017_Data_20130301-20170228.zip` (7.6 MB) and describes 18 columns: `No,year,month,day,hour,PM2.5,PM10,SO2,NO2,CO,O3,TEMP,PRES,DEWP,RAIN,wd,WSPM,station`; PM2.5 units are micrograms/m³. It labels the dataset CC BY 4.0 and gives attribution to Chen, S. (2017). [CC BY 4.0 terms](https://creativecommons.org/licenses/by/4.0/) require appropriate attribution, a license link and indication of changes.

The page's download target is [the UCI outer archive](https://archive.ics.uci.edu/static/public/501/beijing%2Bmulti%2Bsite%2Bair%2Bquality%2Bdata.zip). Browser retrieval refused it with `Content length is too large: 4194305+`; no shell download was attempted under this reconnaissance's no-heavy-assets constraint. The page also lists auxiliary JPG/CSV files, so the outer download must not be assumed to be identical to the named PRSA archive. Metadata is not an executed validation of extracted CSVs. The metadata inspected does not specify a timezone; retain the spec's documented dataset-local civil-hour convention and do not infer system-local DST.

## HiPPO Zoo (R06/R07)

[arXiv v2](https://arxiv.org/abs/2602.21340v2) verifies the title/authors and v2 revision date 29 May 2026. [Appendix D.3–D.4](https://arxiv.org/html/2602.21340v2#A4.SS3) describes the log-scale formulation and its diagonalized bank interpretation. No paper result was reproduced.

GitHub API verifies [commit `04e38b3cf246f4c50cb6c6a7e10597e2e37eebc7`](https://github.com/jackgoffinet/hippo-zoo/commit/04e38b3cf246f4c50cb6c6a7e10597e2e37eebc7), committer date `2026-05-29T14:40:37Z`. The correct license filename is **LICENSE.md**. [Pinned license](https://github.com/jackgoffinet/hippo-zoo/blob/04e38b3cf246f4c50cb6c6a7e10597e2e37eebc7/LICENSE.md), blob `506995421a006e3da02a4f7c02f79eae13eaeb26`, contains the MIT grant, copyright 2026 Jack Goffinet; retain copyright and permission notices for copied/substantial material.

| Pinned file | Git blob |
|---|---|
| [scripts/multiscale_hippo.py](https://github.com/jackgoffinet/hippo-zoo/blob/04e38b3cf246f4c50cb6c6a7e10597e2e37eebc7/scripts/multiscale_hippo.py) | `38f3efb7f5a3f2538cc4ce284b931770086e655e` |
| [src/mpm/models.py](https://github.com/jackgoffinet/hippo-zoo/blob/04e38b3cf246f4c50cb6c6a7e10597e2e37eebc7/src/mpm/models.py) | `35acec2230e392d80e2fe8a68c3028cf97a8afd8` |
| [src/mpm/polynomials.py](https://github.com/jackgoffinet/hippo-zoo/blob/04e38b3cf246f4c50cb6c6a7e10597e2e37eebc7/src/mpm/polynomials.py) | `efaca78a15cba574ef6017e6a195127b0cf00834` |

The script's lines 113–149 construct symmetric Jacobi off-diagonals `r/sqrt((2r-1)(2r+1))`, `G=sqrt(eps)*expm(log(1/eps)*Jx/2)` (explicitly symmetrized), and analytic input coefficients `beta_r=sqrt(eps)*sqrt((2r+1)*log(1/eps))*i_r(log(1/eps)/2)` using modified spherical Bessel functions. `B=b betaᵀ`. Lines 375–402 divide A/b by the base timescale, flatten with transpose convention, and form `kron(G.T,A)`. Lines 235–243 discretize through an augmented dense exponential for **ZOH** input. Therefore the spec's impulse write is a declared adaptation, not verbatim reproduction. Use these analytic coefficients rather than substituting a finite-truncation `G e0`; the latter is not what this script implements. Source inspection does not replace converged quadrature or dense-versus-diagonalized tests.

`models.py` lines 366–373 map state to scalar sigmoid key/query locations and evaluate Legendre vectors there; it is not a generic arbitrary dense-key associative implementation.

## Gated DeltaNet-2 (R10/R11)

[Primary paper v1](https://arxiv.org/abs/2605.22791v1) exists, submitted 21 May 2026; [full text](https://arxiv.org/html/2605.22791v1) links the official NVlabs repository. Sections 3.1/3.5 and Appendices C/D support the spec's decay-before-erase recurrence, separate key-side erase/value-side write gates, tied KDA/GDN reductions, short causal convolutions, q/k L2 normalization, RMSNorm/SiLU output gate and FP32 recurrent state. These are implementation requirements, not local benchmark evidence.

GitHub API resolves current `main` to [commit `de8476de0fecae08fc16f0bf3154900244c61c73`](https://github.com/NVlabs/GatedDeltaNet-2/commit/de8476de0fecae08fc16f0bf3154900244c61c73), committer date `2026-10-11T07:14:11Z`, before the research cutoff. At this complete pin:

- [lit_gpt/gdn2.py](https://github.com/NVlabs/GatedDeltaNet-2/blob/de8476de0fecae08fc16f0bf3154900244c61c73/lit_gpt/gdn2.py) is exactly supplied blob `4a0199c69b2097d2637bb8714d707bd53e67e91d`.
- [LICENSE](https://github.com/NVlabs/GatedDeltaNet-2/blob/de8476de0fecae08fc16f0bf3154900244c61c73/LICENSE) is exactly supplied blob `d50677fec39f78e04515c615d30ad16741f8a29c`, NVIDIA Source Code License-NC. Its §3.3 limits the Work and derivatives to research/evaluation noncommercial use; §§3.1–3.2 require license/notices and preservation of that limitation. This is evidence of source restrictions, not commercial clearance.

The wrapper imports FLA helpers and local chunk/fused recurrent kernels, uses q/k/v short convolutions (default size 4), separate sigmoid `b_proj`/`w_proj`, and explicit FP32 decay parameters. A native PyTorch/MPS equation implementation must implement the complete mixer and cache accounting; the wrapper is not a standalone portable recurrence. Keep any restricted source reference separate. Equation attribution alone does not establish legal clearance.

## Time-Local Transformer (R04/R22)

[Publisher article](https://link.springer.com/article/10.1007/s42113-025-00253-9) verifies DOI/title, publication date 6 August 2025 (March 2026 issue), CC BY 4.0 article rights and the official code link. Article licensing does not itself establish a license for externally hosted repository files.

GitHub API resolves [repository main](https://github.com/cogneuroai/time-local-transformer) to [commit `99a1a04eb67771a4b1c4b05f7909e1697b8b94ae`](https://github.com/cogneuroai/time-local-transformer/commit/99a1a04eb67771a4b1c4b05f7909e1697b8b94ae), committer date `2025-06-05T16:35:38Z`. [gaver_cell.py](https://github.com/cogneuroai/time-local-transformer/blob/99a1a04eb67771a4b1c4b05f7909e1697b8b94ae/gaver_cell.py) matches supplied blob `a380990b7add55b4f0109ad03a8d2d40ae5b3b31`. The complete recursive tree has seven files (README, four model/helper Python files, train.py and data/wikitext2/prepare.py), with no LICENSE/COPYING/NOTICE; README has no license/permission/copyright statement. No reuse permission was established.

The inspected Gaver code uses double-precision coefficients/state and `exprel` input in its update (lines 36–63/89). A local FP32 impulse implementation changes precision and input semantics; label it equation-based. Source reproduction/vendoring remains blocked until permission is established; a public code link is insufficient. The optional comparator may be excluded with a documented scope restriction before confirmation.

## PyTorch MPS (R24/R25)

The official [stable environment URL](https://docs.pytorch.org/docs/stable/mps_environment_variables.html) currently redirects to [2.14 documentation](https://docs.pytorch.org/docs/2.14/mps_environment_variables.html). This verifies current web guidance, not an installed dependency. Browser search retrieved the environment table; direct HTML retrieval was incomplete and a shell request received HTTP 403. The official [Markdown source](https://github.com/pytorch/pytorch/blob/2d813dbbbf2b8e7d2691d720de998de04faca39b/docs/source/mps_environment_variables.md) was inspected via API (blob `c2c2f6a77f5eea3eae88a75dfbab9699b2ecee53`; current main resolved to `2d813dbbbf2b8e7d2691d720de998de04faca39b`).

- `PYTORCH_ENABLE_MPS_FALLBACK=1` enables general unsupported-op CPU fallback; `PYTORCH_MPS_FAST_MATH=1` enables fast math. Set both to `0` before importing torch for the reference native path.
- High watermark defaults to 1.7, low watermark to 1.4 unified / 1.0 discrete. High is a hard allocation limit relative to recommended working set; low governs adaptive commits/garbage collection. Setting high to zero removes the protective limit; low zero disables adaptive commit/GC. Preserve protection.

[MPS backend notes](https://docs.pytorch.org/docs/2.14/notes/mps.html) distinguish `is_built()` from `is_available()`. [MPS API](https://docs.pytorch.org/docs/2.14/mps.html) documents synchronization, allocator/driver/recommended-memory queries and RNG state APIs; check their existence in the eventual installed version.

[Official MPSFallback.mm](https://github.com/pytorch/pytorch/blob/2d813dbbbf2b8e7d2691d720de998de04faca39b/aten/src/ATen/mps/MPSFallback.mm), blob `18f80156ba2f8ecee0a5825a4da9eb3914e58bd5`, reads the general fallback environment once and treats unset/`0` as error fallback. It also explicitly registers selected CPU fallback operations independently, including `embedding_renorm_` and `_slow_conv2d_forward`. Consequently `FALLBACK=0` is necessary but does not prove every operation is native; planned operation checks/profiling remain required. Source-main behavior must not be assumed identical to an installed release.

## Access record and reproducible verification commands

Browser cache failures affected pinned GitHub HTML/raw pages and GitHub API pages; successful read-only shell API calls resolved them. Initial sandboxed urllib calls failed DNS resolution; approved read-only network calls succeeded. An initial HiPPO `LICENSE` lookup used the wrong filename; `LICENSE.md` was then verified. Initial PyTorch `.rst` lookup returned 404; the official docs index established `.md`. No approval rejection occurred.

The following reproduces the successful small-source inspection pattern without writing/vendoring files (standard-library Python only):

```sh
python3 - <<'PY'
import base64, json, urllib.request
repos = {
    'jackgoffinet/hippo-zoo': '04e38b3cf246f4c50cb6c6a7e10597e2e37eebc7',
    'NVlabs/GatedDeltaNet-2': 'de8476de0fecae08fc16f0bf3154900244c61c73',
    'cogneuroai/time-local-transformer': '99a1a04eb67771a4b1c4b05f7909e1697b8b94ae',
}
def get(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)
for repo, pin in repos.items():
    commit = get(f'https://api.github.com/repos/{repo}/commits/{pin}')
    print(repo, commit['sha'], commit['commit']['committer']['date'])
    tree = get(f'https://api.github.com/repos/{repo}/git/trees/{pin}?recursive=1')
    print('truncated', tree.get('truncated'))
    print([(x['path'], x['sha']) for x in tree['tree']
           if any(term in x['path'].lower() for term in ('license', 'copying', 'notice', 'multiscale_hippo.py', 'gdn2.py', 'gaver_cell.py'))])
repo, pin = 'jackgoffinet/hippo-zoo', repos['jackgoffinet/hippo-zoo']
item = get(f'https://api.github.com/repos/{repo}/contents/scripts/multiscale_hippo.py?ref={pin}')
print(item['sha'])
lines = base64.b64decode(item['content']).decode().splitlines()
for start, end in ((113,149), (235,243), (375,402)):
    print('\n'.join(f'{i+1}: {lines[i]}' for i in range(start-1, end)))
PY
```

Executed checks were source/metadata reads only. Required follow-up: validate UCI assets under declared disk bounds; implement numerical comparator gates; match official PyTorch docs/source to the resolved local wheel. No inaccessible source here requires replacing the core synthetic population.
