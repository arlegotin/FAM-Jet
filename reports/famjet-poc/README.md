# FAM-Jet run06 report bundle

The [human report](final.md), [machine report](final.json), [chart data](final-chart-data.json) and [charts](final-charts/primary-effect.svg) are the canonical, byte-verified outputs of the **separate run06 report-only recovery**. The [actual recovery and portable replay proof](../../docs/research/e2e-report-recovery-actual/index.json) records hashes for all seven deterministic files. The adjacent `recovery-receipt.json` carries invocation metadata and is not part of that byte-identical comparison.

**Result:** Jet superiority was not demonstrated. Confirmation and independent replication Bank-minus-Jet point estimates favor Jet slightly, but both intervals cross zero. Buckets has lower average synthetic loss than both; finite-period Beijing transfer is mixed. See [README](../../README.md) for a short result table and [AUDIT](../../AUDIT.md) for the attempt ledger and limits.

The original run06 completed all scientific stages but its normal CLI exited **1** at report assembly. The first lines of `final.md` retain that failure and bind the original execution identity to the corrected reporter identity. Its embedded generic `famjet_poc run` commands describe a **fresh execution**, not the historical report recovery. A fresh `--out` repeats the same registered seeds and populations; it is not an independent new confirmation.

To reproduce this historical report, use **CPython 3.13.5 exactly** on macOS 14+ arm64, the main and separate plotting hash locks described in the repository [README](../../README.md#install-prepare-and-replay), the complete ignored run at `artifacts/e2e-core-run-06`, and the [archived original source](../../docs/research/e2e-run06-execution-source/):

```sh
FAMJET_REPORT_PYTHON=.report-venv/bin/python .venv/bin/python scripts/report_run06_recovery.py --run artifacts/e2e-core-run-06 --out artifacts/e2e-run06-replay-new/final.md --archived-source docs/research/e2e-run06-execution-source --compatibility-id run06-report-order-v1
```

Use a new empty sibling output directory for each replay. The complete local Git-ignored bundle `artifacts/e2e-run06-sealed-bundle.tar.gz` is **285,608,419 B**, SHA-256 `b6de6ba91c234a30bf885f5695b26244358749597bd9f043621f1a44bbd624ae`; [bundle receipt](../../docs/research/e2e-run06-execution-record/bundle-receipt.json). Committed reports and hashes do not include that bulk data. The tested portable replay made the original run, prep and tracked source locations unavailable, rendered from copied inputs, and restored them afterward.
