"""Development-only validation harness.

Compares the translator output for the development sample with the paired native
CLI reference, both byte-exact and whitespace-normalised.  This tool is NOT used
by the translator at runtime; it only measures development fidelity.

Usage:
    python tools/compare.py [--generated PATH] [--reference PATH] [--limit N] [--show N]
"""
import argparse
import difflib
import hashlib
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OC = os.path.join(ROOT, 'data', 'raw', 'CQ-JLDC-2201-A03-H9867-GPULA-024.txt')
REF = os.path.join(ROOT, 'data', 'raw', '配置文本_CQ-JLDC-2201-A03-H9867-GPULA-024.txt')
GEN = os.path.join(ROOT, 'outputs', 'sampleB.cli')


def normalise(line):
    return re.sub(r'\s+', ' ', line.strip())


def run_translator(out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmd = [sys.executable, '-m', 'oc2h3c', OC, '-o', out, '--quiet']
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        raise SystemExit('translator failed with %d' % res.returncode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--generated', default=GEN)
    ap.add_argument('--reference', default=REF)
    ap.add_argument('--limit', type=int, default=25, help='show at most N differences')
    ap.add_argument('--show', type=int, default=6, help='context lines per difference')
    ap.add_argument('--no-run', action='store_true')
    a = ap.parse_args()
    if not a.no_run:
        run_translator(a.generated)
    gen = open(a.generated, encoding='utf-8').read().splitlines()
    ref = open(a.reference, encoding='utf-8').read().splitlines()
    print('generated lines %d  sha256 %s' % (len(gen), hashlib.sha256(
        open(a.generated, 'rb').read()).hexdigest()[:16]))
    print('reference lines %d  sha256 %s' % (len(ref), hashlib.sha256(
        open(a.reference, 'rb').read()).hexdigest()[:16]))
    exact = gen == ref
    print('byte-identical:', exact)

    ng = [normalise(x) for x in gen]
    nr = [normalise(x) for x in ref]
    print('normalised identical:', ng == nr)

    sm = difflib.SequenceMatcher(None, ng, nr, autojunk=False)
    shown = 0
    added = removed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if tag == 'replace':
            removed += i2 - i1
            added += j2 - j1
        elif tag == 'delete':
            removed += i2 - i1
        elif tag == 'insert':
            added += j2 - j1
        if shown < a.limit:
            print('\n--- %s generated[%d:%d] reference[%d:%d]' % (tag, i1, i2, j1, j2))
            for x in gen[i1:i2][:a.show]:
                print('  GEN - %r' % x)
            if i2 - i1 > a.show:
                print('  GEN ... %d more' % (i2 - i1 - a.show))
            for x in ref[j1:j2][:a.show]:
                print('  REF + %r' % x)
            if j2 - j1 > a.show:
                print('  REF ... %d more' % (j2 - j1 - a.show))
            shown += 1
    print('\nmissing lines (in reference only): %d' % added)
    print('extra lines (generated only): %d' % removed)
    print('difference blocks: %d' % sum(1 for t, *_ in sm.get_opcodes() if t != 'equal'))
    return 0 if exact else 1


if __name__ == '__main__':
    sys.exit(main())
