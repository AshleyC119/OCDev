"""Monitor-link mapping (feature-pass work item)."""
from . import common

BASE = ('system', 'monitor-link', 'groups', 'group')


def _group_id(ctx, name, path):
    label = ctx.val(*(path + ('name',)), default=name)
    stored = ctx.val(*(path + ('config', 'name')))
    if stored is not None and label is not None and stored != label:
        ctx.ambiguous(path + ('config', 'name'),
                      'monitor-link group name %r differs from its id %r'
                      % (stored, label),
                      'the instance name is used as the CLI group number')
    return label if label is not None else name


def emit_monitor_link(ctx):
    group = ctx.group()
    for name in common.sorted_names(ctx, *BASE):
        path = BASE + (name,)
        label = _group_id(ctx, name, path)
        group.append('monitor-link group %s' % label)
        down_delay = ctx.val(*(path + ('downlink', 'config', 'up-delay')))
        if down_delay is not None:
            group.append('downlink up-delay %s' % down_delay)
        up_delay = ctx.val(*(path + ('uplink', 'config', 'up-delay')))
        if up_delay is not None:
            group.append('uplink up-delay %s' % up_delay)


def emit_monitor_link_ports(ctx):
    for name in common.sorted_names(ctx, *BASE):
        path = BASE + (name,)
        label = _group_id(ctx, name, path)
        interfaces = path + ('interfaces', 'interface')
        for iface in common.sorted_names(ctx, *interfaces):
            iface_path = interfaces + (iface,)
            config = iface_path + ('config',)
            for name_path in (iface_path + ('name',), config + ('name',)):
                stored = ctx.val(*name_path)
                if stored is not None and stored != iface:
                    ctx.ambiguous(name_path,
                                  'monitor-link member instance key %r stores a '
                                  'different name %r' % (iface, stored),
                                  'instance key is used for the CLI interface name')
            lines = []
            for role in ('downlink', 'uplink'):
                role_path = iface_path + (role,)
                if not isinstance(ctx.dig(*role_path), dict):
                    continue
                enabled = ctx.bool_val(*(role_path + ('config', 'enable')))
                if enabled:
                    lines.append(' port monitor-link group %s %s' % (label, role))
                elif enabled is False:
                    ctx.unsupported(role_path + ('config', 'enable'),
                                    'monitor-link %s role is configured but disabled; '
                                    'no CLI command is emitted' % role)
                else:
                    ctx.error(role_path + ('config', 'enable'),
                              'monitor-link %s enable flag is missing or not boolean' % role)
            threshold = ctx.val(*(config + ('threshold',)))
            if threshold is not None:
                ctx.unsupported(config + ('threshold',),
                                'monitor-link interface threshold has no emitted CLI '
                                'command in the reference mapping')
            group = ctx.group()
            group.append('interface %s' % common.cli_name(iface))
            group.extend(lines)
