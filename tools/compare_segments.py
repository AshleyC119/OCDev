"""Development-only: compare selected reference CLI segments with generated output.

Each segment is the text of one ``system-view`` block in the native reference
transcript (segments are separated by ``return`` lines).  This lets independent
mapping work items verify one feature area without waiting for the rest of the
pipeline.

Usage:
    python tools/compare_segments.py 398-405
    python tools/compare_segments.py 600 601 603
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OC = os.path.join(ROOT, 'data', 'raw', 'CQ-JLDC-2201-A03-H9867-GPULA-024.txt')
REF = os.path.join(ROOT, 'data', 'raw', '配置文本_CQ-JLDC-2201-A03-H9867-GPULA-024.txt')
GEN = os.path.join(ROOT, 'outputs', 'sampleB.cli')


def split_segments(lines):
    out, cur = [], []
    for raw in lines:
        text = raw.rstrip('\n')
        if text.strip() == 'return':
            if cur:
                out.append(cur)
            cur = []
        elif text.strip() == '':
            continue
        else:
            cur.append(text)
    if cur:
        out.append(cur)
    return out


def parse_ranges(args):
    wanted = []
    for token in args:
        if '-' in token:
            lo, hi = token.split('-', 1)
            wanted.extend(range(int(lo), int(hi) + 1))
        else:
            wanted.append(int(token))
    return wanted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ranges', nargs='+')
    ap.add_argument('--no-run', action='store_true')
    ap.add_argument('--raw', action='store_true', help='compare bytes, not normalised text')
    a = ap.parse_args()
    if not a.no_run:
        res = subprocess.run([sys.executable, '-m', 'oc2h3c', OC, '-o', GEN, '--quiet'],
                             cwd=ROOT, capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stderr)
            raise SystemExit('translator failed')
    gen = split_segments(open(GEN, encoding='utf-8').read().splitlines())
    ref = split_segments(open(REF, encoding='utf-8').read().splitlines())
    if len(gen) != len(ref):
        print('WARNING: group count differs: generated %d reference %d' % (len(gen), len(ref)))
    wanted = [i for i in parse_ranges(a.ranges) if 1 <= i <= len(ref)]
    ok = 0
    for idx in wanted:
        g = gen[idx - 1] if idx - 1 < len(gen) else ['<missing segment>']
        r = ref[idx - 1]
        if a.raw:
            same = g == r
        else:
            same = [re.sub(r'\s+', ' ', x.strip()) for x in g] == \
                   [re.sub(r'\s+', ' ', x.strip()) for x in r]
        if same:
            ok += 1
            continue
        print('\n=== segment %d differs%s (generated %d lines, reference %d lines)'
              % (idx, '' if a.raw else ' (normalised)', len(g), len(r)))
        import difflib
        for line in difflib.unified_diff(r, g, fromfile='ref', tofile='gen', lineterm='', n=1):
            print(line)
    print('\nsegments checked: %d, identical: %d, differing: %d'
          % (len(wanted), ok, len(wanted) - ok))
    return 0 if ok == len(wanted) else 1


if __name__ == '__main__':
    sys.exit(main())
