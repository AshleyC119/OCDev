"""Development-only: freeze the implementation identity (FROZEN.json).

Hashes every deliverable source/document file (except FROZEN.json itself) plus
records the input material hashes and the development validation summary.
"""
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'FROZEN.json')
INCLUDE_ROOTS = ['oc2h3c', 'tests', 'tools', 'docs']
INCLUDE_FILES = ['README.md', 'PROMPT.md', 'AGENTS.md']


def sha256(path):
    with open(path, 'rb') as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def collect():
    files = {}
    for item in INCLUDE_FILES:
        path = os.path.join(ROOT, item)
        if os.path.isfile(path):
            files[item] = {'sha256': sha256(path), 'bytes': os.path.getsize(path)}
    for root in INCLUDE_ROOTS:
        for base, dirs, names in os.walk(os.path.join(ROOT, root)):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for name in sorted(names):
                if name.endswith('.pyc'):
                    continue
                path = os.path.join(base, name)
                rel = os.path.relpath(path, ROOT).replace('\\', '/')
                files[rel] = {'sha256': sha256(path), 'bytes': os.path.getsize(path)}
    return dict(sorted(files.items()))


def validate_summary():
    sys.path.insert(0, ROOT)
    from oc2h3c.loader import load_document
    from oc2h3c.pipeline import translate, render_groups
    from oc2h3c.report import Report
    oc = os.path.join(ROOT, 'data', 'raw', 'CQ-JLDC-2201-A03-H9867-GPULA-024.txt')
    ref = os.path.join(ROOT, 'data', 'raw', '配置文本_CQ-JLDC-2201-A03-H9867-GPULA-024.txt')
    doc, info = load_document(oc)
    report = Report()
    ctx = translate(doc, report)
    cli = render_groups(ctx)
    ctx.finalize_coverage()
    data = report.to_dict(info, cli, 'sampleB.cli')
    ref_lines = open(ref, encoding='utf-8').read().splitlines()

    def segments(lines):
        out, cur = [], []
        for line in lines:
            if line.strip() == 'return':
                if cur:
                    out.append(cur)
                cur = []
            elif line.strip():
                cur.append(line)
        if cur:
            out.append(cur)
        return out
    gen_lines = cli.splitlines()
    gen_segments = segments(gen_lines)
    ref_segments = segments(ref_lines)
    identical = sum(1 for gen, expected in zip(gen_segments, ref_segments) if gen == expected)
    python = 'Python %s' % platform.python_version()
    return {
        'input_sha256': info['sha256'],
        'input_bytes': info['bytes'],
        'output_cli_lines': len(gen_lines),
        'output_cli_sha256': data['output']['cli_sha256'],
        'reference_cli_lines': len(ref_lines),
        'segments': len(ref_segments),
        'segments_byte_identical': identical,
        'known_difference': 'segment 10: reference emits fixed qos map-table dot1p-lp '
                            'default entries with no OC source; deliberately not reproduced',
        'coverage': {k: v for k, v in data['coverage'].items() if k != 'missing'},
        'diagnostics': data['summary'],
        'runtime': {'python': python, 'third_party_dependencies': [],
                    'offline': True, 'deterministic': True,
                    'reads_reference_cli_at_runtime': False},
    }


def main():
    with open(os.path.join(ROOT, 'data', 'manifest.json'), encoding='utf-8') as handle:
        manifest = json.load(handle)
    frozen = {
        'schema_version': 1,
        'implementation': {'name': 'oc2h3c', 'version': '1.0.0'},
        'frozen_on': '2026-10-27',
        'frozen_time_zone': 'Asia/Shanghai',
        'usage': 'python -m oc2h3c <oc.json> -o <out.cli> --report <report.json> '
                 '--report-text <report.txt>',
        'input_materials': [
            {'side': item['side'], 'path': item['path'], 'sha256': item['sha256'],
             'bytes': item['bytes']} for item in manifest['files']],
        'reference_command_manual': manifest['primary_command_reference'],
        'development_validation': validate_summary(),
        'files': collect(),
        'notes': [
            'FROZEN.json itself is not hashed.',
            'Any change under oc2h3c/, tests/, tools/, docs/ or the listed top-level '
            'documents invalidates this identity; bump the version and re-freeze.',
            'The paired native CLI reference and the command manual are development '
            'materials; the translator never reads them at runtime.',
        ],
    }
    with open(OUT, 'w', encoding='utf-8', newline='\n') as handle:
        json.dump(frozen, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print('wrote', OUT, 'with', len(frozen['files']), 'hashed files')


if __name__ == '__main__':
    main()
