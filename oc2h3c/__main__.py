"""Command-line entry point: python -m oc2h3c."""
import argparse
import os
import sys

from . import __version__
from .errors import InputError
from .loader import load_document
from .pipeline import translate, render_groups
from .report import Report


def build_parser():
    parser = argparse.ArgumentParser(
        prog='oc2h3c',
        description='Deterministic offline OpenConfig -> H3C CLI translator.')
    parser.add_argument('input', help='complete OC JSON document (single JSON object)')
    parser.add_argument('-o', '--output', help='write generated CLI to this file (default: stdout)')
    parser.add_argument('--report', help='write the structured JSON report to this file')
    parser.add_argument('--report-text', help='write the human-readable report to this file')
    parser.add_argument('--quiet', action='store_true', help='do not print the summary to stderr')
    parser.add_argument('--version', action='version', version='oc2h3c ' + __version__)
    return parser


def _write(path, text):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)


def main(argv=None):
    args = build_parser().parse_args(argv)
    report = Report()
    try:
        doc, input_info = load_document(args.input)
    except InputError as exc:
        sys.stderr.write('oc2h3c: input error: %s\n' % exc)
        return 2

    ctx = translate(doc, report)
    cli = render_groups(ctx)
    ctx.finalize_coverage()

    output_name = args.output or '<stdout>'
    if args.output:
        _write(args.output, cli)
    else:
        sys.stdout.write(cli)

    if args.report:
        _write(args.report, report.render_json(input_info, cli, output_name))
    if args.report_text:
        _write(args.report_text, report.render_text(input_info, cli, output_name))

    if not args.quiet:
        summary = report.to_dict(input_info, cli, output_name)
        counts = summary['summary']
        cov = summary.get('coverage') or {}
        sys.stderr.write(
            'oc2h3c: wrote %d CLI lines; data leaves mapped %d/%d, redundant metadata %d, '
            'unmapped content %d; unsupported=%d ambiguous=%d ignored=%d unmapped=%d errors=%d\n'
            % (summary['output']['cli_lines'], cov.get('mapped_leaves', 0),
               cov.get('data_leaves', 0), cov.get('redundant_metadata_leaves', 0),
               cov.get('unmapped_content_leaves', 0),
               counts['unsupported'], counts['ambiguous'], counts['ignored'],
               counts['unmapped'], counts['errors']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
