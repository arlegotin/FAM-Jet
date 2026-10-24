# HOLD: public coordinate preflight

Prepared only. Do not execute until root accepts the reviewed comparator source and commits a clean exact HEAD. No scientific import, model execution, fit, test, Git operation, or tracked-file write is part of this preparation.

The standalone script scans the original development manifest's exact ordered 192 public histories with the same selected Jet `78d5f023…`. It pins original manifest/journal/model/NPZ/cache-manifest bytes and checks every old episode JSON's recorded bytes, SHA and E1 episode digest. A local external diagnostic decoder restores those public JSON records; it does not call, bypass, patch, or adopt into the new E3 cache loader. It verifies unchanged E1 `f787…` and records current reviewed E3/source identities separately from old E3 provenance. No new study or primary-score artifact is written.

Runtime dependency: accepted API `laguerre_control(model, events, queries, diagnostic_mode=True)`, returned `coordinate_diagnostics[history]`, and `coordinate_model_sha256`/`COORDINATE_POLICY`, plus existing `.venv`, unchanged E1 model loader and episode/tensor schema. Review this API against accepted source before execution; API drift is a failed preflight, never permission to shim acceptance.

Root supplies a fresh output path with an existing parent and the full reviewed HEAD SHA. Example, from repository root:

```
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .superpowers/sdd/2026-10-16-famjet/e2e-coordinate-public-preflight.py --out artifacts/ROOT_CHOSEN_FRESH_PUBLIC_PREFLIGHT --expected-head FULL_REVIEWED_40_HEX_COMMIT
```

Run under the independent root witness with fresh OUT/PREP, total original-wall limit 300 seconds, process peak RSS limit 1.5 GiB, total output 32 MiB. The script fixes OMP/MKL/OPENBLAS/VECLIB thread variables before imports, uses one CPU scientific process, sets its own original-clock 270-second alarm, and checks observed peak RSS/output between histories. The external witness remains authoritative for resources between those checks and before admission. Git read-only identity checks occur at runtime; no Git write occurs.

Each completed history produces one compact chronological JSONL diagnostic: immutable input SHA, event count, exact query IDs, counts, all original strict prediction flags, state/mask results, numerical maxima, duration. Strict prediction failures remain FAILED and do not stop this amended diagnostic. On the first substantive state/mask ArithmeticError it records traceback and bounded frame-local state/mask summaries, stops immediately, and exits nonzero. No neighbor is run after a hard failure; this conservative policy avoids extending a failed qualification. Other errors/timeouts are incomplete, never passes. No full features/state arrays are dumped.

On full completion, byte rechecks bind all inputs and tracked Python source, and a fresh HEAD/clean-tree check (including untracked nonignored files) binds the reviewed code. Runtime outputs must be in an ignored artifact location. Exit 0 means only that all 192 public state/mask checks completed; result.json separately retains aggregate strict prediction FAILED/PASSED. It does not qualify all later real histories, authorize protected access, alter resource allocations, or establish source-transition/adoption of old public artifacts.
