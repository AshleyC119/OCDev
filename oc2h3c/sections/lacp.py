"""LACP / S-MLAG mapping (feature-pass work item)."""
from . import common

BASE = ('lacp',)
INTERFACES = BASE + ('interfaces', 'interface')


def emit_lacp(ctx):
    group = ctx.group()
    config = BASE + ('config',)
    mac = ctx.val(*(config + ('system-id-mac',)))
    if mac:
        try:
            group.append('lacp system-mac %s' % common.mac_to_h3c(mac))
        except ValueError as exc:
            ctx.error(config + ('system-id-mac',), str(exc))
    number = ctx.val(*(config + ('system-number',)))
    if number is not None:
        group.append('lacp system-number %s' % number)
    priority = ctx.val(*(config + ('system-priority',)))
    if priority is not None:
        group.append('lacp system-priority %s' % priority)

    ctx.ambiguous(INTERFACES,
                  'the OC LACP "s-mlag-group" attribute is emitted with the fixed '
                  '"port s-mlag group" keyword pair',
                  'the s-mlag keyword is a fixed CLI constant that the OC model '
                  'cannot express')
    ctx.ambiguous(INTERFACES,
                  'the OC LACP interval enumeration value cannot be emitted '
                  'verbatim as a CLI period keyword',
                  'interval FAST is rendered as "lacp period short", SLOW as '
                  '"lacp period long" on the member interfaces')
    for name in common.sorted_names(ctx, *INTERFACES):
        path = INTERFACES + (name,)
        stored = ctx.val(*(path + ('name',)))
        if stored is not None and stored != name:
            ctx.ambiguous(path + ('name',),
                          'LACP interface instance key %r stores a different name %r'
                          % (name, stored),
                          'instance key is used for the CLI interface name')
        iface_config = path + ('config',)
        group.append('interface %s' % common.cli_name(name))
        smlag = ctx.val(*(iface_config + ('s-mlag-group',)))
        if smlag is not None:
            group.append('port s-mlag group %s' % smlag)
        edge_port = ctx.bool_val(*(iface_config + ('edge-port',)))
        if edge_port:
            group.append('lacp edge-port')
        elif edge_port is False:
            ctx.ignored(iface_config + ('edge-port',),
                        'LACP edge port is disabled (default); no CLI command is '
                        'emitted for the default state')
        system_number = ctx.val(*(iface_config + ('system-number',)))
        if system_number is not None:
            ctx.unsupported(iface_config + ('system-number',),
                            'per-aggregate LACP system number has no emitted CLI '
                            'command in the reference mapping')
        interval = ctx.val(*(iface_config + ('interval',)))
        members = path + ('members', 'member')
        for member in common.sorted_names(ctx, *members):
            member_path = members + (member,)
            member_name = ctx.val(*(member_path + ('interface',)), default=member)
            group.append('interface %s' % common.cli_name(member_name or member))
            if interval == 'FAST':
                group.append('lacp period short')
            elif interval == 'SLOW':
                group.append('lacp period long')
            elif interval:
                ctx.unsupported(iface_config + ('interval',),
                                'LACP interval %r has no mapped CLI period' % interval)
