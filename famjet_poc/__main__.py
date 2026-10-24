"""Runnable public entry point for the frozen PoC."""

import argparse
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m famjet_poc',
                                     description='Run or replay the fixed-writer memory study.')
    commands = parser.add_subparsers(dest='command', required=True)
    run_parser = commands.add_parser('run', help='execute the accepted complete pipeline')
    run_parser.add_argument('--out', type=Path, required=True, metavar='RUNROOT')
    run_parser.add_argument('--resume', action='store_true')
    report_parser = commands.add_parser('report', help='rebuild the report from frozen artifacts')
    report_parser.add_argument('--run', type=Path, required=True, metavar='RUNROOT')
    report_parser.add_argument('--out', type=Path, required=True, metavar='MARKDOWN')
    arguments = parser.parse_args(argv)
    if arguments.command == 'run':
        from .pipeline import run
        result = run(arguments.out, resume=arguments.resume)
        if result is None:
            raise RuntimeError('pipeline returned no completed run root')
        print(result)
        return result
    from .report import render_report
    result = render_report(arguments.run, arguments.out)
    if result is None:
        raise RuntimeError('report returned no content reference')
    print(result)
    return result


if __name__ == '__main__':
    main()
