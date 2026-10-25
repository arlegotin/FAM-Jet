# Interactive RED and setup failures

These attempts were run in the tool transcript before capture logging was installed. The commands, exit codes and observed failure causes below are retained; exact UTC, elapsed time, complete raw bytes and log hashes were not captured at invocation and are intentionally left unclaimed. The later raw GREEN receipts are in `commands-source-final.json`.

| Attempt | Command | Exit | Observed failure |
| --- | --- | ---: | --- |
| Setup 1 | `python -m pytest tests/test_measured_execution.py -q` | 1 | Wrong environment: no `pytest` module. |
| Setup 2 | `pytest tests/test_measured_execution.py -q` | 2 | Wrong Python/path: `famjet_poc` unavailable. |
| RED 1 | `.venv/bin/python -m pytest tests/test_measured_execution.py -q` | 2 | New `famjet_poc.execution_policy` absent. |
| RED 2 | `.venv/bin/python -m pytest tests/test_measured_execution.py -q` | 1 | `StageLedger.stage` did not accept scientific policy admission. |
| RED 3 | `.venv/bin/python -m pytest tests/test_poc_protected.py::test_scientific_plan_rejects_changed_protected_root_before_grant -q` | 1 | Old unprefixed protected IDs were accepted. |
| RED 4 | `.venv/bin/python -m pytest tests/test_guard_cadence_public_check.py -q` | 1 | Driver file absent; three tests failed. |
| Fixture correction 1 | `.venv/bin/python -m pytest tests/test_guard_cadence_public_check.py -q` | 1 | Projection fixture omitted required scientific fields. |
| Fixture correction 2 | `.venv/bin/python -m pytest tests/test_measured_execution.py -q` | 1 | Disk violation fixture used 1,001 bytes against a 1,000,000-byte cap. |
| RED 5 | `.venv/bin/python -m pytest tests/test_measured_execution.py::test_background_interval_observes_even_with_fresh_foreground_cache tests/test_measured_execution.py::test_background_deadline_cancels_only_currently_verified_owned_child -q` | 1 | Background reused a fresh sample instead of observing on each interval. |
| RED 6 | `.venv/bin/python -m pytest tests/test_measured_execution.py::test_policy_rejects_bool_and_float_coercion_of_declared_integer_fields -q` | 1 | Boolean schema version compared equal to integer 1. |
| RED 7 | `.venv/bin/python -m pytest tests/test_measured_execution.py::test_dated_policy_is_strict_and_reserve_blocks_scientific_admission -q` | 1 | Float run-policy ceiling compared equal to integer 28,800. |
| RED 8 | `.venv/bin/python -m pytest tests/test_measured_execution.py::test_run_policy_anchor_rejects_consistent_original_clock_rewrite -q` | 4 | New anchor binding function absent. |
| Fixture correction 3 | `.venv/bin/python -m pytest tests/test_measured_execution.py::test_run_policy_anchor_rejects_consistent_original_clock_rewrite -q` | 1 | Float-type fixture lines were accidentally placed in the anchor test (`NameError`). |
| Read-only public diagnostic | Python here-document below | 1 | Archived selected Jet/Bank rows use exact selected configuration hashes as method labels. No new evaluation ran. |
| RED 9 | `.venv/bin/python -m pytest tests/test_guard_cadence_public_check.py::test_projection_requires_complete_exact_scientific_rows -q` | 1 | Projection comparator lacked the bound old source-method label. |

The read-only diagnostic command was:

```sh
.venv/bin/python - <<'PY'
import importlib.util
from pathlib import Path
p=Path('docs/research/e2e-guard-cadence-public-check.py');s=importlib.util.spec_from_file_location('public_guard',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
_,_,_,ids,_,rows,_=m._old_public_sources(m.DEFAULT_PUBLIC_ROOT)
print({method:m.compare_scientific_rows(items,items,ids,method)['row_count'] for method,items in rows.items()})
PY
```

The last four captured affected-suite invocations ended at 122, 123, 124, and 124 passing tests as recorded by their raw evidence files. No failure was hidden or used to weaken a scientific acceptance condition.
