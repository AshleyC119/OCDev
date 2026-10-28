"""LLDP mapping (feature-pass work item)."""
from . import common

BASE = ('lldp',)
INTERFACES = BASE + ('interfaces', 'interface')


def _name_check(ctx, path, name):
    """Consume the redundant stored instance names and detect mismatches."""
    for name_path in (path + ('name',), path + ('config', 'name')):
        stored = ctx.val(*name_path)
        if stored is not None and stored != name:
            ctx.ambiguous(name_path,
                          'LLDP interface instance key %r stores a different name %r'
                          % (name, stored),
                          'instance key is used for the CLI interface name')


def emit_lldp(ctx):
    group = ctx.group()
    enabled = ctx.bool_val(*(BASE + ('config', 'enabled')))
    if enabled:
        group.append('lldp global enable')
    elif enabled is False:
        ctx.unsupported(BASE + ('config', 'enabled'),
                        'LLDP is globally disabled; no CLI command is emitted')
    else:
        ctx.error(BASE + ('config', 'enabled'),
                  'global LLDP enabled state is missing or not a boolean')
    # The OC model has no field for the PVID-inconsistency check, but the
    # provisioned CLI always turns it on globally.
    group.append('lldp ignore-pvid-inconsistency')
    ctx.ambiguous(BASE,
                  'the OC LLDP model has no ignore-pvid-inconsistency attribute, '
                  'so the global check cannot be derived from the document',
                  'emitted unconditionally as a fixed global default of the '
                  'reference configuration')
    ctx.ambiguous(INTERFACES,
                  'the OC model only carries the management-address value, not '
                  'the TLV set / TLV name',
                  'management-address is emitted with the fixed keyword pair '
                  '"basic-tlv management-address-tlv"')
    for name in common.sorted_names(ctx, *INTERFACES):
        path = INTERFACES + (name,)
        config = path + ('config',)
        _name_check(ctx, path, name)
        iface_enabled = ctx.bool_val(*(config + ('enabled',)))
        if iface_enabled is False:
            ctx.unsupported(config + ('enabled',),
                            'LLDP is disabled on this interface; no per-interface '
                            'CLI command is emitted by the reference mapping')
        elif iface_enabled is None:
            ctx.error(config + ('enabled',),
                      'per-interface LLDP enabled state is missing or not a boolean')
        else:
            ctx.ignored(config + ('enabled',),
                        'per-interface LLDP is enabled by default; no CLI command '
                        'is emitted for the default state')
        management = ctx.val(*(config + ('management-address',)))
        admin_status = ctx.val(*(config + ('admin-status',)))
        lines = []
        if management:
            lines.append('lldp tlv-enable basic-tlv management-address-tlv %s'
                         % management)
        if admin_status:
            lines.append('lldp admin-status %s' % admin_status)
        if lines:
            group.append('interface %s' % common.cli_name(name))
            group.extend(lines)
