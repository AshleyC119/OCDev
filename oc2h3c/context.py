"""Shared translation context: document access, coverage tracking, reporting."""
import re


def _norm_scalar(value):
    """Normalise an OC scalar to a plain CLI token.

    OC values in the development corpus are JSON strings; accept native JSON
    scalars too so the translator is not limited to that serialisation.
    """
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if value is None:
        return None
    return str(value)


# Leaf names that only mirror the containing map key / list index.  They carry no
# configuration content of their own, so they are accounted separately from
# genuinely unmapped content.
REDUNDANT_LEAF_NAMES = frozenset({
    'name', 'interface-id', 'index', 'sequence', 'sequence-id', 'id',
    'slice-name', 'vlan-id', 'address', 'ip', 'prefix', 'identifier',
    'name,type', 'name,identifier', 'name,severity', 'facility,severity',
})


def is_redundant_leaf(path):
    """True when the leaf only repeats its parent container key."""
    if not path:
        return True
    leaf = path[-1]
    if leaf not in REDUNDANT_LEAF_NAMES:
        return False
    return len(path) >= 2


class Ctx:
    def __init__(self, doc, report):
        self.doc = doc
        self.report = report
        self.groups = []          # list[list[str]] emitted CLI blocks
        self.used = set()         # path tuples read by a mapping
        self.ignored_paths = set()  # path tuples deliberately ignored (reported)
        self.interfaces = None    # built lazily by interfaces module
        self._warned = set()

    # ---------------------------------------------------------------- output
    def group(self):
        """Start a new CLI block (rendered as: return / system-view / body)."""
        self.groups.append([])
        return self.groups[-1]

    # -------------------------------------------------------------- document
    def dig(self, *parts):
        """Navigate without marking coverage. Returns None when absent."""
        node = self.doc
        for part in parts:
            if isinstance(node, dict):
                if part not in node:
                    return None
                node = node[part]
            elif isinstance(node, list):
                try:
                    node = node[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return node

    def val(self, *parts, **kwargs):
        """Navigate, mark the path as consumed, return a normalised scalar."""
        node = self.dig(*parts)
        if node is None:
            return kwargs.get('default')
        if isinstance(node, (dict, list)):
            # a container was addressed as a scalar: report and ignore
            self.report.error(parts, 'expected scalar but found %s' % type(node).__name__)
            return kwargs.get('default')
        self.used.add(tuple(str(p) for p in parts))
        return _norm_scalar(node)

    def int_val(self, *parts, **kwargs):
        raw = self.val(*parts, **kwargs)
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            self.report.error(parts, 'expected integer, got %r' % raw)
            return kwargs.get('default')

    def bool_val(self, *parts, **kwargs):
        raw = self.val(*parts, **kwargs)
        if raw is None:
            return None
        text = raw.strip().lower()
        if text == 'true':
            return True
        if text == 'false':
            return False
        self.report.error(parts, 'expected boolean, got %r' % raw)
        return kwargs.get('default')

    def items(self, *parts):
        """Iterate a map's items without marking coverage of its children."""
        node = self.dig(*parts)
        if not isinstance(node, dict):
            return []
        return [(k, v) for k, v in node.items() if isinstance(v, dict)]

    def seq(self, *parts):
        node = self.dig(*parts)
        if not isinstance(node, list):
            return []
        return [v for v in node if isinstance(v, dict)]

    # -------------------------------------------------------------- reporting
    def unsupported(self, parts, message):
        self.ignored_paths.add(tuple(str(p) for p in parts))
        self.report.unsupported(parts, message)

    def ignored(self, parts, message):
        self.ignored_paths.add(tuple(str(p) for p in parts))
        self.report.ignored(parts, message)

    def ambiguous(self, parts, message, resolution):
        self.report.ambiguous(parts, message, resolution)

    def error(self, parts, message):
        self.report.error(parts, message)

    def note(self, message):
        self.report.note(message)

    # -------------------------------------------------------------- coverage
    def finalize_coverage(self):
        """Record every data leaf that no mapping consumed or explicitly ignored."""
        leaves = []
        stack = [((), self.doc)]
        while stack:
            path, node = stack.pop()
            if isinstance(node, dict):
                for key, value in node.items():
                    stack.append((path + (str(key),), value))
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    stack.append((path + (str(index),), value))
            else:
                leaves.append(path)
        used = self.used
        ignored = self.ignored_paths

        def covered(leaf):
            for size in range(len(leaf), 0, -1):
                prefix = leaf[:size]
                if prefix in used or prefix in ignored:
                    return True
            return False

        missing = [leaf for leaf in leaves if not covered(leaf)]
        metadata = [leaf for leaf in missing if is_redundant_leaf(leaf)]
        content = [leaf for leaf in missing if not is_redundant_leaf(leaf)]
        self.report.coverage(leaves, missing, metadata, content)

        # Give every remaining content leaf a structured, grouped report entry so
        # no input value is silently unaccounted for.
        from .report import _mask
        groups = {}
        for leaf in content:
            groups.setdefault(_mask(leaf), []).append(leaf)
        for leaves_group in groups.values():
            self.report.unmapped(
                leaves_group[0],
                'input value(s) under this path template are not represented in the '
                'generated CLI (no implemented mapping)',
                occurrences=len(leaves_group))
        return len(leaves), len(content)


def cli_name(oc_name):
    """Map an OC interface name to its H3C CLI name."""
    if oc_name.startswith('Vlan') and not oc_name.startswith('Vlan-interface'):
        return 'Vlan-interface' + oc_name[len('Vlan'):]
    return oc_name


_INSTANCE_RE = re.compile(r'^(?:\d[\d:/.]*|[A-Za-z][\w-]*\d[\w:/.-]*)$')


def path_text(parts):
    return '/'.join(str(p) for p in parts)
