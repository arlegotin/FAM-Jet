"""Plot export is byte-stable and isolated from the model interpreter."""

import hashlib
import json
from pathlib import Path
import subprocess


REPORT_PYTHON = Path('/private/tmp/famjet-report-20261024-01/bin/python')


def test_chart_export_is_deterministic_from_frozen_json(tmp_path):
    assert REPORT_PYTHON.is_file()
    data = {'schema_version': 1, 'kind': 'famjet_e5_chart_data',
            'methods': [
                {'name': 'jet', 'loss': 0.3, 'state_bytes': 9345,
                 'static_bytes': 1000, 'query_seconds': 0.2},
                {'name': 'bank', 'loss': 0.2, 'state_bytes': 9345,
                 'static_bytes': 1100, 'query_seconds': 0.3}],
            'effects': [
                {'panel': 'confirmation', 'estimate': -0.1, 'lower': -0.2, 'upper': 0.0},
                {'panel': 'replication', 'estimate': -0.05, 'lower': -0.15, 'upper': 0.05}]}
    source = tmp_path / 'chart.json'
    source.write_text(json.dumps(data))
    script = Path(__file__).resolve().parents[1] / 'famjet_poc' / 'plots.py'
    receipts = []
    for name in ('first', 'second'):
        out = tmp_path / name
        result = subprocess.run([str(REPORT_PYTHON), str(script), '--data', str(source),
                                 '--out', str(out)], capture_output=True, text=True,
                                timeout=60)
        assert result.returncode == 0, result.stderr
        assert 'torch' not in result.stdout.lower()
        receipt = json.loads((out / 'plots-receipt.json').read_text())
        assert receipt['data_sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
        assert receipt['locked_packages']['matplotlib'] == '3.11.2'
        assert receipt['locked_packages']['numpy'] == '2.5.4'
        assert set(receipt['outputs']) == {'accuracy-memory.svg', 'cost.svg', 'primary-effect.svg'}
        receipts.append({file: hashlib.sha256((out / file).read_bytes()).hexdigest()
                         for file in receipt['outputs']})
    assert receipts[0] == receipts[1]
