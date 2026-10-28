"""Verify the shared original freeze without rewriting any files."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_FREEZE = '7c3eff6441253e462ca4b2780b228fcf107487ac63f8e2575ddaac37d0cc85c1'


def main():
    raw = (ROOT / 'FROZEN.json').read_bytes()
    if sha256(raw).hexdigest() != EXPECTED_FREEZE:
        raise SystemExit('FROZEN.json differs from the shared original freeze')
    frozen = json.loads(raw)
    for name, record in frozen['files'].items():
        path = (ROOT / name).resolve()
        if ROOT not in path.parents:
            raise SystemExit('Frozen path outside workspace: ' + name)
        data = path.read_bytes()
        if len(data) != record['bytes'] or sha256(data).hexdigest() != record['sha256']:
            raise SystemExit('Frozen file mismatch: ' + name)
    print('Verified original freeze: %d files unchanged.' % len(frozen['files']))


if __name__ == '__main__':
    main()
