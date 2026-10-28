"""System-level service mapping (reference segment 600).

The block emitted here is the device-wide service configuration: ICMP behaviour,
host name, login header, clock, SSH access control, logging (info-center), NTP,
SNMP, and ARP aging.  Values are derived from the OC ``system`` subtree; fixed
CLI text that the OC cannot express is recorded with ``ctx.ambiguous`` and
deliberately unemitted values with ``ctx.unsupported`` / ``ctx.ignored``.
"""
from . import common

#: The OC document has no ACL numbers.  Basic (control-plane) ACLs are numbered
#: 2000+ in document order - the same deterministic policy the ACL section uses
#: (kept local here so this module does not depend on another section's internals).
ACL_CTRL_TYPE = 'ACL_CTRL'
BASIC_ACL_NUMBER_START = 2000

#: Login header text is not present in the OC document at all (see ambiguous note).
LOGIN_BANNER_RULE = '*' * 57
LOGIN_BANNER = (
    'header login %',
    LOGIN_BANNER_RULE,
    '               Authorized Access Only#',
    'Disconnect IMMEDIATELY as you are not an authorized user#',
    LOGIN_BANNER_RULE,
    '%',
)


def _basic_acl_numbers(ctx):
    """Map ACL set key and ACL name -> basic ACL number, mirroring the ACL policy."""
    numbers = {}
    index = 0
    for key, _node in ctx.items('acl', 'acl-sets', 'acl-set'):
        acl_type = ctx.val('acl', 'acl-sets', 'acl-set', key, 'config', 'type')
        if acl_type != ACL_CTRL_TYPE:
            continue
        number = BASIC_ACL_NUMBER_START + index
        index += 1
        numbers[key] = number
        name = ctx.val('acl', 'acl-sets', 'acl-set', key, 'config', 'name')
        if name and name not in numbers:
            numbers[name] = number
    return numbers


def _report_acl_number(ctx, parts, name, number):
    ctx.ambiguous(parts,
                  'the OC refers to ACL %r by name; the emitted CLI needs its basic-ACL '
                  'number, which is not present in the document' % name,
                  'number %d assigned by the translator basic-ACL numbering policy '
                  '(%d + document order of %s sets)'
                  % (number, BASIC_ACL_NUMBER_START, ACL_CTRL_TYPE))


def _emit_icmp(ctx, group):
    icmp = ('system', 'icmp', 'config')
    unreachable = ctx.bool_val(*(icmp + ('ip-unreachable',)))
    if unreachable:
        group.append('ip unreachables enable')
    ttl = ctx.bool_val(*(icmp + ('ip-ttl-expire',)))
    if ttl is not None:
        ctx.unsupported(icmp + ('ip-ttl-expire',),
                        'ICMP time-exceeded notification is configured in the OC but '
                        'has no implemented CLI mapping; input left unrepresented')


def _emit_identity(ctx, group):
    hostname = ctx.val('system', 'config', 'hostname')
    if hostname:
        group.append('sysname %s' % hostname)
    for line in LOGIN_BANNER:
        group.append(line)
    ctx.ambiguous(('system', 'config'),
                  'the login header banner text (and the %/commented-line form) is not '
                  'present anywhere in the OC document; it is a fixed translator '
                  'constant for the native management banner',
                  'fixed login banner emitted')
    # Remaining system identity/state metadata.  The ISP domain name is mapped by
    # the AAA section, so it is not reported here.
    for field, message in (
            ('role', 'device role metadata has no CLI effect'),
            ('route-mode', 'device route-mode metadata has no CLI effect'),
            ('switch-mode', 'device switch-mode metadata has no CLI effect'),
            ('ztp-status', 'ZTP status metadata has no CLI effect'),
            ('login-shell', 'login shell metadata has no CLI effect')):
        value = ctx.val('system', 'config', field)
        if value is not None:
            ctx.ignored(('system', 'config', field), message)


def _emit_clock(ctx, group):
    timezone = ctx.val('system', 'clock', 'config', 'timezone-name')
    if not timezone:
        return
    if ' ' not in timezone:
        ctx.error(('system', 'clock', 'config', 'timezone-name'),
                  'clock timezone value %r has no separate UTC offset' % timezone)
        return
    zone, offset = timezone.rsplit(' ', 1)
    keyword = 'add'
    if offset.startswith('-'):
        keyword = 'minus'
        offset = offset[1:]
    elif offset.startswith('+'):
        offset = offset[1:]
    group.append('clock timezone %s %s %s' % (zone, keyword, offset))
    ctx.ambiguous(('system', 'clock', 'config', 'timezone-name'),
                  'the OC combines the zone name and a sign-less UTC offset; the '
                  'add/minus keyword is derived from the offset sign with add as the '
                  'default when no sign is present',
                  'add keyword emitted for non-negative offsets, minus for negative')


def _emit_ssh(ctx, group, acl_numbers):
    config = ('system', 'ssh-server', 'config')
    enabled = ctx.bool_val(*(config + ('enable',)))
    if enabled:
        group.append('ssh server enable')
    filters = ctx.dig(*(config + ('filters',)))
    if not isinstance(filters, list):
        if filters is not None:
            ctx.unsupported(config + ('filters',),
                            'SSH access filter list is not a JSON array; not emitted')
        return
    ctx.used.add(tuple(str(part) for part in config + ('filters',)))
    for name in filters:
        number = acl_numbers.get(name)
        if number is None:
            ctx.unsupported(config + ('filters',),
                            'SSH filter refers to ACL %r, which is not defined as a '
                            'basic ACL in the OC document; filter not emitted' % name)
            continue
        group.append('ssh server acl %d' % number)
        _report_acl_number(ctx, config + ('filters',), name, number)


def _emit_logging(ctx, group):
    logging = ('system', 'logging')
    servers = ctx.dig(*(logging + ('remote-servers', 'remote-server')))
    for host_key in sorted(servers or {}):
        node = logging + ('remote-servers', 'remote-server', host_key)
        host = ctx.val(*(node + ('config', 'host')), default=host_key)
        vrf = ctx.val(*(node + ('network-instance', 'config', 'name')))
        ctx.ignored(node + ('host',), 'duplicate of config/host')
        facilities = []
        selectors = ctx.dig(*(node + ('selectors', 'selector')))
        for selector_key in sorted(selectors or {}):
            selector = node + ('selectors', 'selector', selector_key)
            facility = ctx.val(*(selector + ('config', 'facility')))
            severity = ctx.val(*(selector + ('config', 'severity')))
            ctx.ignored(selector + ('severity',), 'duplicate of config/severity')
            ctx.ignored(selector + ('facility',), 'duplicate of config/facility')
            ctx.ignored(selector + ('facility,severity',),
                        'combined facility/severity key duplicate')
            if severity:
                ctx.ignored(selector + ('config', 'severity'),
                            'log severity is not represented in the emitted loghost line')
            text = facility.lower() if facility else None
            if text and text not in facilities:
                facilities.append(text)
        for facility in facilities or [None]:
            line = 'info-center loghost'
            if vrf:
                line += ' vpn-instance %s' % vrf
            line += ' %s' % host
            if facility:
                line += ' facility %s' % facility
            group.append(line)
    buffer_size = ctx.val(*(logging + ('config', 'buffer-size')))
    if buffer_size is not None:
        group.append('info-center logbuffer size %s' % buffer_size)
    source_interface = ctx.val(*(logging + ('config', 'source-interface')))
    if source_interface:
        group.append('info-center loghost source %s' % source_interface)
    components = ctx.dig(*(logging + ('components', 'component')))
    for component in sorted(components or {}):
        cnode = logging + ('components', 'component', component)
        ctx.ignored(cnode + ('name',), 'duplicate of the component map key')
        ctx.ignored(cnode + ('config', 'name'), 'duplicate of the component map key')
        nodes = ctx.dig(*(cnode + ('log-nodes', 'log-node')))
        for node_name in sorted(nodes or {}):
            nnode = cnode + ('log-nodes', 'log-node', node_name)
            action = ctx.val(*(nnode + ('config', 'action')))
            ctx.ignored(nnode + ('node',), 'duplicate of the log-node map key')
            if action:
                group.append('info-center source %s %s %s'
                             % (component, node_name, action))


def _emit_ntp(ctx, group):
    ntp = ('system', 'ntp')
    enabled = ctx.bool_val(*(ntp + ('config', 'enabled')))
    if enabled:
        group.append('ntp-service enable')
    servers = ctx.dig(*(ntp + ('servers', 'server')))
    for key in sorted(servers or {}):
        node = ntp + ('servers', 'server', key)
        address = ctx.val(*(node + ('config', 'address')), default=key)
        vrf = ctx.val(*(node + ('network-instance', 'config', 'name')))
        ctx.ignored(node + ('address',), 'duplicate of config/address')
        line = 'ntp-service unicast-server %s' % address
        if vrf:
            line += ' vpn-instance %s' % vrf
        group.append(line)
    source_interface = ctx.val(*(ntp + ('config', 'source-interface')))
    if source_interface:
        group.append('ntp-service source %s' % source_interface)
    source_address = ctx.val(*(ntp + ('config', 'ntp-source-address')))
    if source_address is not None:
        ctx.unsupported(ntp + ('config', 'ntp-source-address'),
                        'the explicit NTP source address has no implemented CLI '
                        'mapping (the source interface is emitted instead); input '
                        'left unrepresented')


def _snmp_version_lines(ctx, group, version, path):
    if not version:
        return
    group.append('snmp-agent sys-info version %s' % version)
    if version != 'v3':
        group.append('undo snmp-agent sys-info version v3')
        ctx.ambiguous(path,
                      'the OC lists only the enabled SNMP version(s); the native '
                      'block also disables SNMPv3 explicitly when v3 is not enabled '
                      '(SNMPv3 is on by default)',
                      'undo ... version v3 emitted whenever the OC version set omits v3')


def _emit_snmp(ctx, group, acl_numbers):
    snmp = ('system', 'snmp')
    if not isinstance(ctx.dig(*snmp), dict):
        return
    servers = ctx.dig(*(snmp + ('servers', 'server')))
    config = ctx.dig(*(snmp + ('config',)))
    communities = ctx.dig(*(snmp + ('communities', 'community')))
    if not (servers or config or communities):
        return
    group.append('snmp-agent')
    # The enabled version set is a global SNMP setting; the native block repeats it
    # in front of every trap target.
    global_version = ctx.val(*(snmp + ('config', 'version')))
    for key in sorted(servers or {}):
        node = snmp + ('servers', 'server', key)
        address = ctx.val(*(node + ('config', 'address')), default=key)
        vrf = ctx.val(*(node + ('network-instance', 'config', 'name')))
        version = ctx.val(*(node + ('config', 'version')))
        target_type = ctx.val(*(node + ('config', 'type')))
        security = ctx.val(*(node + ('config', 'key')))
        ctx.ignored(node + ('address',), 'duplicate of config/address')
        _snmp_version_lines(ctx, group, global_version or version,
                            snmp + ('config', 'version'))
        line = 'snmp-agent target-host %s address udp-domain %s' \
               % (target_type or 'trap', address)
        if vrf:
            line += ' vpn-instance %s' % vrf
        if security:
            line += ' params securityname %s' % security
        if version:
            line += ' %s' % version
        group.append(line)
        ctx.ambiguous(node + ('config',),
                      'the trap target transport/domain keyword and the "params '
                      'securityname" keyword form are fixed CLI text with no OC '
                      'counterpart',
                      'udp-domain and params securityname emitted')
    for name in sorted(communities or {}):
        node = snmp + ('communities', 'community', name)
        mode = ctx.val(*(node + ('config', 'mode')))
        filter_name = ctx.val(*(node + ('config', 'filter')))
        ctx.ignored(node + ('name',), 'duplicate of the community map key')
        ctx.ignored(node + ('config', 'name'),
                    'duplicate of the community map key')
        line = 'snmp-agent community %s %s' % (mode or 'read', name)
        if filter_name:
            number = acl_numbers.get(filter_name)
            if number is None:
                ctx.unsupported(node + ('config', 'filter'),
                                'SNMP community filter refers to ACL %r, which is not '
                                'defined as a basic ACL in the OC document; the ACL '
                                'reference is not emitted' % filter_name)
            else:
                line += ' acl %d' % number
                _report_acl_number(ctx, node + ('config', 'filter'), filter_name, number)
        group.append(line)
    packet_size = ctx.val(*(snmp + ('config', 'packet-size')))
    if packet_size is not None:
        group.append('snmp-agent packet max-size %s' % packet_size)


def _emit_arp(ctx, group):
    arp = ('system', 'arp')
    aging = ctx.val(*(arp + ('config', 'time-out')))
    if aging is not None:
        group.append('arp timer aging %s' % aging)
    arp_to_route = ctx.val(*(arp + ('config', 'arp-to-route')))
    if arp_to_route is not None:
        ctx.ignored(arp + ('config', 'arp-to-route'),
                    'the system-wide ARP-to-route default has no CLI command here; '
                    'per-interface ARP-to-route is mapped with the interface section')
    interfaces = ctx.dig(*(arp + ('interfaces', 'interface')))
    for name in sorted(interfaces or {}):
        node = arp + ('interfaces', 'interface', name)
        time_out = ctx.val(*(node + ('config', 'time-out')))
        rate_limit = ctx.val(*(node + ('config', 'rate-limit')))
        ctx.ignored(node + ('name',), 'duplicate of the interface map key')
        ctx.ignored(node + ('config', 'name'), 'duplicate of the interface map key')
        if rate_limit is not None:
            ctx.unsupported(node + ('config', 'rate-limit'),
                            'per-interface ARP rate limit has no implemented CLI '
                            'mapping; input left unrepresented')
        if time_out is not None:
            group.append('interface %s' % common.cli_name(name))
            group.append('arp timer aging second %s' % time_out)
        elif rate_limit is None:
            ctx.ignored(node, 'no ARP aging/rate-limit command emitted for this interface')


def emit_system(ctx):
    group = ctx.group()
    acl_numbers = _basic_acl_numbers(ctx)
    _emit_icmp(ctx, group)
    _emit_identity(ctx, group)
    _emit_clock(ctx, group)
    _emit_ssh(ctx, group, acl_numbers)
    _emit_logging(ctx, group)
    _emit_ntp(ctx, group)
    _emit_snmp(ctx, group, acl_numbers)
    _emit_arp(ctx, group)
