"""INT / iFIT mapping (feature-pass work item)."""
from . import common

BASE = ('int',)
INTERFACES = BASE + ('interfaces', 'interface')


def emit_int(ctx):
    group = ctx.group()
    device_id = ctx.val(*(BASE + ('config', 'device-id')))
    names = common.sorted_names(ctx, *INTERFACES)
    if not names and device_id is None:
        ctx.unsupported(BASE, 'no INT/iFIT configuration present; nothing emitted')
        return
    group.append('telemetry ifa global enable')
    ctx.ambiguous(BASE + ('config',),
                  'the OC INT model has no global administrative-enable attribute; '
                  'only the device-id is exported',
                  'the global iFIT feature is enabled whenever the OC int container '
                  'is provisioned, following the provisioned reference convention')
    if device_id is not None:
        group.append('telemetry ifa device-id %s' % device_id)
    else:
        ctx.unsupported(BASE + ('config',), 'iFIT device-id is missing; command not emitted')
    ctx.ambiguous(INTERFACES,
                  'the OC flag insert-md-transit does not name an iFIT role; the '
                  'CLI requires a role keyword',
                  'insert-md-transit is rendered as the fixed role keyword '
                  '"transit"')
    for name in names:
        path = INTERFACES + (name,)
        config = path + ('config',)
        stored = ctx.val(*(path + ('name',)))
        if stored is not None and stored != name:
            ctx.ambiguous(path + ('name',),
                          'INT interface instance key %r stores a different name %r'
                          % (name, stored),
                          'instance key is used for the CLI interface name')
        transit = ctx.bool_val(*(config + ('insert-md-transit',)))
        if transit:
            group.append('interface %s' % common.cli_name(name))
            group.append('telemetry ifa role transit')
        elif transit is False:
            ctx.ignored(config + ('insert-md-transit',),
                        'interface does not insert metadata in transit; no CLI '
                        'role command is emitted')
        else:
            ctx.error(config + ('insert-md-transit',),
                      'absent or non-boolean insert-md-transit value')
        insert_md = ctx.bool_val(*(config + ('insert-md',)))
        if insert_md is not None:
            ctx.ignored(config + ('insert-md',),
                        'metadata insertion is expressed by the iFIT transit role; '
                        'the flag has no separate CLI command')
