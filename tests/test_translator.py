"""Regression and development-fidelity tests for the oc2h3c translator.

The fidelity test reads the paired native CLI reference.  It is a development
check only; the translator itself never opens that file (enforced by another
test below).
"""
import difflib
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OC = os.path.join(ROOT, 'data', 'raw', 'CQ-JLDC-2201-A03-H9867-GPULA-024.txt')
REF = os.path.join(ROOT, 'data', 'raw', '配置文本_CQ-JLDC-2201-A03-H9867-GPULA-024.txt')
MANIFEST = os.path.join(ROOT, 'data', 'manifest.json')

sys.path.insert(0, ROOT)
from oc2h3c.loader import load_document                  # noqa: E402
from oc2h3c.pipeline import translate, render_groups     # noqa: E402
from oc2h3c.report import Report                         # noqa: E402

#: The only reference lines that are not reproducible from the OC document:
#: a fixed default dot1p->local-priority table with no OC source.
KNOWN_UNREPRODUCIBLE = {
    'qos map-table dot1p-lp',
    'import 0 export 0',
    'import 1 export 1',
    'import 2 export 2',
}


def read_lines(path):
    with open(path, encoding='utf-8') as handle:
        return handle.read().splitlines()


def translate_path(path):
    doc, info = load_document(path)
    report = Report()
    ctx = translate(doc, report)
    cli = render_groups(ctx)
    ctx.finalize_coverage()
    return cli, report, info


def normalise(lines):
    return [re.sub(r'\s+', ' ', line.strip()) for line in lines]


class TranslatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cli, cls.report, cls.info = translate_path(OC)
        cls.report_dict = cls.report.to_dict(cls.info, cls.cli, 'sampleB.cli')

    def test_input_identity(self):
        self.assertEqual(
            self.info['sha256'],
            'b60b07a2af299ad1e06a94791813df6cc66d63d0d12e4eb0b1eeb841bbd1f430')

    def test_raw_materials_unchanged(self):
        import hashlib
        import json
        with open(MANIFEST, encoding='utf-8') as handle:
            manifest = json.load(handle)
        for item in manifest['files']:
            path = os.path.join(ROOT, item['path'])
            with open(path, 'rb') as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            self.assertEqual(digest, item['sha256'], item['path'])

    def test_deterministic(self):
        again, _report, _info = translate_path(OC)
        self.assertEqual(again, self.cli)

    def test_runtime_does_not_read_reference(self):
        reference = os.path.basename(REF)
        offenders = []
        for base, _dirs, files in os.walk(os.path.join(ROOT, 'oc2h3c')):
            for name in files:
                if not name.endswith('.py'):
                    continue
                path = os.path.join(base, name)
                with open(path, encoding='utf-8') as handle:
                    text = handle.read()
                if reference in text or '配置文本' in text:
                    offenders.append(path)
        self.assertEqual(offenders, [])

    def test_no_network_or_model_imports(self):
        banned = re.compile(
            r'^\s*(?:import|from)\s+'
            r'(?:requests|urllib|socket|http|openai|anthropic|transformers)\b',
            re.MULTILINE)
        offenders = []
        for base, _dirs, files in os.walk(os.path.join(ROOT, 'oc2h3c')):
            for name in files:
                if not name.endswith('.py'):
                    continue
                path = os.path.join(base, name)
                with open(path, encoding='utf-8') as handle:
                    text = handle.read()
                if banned.search(text):
                    offenders.append(path)
        self.assertEqual(offenders, [])

    def test_development_fidelity(self):
        """Everything except the known fixed dot1p-lp table is reproduced exactly."""
        gen = self.cli.splitlines()
        ref = read_lines(REF)
        matcher = difflib.SequenceMatcher(None, normalise(gen), normalise(ref),
                                          autojunk=False)
        differences = [(tag, i1, i2, j1, j2)
                       for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != 'equal']
        self.assertEqual(len(differences), 1, differences)
        tag, i1, i2, j1, j2 = differences[0]
        self.assertEqual(tag, 'insert')
        inserted = set(normalise(ref[j1:j2]))
        self.assertEqual(inserted, KNOWN_UNREPRODUCIBLE)
        self.assertEqual(i1, i2)

    def test_segment_count_matches_development_reference(self):
        gen = self.cli.splitlines()
        ref = read_lines(REF)
        self.assertEqual(sum(1 for line in gen if line == 'system-view'),
                         sum(1 for line in ref if line == 'system-view'))

    def test_report_structure(self):
        data = self.report_dict
        self.assertEqual(data['translator']['name'], 'oc2h3c')
        for key in ('input', 'output', 'summary', 'coverage', 'diagnostics', 'notes'):
            self.assertIn(key, data)
        self.assertGreater(data['coverage']['data_leaves'], 0)
        self.assertGreaterEqual(data['coverage']['mapped_leaves'], 1)
        for kind in ('unsupported', 'ambiguous', 'ignored', 'error'):
            self.assertIn(kind, data['diagnostics'])

    def test_known_cli_fragments(self):
        self.assertIn('sysname CQ-JLDC-2201-A03-H9867-GPULA-024', self.cli)
        self.assertIn('route-distinguisher 2:1', self.cli)
        self.assertIn('priority-flow-control deadlock precision high', self.cli)
        self.assertIn('buffer threshold alarm headroom interval 30', self.cli)

    def test_empty_document(self):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                         encoding='utf-8') as handle:
            handle.write('{}')
            path = handle.name
        try:
            cli, report, info = translate_path(path)
        finally:
            os.unlink(path)
        self.assertTrue(cli.startswith('return\n'))
        data = report.to_dict(info, cli, '<tmp>')
        self.assertEqual(data['coverage']['unmapped_content_leaves'], 0)

    def test_invalid_json_is_rejected(self):
        out = os.path.join(tempfile.gettempdir(), 'oc2h3c-bad.cli')
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                         encoding='utf-8') as handle:
            handle.write('{not json')
            path = handle.name
        try:
            res = subprocess.run([sys.executable, '-m', 'oc2h3c', path, '-o', out],
                                 cwd=ROOT, capture_output=True, text=True)
        finally:
            os.unlink(path)
            if os.path.exists(out):
                os.unlink(out)
        self.assertEqual(res.returncode, 2)
        self.assertIn('input error', res.stderr)

    def test_partial_sections_do_not_crash(self):
        """Re-translate with several sections removed: must not raise."""
        import copy
        import json
        with open(OC, encoding='utf-8') as handle:
            raw = json.load(handle)
        variants = []
        for key in ('qos', 'system', 'interfaces', 'components', 'lacp', 'bgp'):
            variant = copy.deepcopy(raw)
            variant.pop(key, None)
            variants.append(variant)
        for variant in variants:
            with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                             encoding='utf-8') as handle:
                json.dump(variant, handle)
                path = handle.name
            try:
                cli, report, _info = translate_path(path)
                self.assertIn('system-view', cli)
                summary = report.to_dict(_info, cli, 'x')['summary']
                # Removing a section can legitimately surface "referenced data
                # missing" diagnostics; it must never crash or explode.
                self.assertLessEqual(summary['errors'], 10, summary)
            finally:
                os.unlink(path)


if __name__ == '__main__':
    unittest.main()
