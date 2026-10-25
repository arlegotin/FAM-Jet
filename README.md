# FAM-Jet

Compress a stream before you know the question. Then ask different questions about its past without replaying the history.

FAM-Jet tests a specific bet: **keeping an exact first moment of event age should make a small associative memory more useful for later temporal queries.** Each decay rate stores both weighted content and weighted age. The fair comparison spends the same bytes on more ordinary decay rates instead.

The mechanism works. Its extra structure hasn't earned a general performance win in this study. Two protected synthetic panels slightly favor Jet on average, but both uncertainty intervals include zero. Simple temporal buckets do better on the synthetic averages, and the ordinary exponential bank wins the real-trained sensor comparison. The repository contains the implementation, matched experiment, complete results and the evidence needed to inspect that outcome.

[Results](#results) · [How it works](#how-it-works) · [Quick check](#quick-check) · [Reproduce](REPRODUCE.md) · [Full report](reports/famjet-poc/final.md) · [Citation](CITATION.cff)

## What you can reuse

- **Exact temporal-moment memory.** Streaming updates, direct-sum references, terminal contractions, normalized reads and rate derivatives. Querying advances a copy; it doesn't age or mutate the saved history.
- **A controlled basis comparison.** Four Jet anchors versus eight ordinary exponential anchors, with identical writers and actual persistent bytes. Equivalent gamma/Laguerre coordinates expose what is a change of representation rather than extra information.
- **Deferred temporal-query tasks.** Hard-window observed-event means and adjacent-window contrasts, exact event-level targets, simple storage baselines, chronological sensor splits and explicit failure handling.
- **An inspectable experiment.** Frozen selection, paired history-level uncertainty, ingestion/query costs, state and parameter accounting, raw prediction records and report-only replay. Failed attempts remain in the audit.

The completed experiment ran locally on one 36-GiB M3 Max, using CPU float64. It requires no remote GPU, paid model API or language model.

## How it works

An ordinary exponential memory discounts an event by its age. Jet also retains the same contribution multiplied by its dimensionless age. At rate $\lambda$, with event age $a_i=T-t_i$ and associative write $X_i$:

$$
Z_\lambda=\sum_i e^{-\lambda a_i}X_i,
\qquad H_\lambda=\sum_i(\lambda a_i)e^{-\lambda a_i}X_i.
$$

For a time gap $\Delta$, let $d=\lambda\Delta$ and $\alpha=e^{-d}$. The exact update is:

$$
H'=\alpha H+\alpha dZ,\qquad Z'=\alpha Z+X_t.
$$

The moment uses the **old** $Z$; a new event has age zero. A normalization column travels with the values. The later reader sees the retained anchors and the requested time window. Historical writes never see that question.

This is a repeated-pole/gamma system. Derivatives do not create another category of memory or certify an answer's confidence. The research question is whether this particular temporal basis is useful enough to justify its bytes and cost. [Specification](docs/superpowers/specs/2026-10-16-famjet-design.md) · [Prior art and adaptations](docs/baseline_adaptations.md)

## Results

The entered study uses known one-hot keys, fixed writers, query-conditioned ridge readers and one state budget. Jet4 and Bank8 each retain **9,345 bytes per synthetic history**; reader parameters and runtime costs are reported separately. Targets are hard windows and contrasts, not exponentially weighted answers chosen to fit the proposed kernel.

### Synthetic histories

Lower normalized squared error is better. Each panel contains **3,072 independent histories** across three lengths and four signal regimes.

| Panel | Jet4 | Bank8 | Temporal buckets |
| --- | ---: | ---: | ---: |
| Confirmation | 0.15649 | 0.19184 | **0.12862** |
| Independent replication | 0.16638 | 0.20607 | **0.14074** |

The paired Bank-minus-Jet effects are **+0.03535**, 95% interval **[−0.01971, +0.09042]**, and **+0.03968**, interval **[−0.01275, +0.09211]**. Positive favors Jet. Both intervals cross zero: superiority was not demonstrated. Bucket averages are descriptive comparisons, not an additional registered significance claim.

![Paired Jet-versus-bank effects and uncertainty](reports/famjet-poc/final-charts/primary-effect.svg)

These intervals condition on the actual frozen fits, training corpus, preprocessing and selection. They do not include variation from retraining the whole procedure.

### Real sensor histories

Observed PM2.5 at 12 Beijing stations, with chronological training/development/test splits and **56 nonoverlapping 14-day test histories**. Lower RMSE is better, in µg/m³. Each memory uses **1,665 persistent bytes** here.

| Reader training | Jet4 RMSE | Bank8 RMSE |
| --- | ---: | ---: |
| Shape-matched synthetic training, frozen for transfer | **130.49** | 1069.5 |
| Training and tuning on the real task | 68.64 | **21.36** |

Frozen transfer favors Jet over Bank, but both are worse than simple sensor summaries near 54–63 RMSE. After real-task training, the bank has lower RMSE and MAE. Temporal-cluster ranges describe the evaluated 2015–17 period; they are not a guarantee about future pollution histories.

The [full report](reports/famjet-poc/final.md) keeps all eight scored methods, native-unit errors, numerical failures and measured costs visible. The [machine report](reports/famjet-poc/final.json) is about 45 MB. [Cost chart](reports/famjet-poc/final-charts/cost.svg) · [Memory/accuracy chart](reports/famjet-poc/final-charts/accuracy-memory.svg)

## Quick check

The recorded lock targets **CPython 3.13.5 exactly, macOS 14+ on ARM64**. Other environments need their own dependency resolution and numerical checks. From the repository root:

```sh
python3.13 --version  # must be 3.13.5 for the recorded environment
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m pytest -q tests/test_algebra.py tests/test_time.py tests/test_gradients.py
```

That checks the mechanism without downloading the sensor dataset or running the study. [REPRODUCE.md](REPRODUCE.md) covers the full test suite, the public evidence bundle, report replay and fresh experiments. Core evaluation and reporting run locally; plots use a separate locked environment.

## What the result leaves open

The current configuration doesn't justify replacing simpler memory methods. It also doesn't establish the best possible reader, learned addressing, interference tolerance or an information-capacity limit. HiPPO and modern delta-rule implementations have separate component records; this experiment does not claim to beat those families. Language and agent memory remain untested.

The broader architectural novelty claim was withdrawn because gamma, Laplace and multiscale polynomial memories already overlap with the mechanism. The useful contribution is the controlled implementation and evidence about this allocation of a fixed memory budget. A new reader or task should face the same byte accounting and fresh evaluation.

[Final audit](docs/research/e2e-final-audit/README.md) · [Publication scope](docs/PUBLICATION.md) · [Development history](docs/research/prepublication-readme.md)

## License and citation

By **Artem Legotin**. Original software is **AGPL-3.0-only**; original writing and result presentation are **CC BY 4.0**. [Licensing scope](LICENSING.md) and [third-party notices](THIRD_PARTY_NOTICES.md) retain upstream rights, including the UCI data attribution.

Please cite [CITATION.cff](CITATION.cff), link this repository and identify the commit you used. Development, experiments and reporting used AI assistance under the owner's direction. README editing used [write-like-me](https://github.com/arlegotin/write-like-me).
