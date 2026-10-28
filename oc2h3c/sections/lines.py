"""Console/VTY line mapping (feature-pass work item)."""
from . import common

TTY_LINES = ('system', 'tty', 'lines', 'line')
VTY_LINES = ('system', 'vty', 'lines', 'line')


def _emit_lines(ctx, base, keyword):
    group = ctx.group()
    for name in common.sorted_names(ctx, *base):
        path = base + (name,)
        config = path + ('config',)
        index = ctx.val(*(path + ('index',)), default=name)
        group.append('line %s %s' % (keyword, index))
        auth_mode = ctx.val(*(config + ('auth-mode',)))
        if auth_mode is not None:
            group.append('authentication-mode %s' % auth_mode)
        else:
            ctx.unsupported(config, 'line authentication mode is missing; command not emitted')
        roles = ctx.dig(*(config + ('user-role',)))
        if isinstance(roles, list):
            ctx.used.add(tuple(str(p) for p in config + ('user-role',)))
            values = roles
        elif roles is None:
            values = []
        else:
            ctx.used.add(tuple(str(p) for p in config + ('user-role',)))
            values = [roles]
        for role in values:
            group.append('user-role %s' % role)


def emit_line_aux(ctx):
    ctx.ambiguous(TTY_LINES,
                  'the OC system/tty container is emitted as "line aux", a fixed '
                  'CLI line type keyword that the OC model does not carry',
                  'system/tty lines are rendered as line aux <index>')
    _emit_lines(ctx, TTY_LINES, 'aux')


def emit_line_vty(ctx):
    ctx.ambiguous(VTY_LINES,
                  'the OC system/vty container is emitted as "line vty", a fixed '
                  'CLI line type keyword that the OC model does not carry',
                  'system/vty lines are rendered as line vty <index>')
    _emit_lines(ctx, VTY_LINES, 'vty')
