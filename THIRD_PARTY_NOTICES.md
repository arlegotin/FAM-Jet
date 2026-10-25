# Third-party material and attribution

The project license grants rights in original FAM-Jet material. It does not relicense external data, dependencies, papers, source repositories or their notices.

## Beijing Multi-Site Air Quality

Chen, S. (2017). *Beijing Multi-Site Air Quality* [Dataset]. UCI Machine Learning Repository. DOI: [10.24432/C5RK5G](https://doi.org/10.24432/C5RK5G). [Catalog](https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data). License: **CC BY 4.0**, [full terms](licenses/CC-BY-4.0.txt).

The study selects observed PM2.5 across 12 stations, omits missing measurements, creates chronological 14-day histories and computes observed-event means/contrasts with training-only normalization. These are project transformations, not the original raw dataset or regulatory exposure estimates. The full raw archive/derived source arrays are not committed. Published query records and real-data-derived results retain the source attribution. The fixed source archive SHA and exact transformations are recorded in [the preparation record](docs/research/2026-10-16-beijing-preparation.md) and [sealed report](reports/famjet-poc/final.md). No UCI or data-author endorsement is implied.

## Temporal-memory mechanisms

Gamma/repeated-pole memory, Laplace temporal representations, HiPPO, retention and delta-rule memories are established work. [The supplied research record](docs/research/2026-10-13-source-record.md) and [baseline adaptation ledger](docs/baseline_adaptations.md) identify the papers, equations, inspected revisions and deviations. Attribution is retained for these mechanisms; FAM-Jet does not claim to invent a new category of function-valued memory.

- **HiPPO Zoo:** Goffinet, Hanks and Carlson; inspected source at `04e38b3cf246f4c50cb6c6a7e10597e2e37eebc7`, MIT, copyright 2026 Jack Goffinet. The local polynomial/multiscale/associative implementations are independently written equation-based adaptations. No upstream source is vendored. Any future copied substantial source must retain its MIT notice.
- **Gated DeltaNet-2:** the inspected NVIDIA source uses **NVIDIA Source Code License-NC**, not a permissive source license. No NVIDIA source, fused Triton/FLA kernel or pretrained weight is vendored or granted rights by this repository. The native tensor recurrence is independently implemented from the published equations; the original source restrictions remain attached to that external source.
- **Time-Local Transformer / Gaver:** the inspected external code had no established reuse license. No external cell source is copied. The local Gaver implementation is an equation-based impulse adaptation with separately recorded input and precision semantics.

Component implementations and tests are distinct from a completed all-family scientific comparison. See the ledger for exact limitations and source links.

## Runtime dependencies

NumPy, SciPy and PyTorch retain their BSD-family terms; PyYAML and pytest retain their MIT terms; other locked dependencies retain their package notices. They are installed separately from [requirements.lock](requirements.lock), not vendored here. Matplotlib and its dependencies retain their terms in the separate [reporting lock](docs/reporting-requirements.lock). License documents retain their own copying permissions.

Original software and writing licensing is defined in [LICENSING.md](LICENSING.md). Citation of a paper or inspection of a repository is not a grant of rights in its source code.
