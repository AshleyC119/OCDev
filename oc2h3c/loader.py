"""Load and structurally validate the input OC document."""
import hashlib
import json

from .errors import InputError


def load_bytes(path):
    try:
        with open(path, 'rb') as f:
            return f.read()
    except OSError as exc:
        raise InputError('cannot read input %r: %s' % (path, exc))


def load_document(path):
    """Return (document, info dict). Raises InputError for unusable input."""
    raw = load_bytes(path)
    if not raw.strip():
        raise InputError('input file is empty')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise InputError('input is not valid UTF-8: %s' % exc)
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError('input is not valid JSON: %s (line %d column %d)' % (exc.msg, exc.lineno, exc.colno))
    if not isinstance(doc, dict):
        raise InputError('top-level JSON value must be an object, got %s' % type(doc).__name__)
    info = {
        'path': path,
        'sha256': hashlib.sha256(raw).hexdigest(),
        'bytes': len(raw),
    }
    return doc, info
