"""Render the one registered run06 report recovery from sealed artifacts."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
import traceback

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from famjet.provenance import canonical_json
from famjet_poc.report_inputs import load_report_inputs
from famjet_poc import report


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _files(directory):
    return {str(path.relative_to(directory)): {'sha256': _sha(path), 'bytes': path.stat().st_size}
            for path in sorted(directory.rglob('*')) if path.is_file() and
            path.name != 'recovery-receipt.json'}


def _destination(requested):
    requested = Path(requested)
    if not requested.parent.exists():
        return requested
    if not (requested.parent / 'recovery-receipt.json').is_file():
        raise ValueError('report output directory already exists without a recovery receipt')
    number = 2
    while True:
        replay = requested.parent.with_name(requested.parent.name + f'-replay-{number:03d}')
        if not replay.exists():
            return replay / requested.name
        number += 1


def _render(run, out, archive):
    inputs = load_report_inputs(run, compatibility_id='run06-report-order-v1',
                                archived_source=archive)
    if inputs['status'] != 'scientific_artifacts_validated':
        raise ValueError('registered recovery requires the scientific run06')
    plot = report._render_plots(report._science_chart_data(inputs), out)
    machine = report._science_machine(inputs, plot)
    provenance = inputs['report_recovery']
    machine['report_recovery'] = provenance
    machine['report_recovery']['status'] = 'audited_report_only_recovery'
    machine['report_recovery']['description'] = (
        'sealed scientific run completed; initial report failed; audited report-only recovery completed')
    markdown = ('# Run06 report recovery\n\n'
                '**Status:** sealed scientific run completed; initial report failed; '
                'audited report-only recovery completed.\n\n'
                f"Execution executable SHA-256: `{provenance['execution_sha256']}`.  \n"
                f"Reporter executable SHA-256: `{provenance['reporter_sha256']}`.  \n"
                f"Migration manifest SHA-256: `{provenance['manifest_sha256']}`.  \n"
                f"Recovery launcher SHA-256: `{provenance['launcher_sha256']}`.  \n"
                f"Original exit: {provenance['original_exit_code']}; report "
                f"{provenance['original_report_status']}: "
                f"`{provenance['original_report_error']}`.\n\n"
                'The reproduction commands below describe fresh runs under the corrected reporter; '
                'this historical run requires the registered recovery launcher.\n\n'
                + report._science_markdown(machine))
    report._write(out.with_suffix('.json'), canonical_json(machine))
    report._write(out, markdown.encode('utf-8'))
    return provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path, metavar='RUNROOT')
    parser.add_argument('--out', required=True, type=Path, metavar='MARKDOWN')
    parser.add_argument('--archived-source', required=True, type=Path, metavar='DIR')
    parser.add_argument('--compatibility-id', required=True,
                        choices=('run06-report-order-v1',))
    args = parser.parse_args(argv)
    run = args.run.resolve(strict=True)
    archive = args.archived_source.resolve(strict=True)
    requested = args.out.resolve()
    if requested.parent.is_relative_to(run) or requested.parent.is_relative_to(archive):
        raise ValueError('report output must be a new sibling directory outside sealed inputs')
    target = _destination(requested)
    target.parent.parent.mkdir(parents=True, exist_ok=True)
    attempt_number = 1
    while True:
        attempt = target.parent.with_name(target.parent.name + f'-attempt-{attempt_number:03d}')
        if not attempt.exists():
            attempt.mkdir()
            break
        attempt_number += 1
    started_utc = _utc()
    started = time.perf_counter()
    receipt = {'schema_version': 1, 'kind': 'famjet_run06_report_recovery_receipt',
               'compatibility_id': args.compatibility_id,
               'invocation': {'run': str(run), 'requested_out': str(requested),
                              'published_out': str(target), 'archived_source': str(archive)},
               'started_utc': started_utc, 'reporter_git_revision': None,
               'status': 'failed'}
    try:
        import subprocess
        receipt['reporter_git_revision'] = subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=_ROOT, check=True,
            capture_output=True, text=True).stdout.strip()
        provenance = _render(run, attempt / target.name, archive)
        receipt.update(provenance)
        receipt['output_files'] = _files(attempt)
        receipt['status'] = 'completed'
    except BaseException as error:
        receipt['error'] = f'{type(error).__name__}: {error}'
        receipt['traceback'] = traceback.format_exc()
        raise
    finally:
        receipt['ended_utc'] = _utc()
        receipt['elapsed_seconds'] = time.perf_counter() - started
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        receipt['maximum_rss_bytes'] = rss if sys.platform == 'darwin' else rss * 1024
        (attempt / 'recovery-receipt.json').write_bytes(canonical_json(receipt))
        if receipt['status'] == 'completed':
            os.replace(attempt, target.parent)
    print(canonical_json({'path': str(target), 'sha256': _sha(target),
                          'receipt': str(target.parent / 'recovery-receipt.json')}).decode(), end='')


if __name__ == '__main__':
    main()
