"""Structured translation report: unsupported, ambiguous, erroneous input."""
import collections
import hashlib
import json
import re

from .context import path_text
from . import __version__

LEAF_KINDS = ('unsupported', 'ambiguous', 'ignored', 'error', 'unmapped')


def _mask(parts):
    """Build a stable template for a path so repeated instance errors aggregate."""
    out = []
    for part in parts:
        text = str(part)
        if re.fullmatch(r'\d+', text) or re.fullmatch(r'\d+(?:\.\d+){0,3}', text) \
                or re.fullmatch(r'[A-Za-z][\w-]*\d[\w:/.-]*', text) or re.fullmatch(r'\d+:\d+', text) \
                or '/' in text or '.' in text and re.search(r'\d', text):
            out.append('*')
        else:
            out.append(text)
    return '/'.join(out)


class Report:
    def __init__(self):
        self.entries = []
        self.notes = []
        self.coverage_info = None
        self.metadata = {}
        self.fatal = None

    # ---------------------------------------------------------------- entries
    def _add(self, kind, parts, message, occurrences=1, **extra):
        entry = {
            'kind': kind,
            'path': path_text(parts) if parts else '',
            'template': _mask(parts) if parts else '',
            'message': message,
            'occurrences': occurrences,
        }
        entry.update(extra)
        self.entries.append(entry)
        return entry

    def unsupported(self, parts, message, **extra):
        return self._add('unsupported', parts, message, **extra)

    def ambiguous(self, parts, message, resolution=None, **extra):
        entry = self._add('ambiguous', parts, message, **extra)
        if resolution:
            entry['resolution'] = resolution
        return entry

    def unmapped(self, parts, message, **extra):
        return self._add('unmapped', parts, message, **extra)

    def ignored(self, parts, message, **extra):
        return self._add('ignored', parts, message, **extra)

    def error(self, parts, message, **extra):
        return self._add('error', parts, message, **extra)

    def note(self, message):
        self.notes.append(message)

    def coverage(self, leaves, missing, metadata=None, content=None):
        metadata = metadata if metadata is not None else []
        content = content if content is not None else missing
        self.coverage_info = {
            'data_leaves': len(leaves),
            'mapped_leaves': len(leaves) - len(missing),
            'redundant_metadata_leaves': len(metadata),
            'unmapped_content_leaves': len(content),
            'missing': [path_text(p) for p in sorted(content)],
        }

    # ---------------------------------------------------------------- output
    def _aggregate(self, kind):
        groups = collections.OrderedDict()
        for entry in self.entries:
            if entry['kind'] != kind:
                continue
            key = (entry['template'], entry['message'])
            if key not in groups:
                groups[key] = {
                    'template': entry['template'],
                    'message': entry['message'],
                    'count': 0,
                    'examples': [],
                }
                if 'resolution' in entry:
                    groups[key]['resolution'] = entry['resolution']
            group = groups[key]
            group['count'] += entry.get('occurrences', 1)
            if len(group['examples']) < 3:
                group['examples'].append(entry['path'])
        return list(groups.values())

    def to_dict(self, input_info, output_text, output_name):
        by_kind = {kind: self._aggregate(kind) for kind in LEAF_KINDS}
        section_stats = collections.OrderedDict()
        if self.coverage_info:
            for path in self.coverage_info.get('missing', []):
                section = path.split('/', 1)[0] if path else ''
                stats = section_stats.setdefault(section, {'missing': 0, 'examples': []})
                stats['missing'] += 1
                if len(stats['examples']) < 5:
                    stats['examples'].append(path)
        counts = {
            'unmapped': sum(g['count'] for g in by_kind['unmapped']),
            'unsupported': sum(g['count'] for g in by_kind['unsupported']),
            'ambiguous': sum(g['count'] for g in by_kind['ambiguous']),
            'ignored': sum(g['count'] for g in by_kind['ignored']),
            'errors': sum(g['count'] for g in by_kind['error']),
        }
        data = {
            'translator': {'name': 'oc2h3c', 'version': __version__},
            'input': input_info,
            'output': {
                'cli_lines': len(output_text.splitlines()),
                'cli_sha256': hashlib.sha256(output_text.encode('utf-8')).hexdigest(),
                'name': output_name,
            },
            'summary': dict(counts),
            'coverage': self.coverage_info,
            'unmapped_by_section': section_stats,
            'diagnostics': by_kind,
            'notes': self.notes,
        }
        if self.fatal:
            data['fatal'] = self.fatal
        return data

    def render_json(self, input_info, output_text, output_name):
        return json.dumps(self.to_dict(input_info, output_text, output_name),
                          ensure_ascii=False, indent=2, sort_keys=False) + '\n'

    def render_text(self, input_info, output_text, output_name):
        data = self.to_dict(input_info, output_text, output_name)
        lines = []
        lines.append('oc2h3c %s report' % data['translator']['version'])
        lines.append('input : %s' % data['input']['path'])
        lines.append('        sha256=%s bytes=%d' % (data['input']['sha256'], data['input']['bytes']))
        lines.append('output: %s lines=%d sha256=%s'
                     % (data['output']['name'], data['output']['cli_lines'], data['output']['cli_sha256']))
        cov = data.get('coverage') or {}
        if cov:
            lines.append('coverage: %d/%d data leaves mapped (%.2f%%); '
                         'redundant metadata leaves=%d, unmapped content leaves=%d'
                         % (cov['mapped_leaves'], cov['data_leaves'],
                            100.0 * cov['mapped_leaves'] / max(1, cov['data_leaves']),
                            cov['redundant_metadata_leaves'], cov['unmapped_content_leaves']))
        summary = data['summary']
        lines.append('diagnostics: unsupported=%d ambiguous=%d ignored=%d errors=%d '
                     'unmapped=%d'
                     % (summary['unsupported'], summary['ambiguous'],
                        summary['ignored'], summary['errors'], summary['unmapped']))
        titles = [('error', 'ERRORS'), ('unsupported', 'UNSUPPORTED INPUT'),
                  ('ambiguous', 'AMBIGUOUS MAPPINGS'), ('ignored', 'IGNORED INPUT'),
                  ('unmapped', 'UNMAPPED INPUT (grouped by path template)')]
        for kind, title in titles:
            groups = data['diagnostics'][kind]
            if not groups:
                continue
            lines.append('')
            lines.append('== %s ==' % title)
            for group in groups:
                lines.append('- [%s] %s' % (group['count'], group['template'] or '(document)'))
                lines.append('    %s' % group['message'])
                if group.get('resolution'):
                    lines.append('    resolution: %s' % group['resolution'])
                for example in group['examples']:
                    lines.append('    e.g. %s' % example)
        if data.get('unmapped_by_section'):
            lines.append('')
            lines.append('== UNMAPPED INPUT BY SECTION ==')
            for section, stats in data['unmapped_by_section'].items():
                lines.append('- %-24s %d leaf/leaves' % (section or '(root)', stats['missing']))
        if data['notes']:
            lines.append('')
            lines.append('== NOTES ==')
            for note in data['notes']:
                lines.append('- ' + note)
        return '\n'.join(lines) + '\n'
