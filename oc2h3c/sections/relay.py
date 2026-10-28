"""DHCP relay agent mapping (feature-pass work item)."""
from . import common

BASE = ('relay-agent', 'dhcp')
INTERFACES = BASE + ('interfaces', 'interface')


def emit_dhcp(ctx):
    group = ctx.group()
    enabled = ctx.bool_val(*(BASE + ('config', 'enable-relay-agent')))
    if enabled:
        group.append('dhcp enable')
        ctx.ambiguous(BASE + ('config', 'enable-relay-agent'),
                      'the OC relay-agent enable flag is mapped to the global '
                      '"dhcp enable" command, which enables the DHCP service as a '
                      'whole rather than the relay agent alone',
                      'emitted as "dhcp enable" following the provisioned '
                      'reference convention')
    elif enabled is False:
        ctx.unsupported(BASE + ('config', 'enable-relay-agent'),
                        'DHCP relay is globally disabled; no CLI command is emitted')
    else:
        ctx.error(BASE + ('config', 'enable-relay-agent'),
                  'global DHCP relay enabled state is missing or not a boolean')

    ctx.unsupported(INTERFACES,
                    'per-interface DHCP relay state, relay source address and '
                    'agent-information option have no emitted CLI command in the '
                    'reference mapping')
    for name in common.sorted_names(ctx, *INTERFACES):
        path = INTERFACES + (name,)
        config = path + ('config',)
        stored = ctx.val(*(config + ('id',)))
        if stored is not None and stored != name:
            ctx.ambiguous(path + ('config', 'id'),
                          'DHCP relay interface instance key %r stores a different id %r'
                          % (name, stored),
                          'instance key is used for the CLI interface name')
        # The remaining per-interface leaves are covered by the container-level
        # unsupported() report above; read them so no value is dropped silently.
        ctx.val(*(config + ('enable',)))
        ctx.val(*(config + ('source-address',)))
        ctx.val(*(path + ('agent-information-option', 'config', 'enable')))
