"""Render emitted groups into the native H3C command script format.

The reference transcript style of the development pair consists of a leading
``return`` followed by blocks of ``system-view`` + commands, each block
terminated by ``return`` (the final ``return`` is omitted).
"""


def render(groups):
    lines = ['return']
    for body in groups:
        lines.append('system-view')
        lines.extend(body)
        lines.append('return')
    if len(lines) > 1:
        lines.pop()
    return '\n'.join(lines) + '\n'
