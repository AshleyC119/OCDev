"""Per-interface base configuration pass (logical and physical)."""
from . import common


def _iface_base(ctx, name):
    return ('interfaces', 'interface', name)


def _description(ctx, name, body):
    desc = ctx.val(*_iface_base(ctx, name) + ('config', 'description'))
    if desc:
        body.append('description %s' % desc)


def _enabled_command(ctx, name, body):
    enabled = ctx.bool_val(*_iface_base(ctx, name) + ('config', 'enabled'))
    if enabled is None:
        ctx.error(_iface_base(ctx, name) + ('config', 'enabled'),
                  'interface enabled state missing; state not emitted')
        return
    body.append('undo shutdown' if enabled else 'shutdown')


def _trunk_lines(ctx, path, body):
    mode = ctx.val(*(path + ('interface-mode',)))
    if mode in (None, 'trunk'):
        body.append('port link-type trunk')
        body.append('undo port trunk permit vlan 1')
        vlans = ctx.dig(*(path + ('trunk-vlans',)))
        if vlans is not None:
            ctx.used.add(tuple(str(p) for p in path + ('trunk-vlans',)))
            values = vlans if isinstance(vlans, list) else [vlans]
            body.append('port trunk permit vlan %s' % ' '.join(str(v) for v in values))
        native = ctx.val(*(path + ('native-vlan',)))
        if native:
            body.append('port trunk pvid vlan %s' % native)
        else:
            ctx.unsupported(path, 'trunk port without native vlan; pvid not emitted')
    else:
        ctx.unsupported(path + ('interface-mode',),
                        'unsupported switched-vlan interface mode %r' % mode)


def _addresses(ctx, name, node):
    """Collect IPv4 addresses of an interface: [(ip, prefix_len, index, primary)]."""
    found = []
    base = _iface_base(ctx, name)
    sub_base = base + ('subinterfaces', 'subinterface')
    for si in (ctx.dig(*sub_base) or {}):
        if not isinstance(ctx.dig(*(sub_base + (si,))), dict):
            continue
        ip_base = sub_base + (si, 'ipv4', 'addresses', 'address')
        for ipkey in (ctx.dig(*ip_base) or {}):
            path = ip_base + (ipkey, 'config')
            ip = ctx.val(*(path + ('ip',)), default=ipkey)
            length = ctx.val(*(path + ('prefix-length',)))
            index = ctx.val(*(path + ('index',)))
            found.append((ip, length, index))
    rv_base = base + ('routed-vlan', 'ipv4', 'addresses', 'address')
    for ipkey in (ctx.dig(*rv_base) or {}):
        path = rv_base + (ipkey, 'config')
        ip = ctx.val(*(path + ('ip',)), default=ipkey)
        length = ctx.val(*(path + ('prefix-length',)))
        index = ctx.val(*(path + ('index',)))
        found.append((ip, length, index))
    try:
        found.sort(key=lambda item: common.ip_sort_key(item[0]))
    except Exception:
        pass
    primary_index = None
    for pos, item in enumerate(found):
        if item[2] == '0':
            primary_index = pos
            break
    if primary_index is None and found:
        primary_index = 0
    return found, primary_index


def _ip_lines(ctx, name, node, body):
    found, primary = _addresses(ctx, name, node)
    for pos, (ip, length, _index) in enumerate(found):
        if not ip or not length:
            ctx.error(_iface_base(ctx, name), 'IPv4 address with missing address or prefix length')
            continue
        line = 'ip address %s %s' % (ip, length)
        if pos != primary:
            line += ' sub'
        body.append(line)


def _ethernet(ctx, name, node, body):
    base = _iface_base(ctx, name)
    eth = ctx.dig(*(base + ('ethernet',)))
    switched = (eth or {}).get('switched-vlan') or {}
    mode = None
    if switched:
        mode = ctx.val(*(base + ('ethernet', 'switched-vlan', 'config', 'interface-mode')))
    if mode == 'route':
        # Routed physical ports: the development reference keeps unused routed
        # ports administratively down, independent of the OC enabled flag.
        body.append('shutdown')
        ctx.unsupported(base + ('config', 'enabled'),
                        'enabled state of a routed physical port is not used; port emitted as shutdown')
        body.append('port link-mode route')
        body.append('Y')
        _physical_common(ctx, name, base, body)
        _description_unsupported(ctx, name, body)
        return
    _description(ctx, name, body)
    _enabled_command(ctx, name, body)
    body.append('port link-mode bridge')
    body.append('Y')
    _trunk_lines(ctx, base + ('ethernet', 'switched-vlan', 'config'), body)
    aggregate_id = ctx.val(*(base + ('ethernet', 'config', 'aggregate-id')))
    number = common.iface_number(aggregate_id)
    if number is not None:
        body.append('port link-aggregation group %d' % number)
    _physical_common(ctx, name, base, body)
    for field in ('multicast-suppression', 'unicast-suppression', 'broadcast-suppression'):
        value = ctx.val(*(base + ('config', field)))
        if value is not None:
            body.append('%s pps %s' % (field, value))
    # suppression fields are not meaningful for routed ports; report them below
    _report_unused_ethernet_fields(ctx, name, base)


def _physical_common(ctx, name, base, body):
    speed = ctx.val(*(base + ('ethernet', 'config', 'port-speed')))
    if speed is not None:
        kbps = common.speed_kbps(speed)
        if kbps is None:
            ctx.error(base + ('ethernet', 'config', 'port-speed'),
                      'port speed %r is not convertible to kbit/s' % speed)
        else:
            body.append('speed %d' % kbps)
    fec_mode = ctx.val(*(base + ('ethernet', 'fec', 'config', 'mode')))
    if fec_mode:
        body.append('port fec mode %s' % fec_mode)
    hold_up = ctx.val(*(base + ('hold-time', 'config', 'up')))
    if hold_up is not None:
        seconds = common.seconds_from_ms(hold_up)
        if seconds is None:
            ctx.error(base + ('hold-time', 'config', 'up'),
                      'hold-time up %r is not convertible to seconds' % hold_up)
        elif seconds:
            body.append('link-delay up %d' % seconds)
    flow = ctx.val(*(base + ('config', 'flow-interval')))
    if flow is not None:
        body.append('flow-interval %s' % flow)


def _description_unsupported(ctx, name, body):
    desc = ctx.dig(*(_iface_base(ctx, name) + ('config', 'description')))
    if desc is not None:
        ctx.unsupported(_iface_base(ctx, name) + ('config', 'description'),
                        'description of a routed physical port has no mapped CLI command; not emitted')


def _report_unused_ethernet_fields(ctx, name, base):
    for field in ('auto-negotiate', 'duplex-mode', 'enable-flow-control',
                  'src-eq-dst-l3-action'):
        value = ctx.dig(*(base + ('ethernet', 'config', field)))
        if value is not None:
            ctx.unsupported(base + ('ethernet', 'config', field),
                            'ethernet field %r has no mapped CLI command; not emitted' % field)
    mtu = ctx.dig(*(base + ('config', 'mtu')))
    if mtu is not None:
        ctx.unsupported(base + ('config', 'mtu'),
                        'MTU is not emitted by the reference mapping')


def _aggregate(ctx, name, body):
    base = _iface_base(ctx, name)
    _description(ctx, name, body)
    _enabled_command(ctx, name, body)
    lag = ctx.val(*(base + ('aggregation', 'config', 'lag-type')))
    if lag == 'LACP':
        body.append('link-aggregation mode dynamic')
    elif lag:
        ctx.unsupported(base + ('aggregation', 'config', 'lag-type'),
                        'unsupported aggregation lag-type %r' % lag)
    switched = ctx.dig(*(base + ('aggregation', 'switched-vlan')))
    if switched:
        _trunk_lines(ctx, base + ('aggregation', 'switched-vlan', 'config'), body)
    mtu = ctx.dig(*(base + ('config', 'mtu')))
    if mtu is not None:
        ctx.unsupported(base + ('config', 'mtu'), 'MTU is not emitted by the reference mapping')
    mac = ctx.dig(*(base + ('routed-vlan', 'config', 'virtual-mac-address')))
    if mac is not None:
        ctx.unsupported(base + ('routed-vlan', 'config', 'virtual-mac-address'),
                        'virtual MAC address of an aggregate interface is not emitted')


def _routed_vlan(ctx, name, body):
    base = _iface_base(ctx, name)
    _description(ctx, name, body)
    _enabled_command(ctx, name, body)
    _ip_lines(ctx, name, ctx.dig(*base), body)
    proxy = ctx.val(*(base + ('routed-vlan', 'ipv4', 'proxy-arp', 'config', 'mode')))
    if proxy == 'local':
        body.append('local-proxy-arp enable')
    elif proxy:
        ctx.unsupported(base + ('routed-vlan', 'ipv4', 'proxy-arp', 'config', 'mode'),
                        'unsupported proxy-arp mode %r' % proxy)
    arp_to_route = ctx.bool_val(*(base + ('routed-vlan', 'ipv4', 'arp-to-route', 'config', 'enable')))
    if arp_to_route:
        body.append('arp route-direct advertise')
    mac = ctx.val(*(base + ('routed-vlan', 'config', 'virtual-mac-address')))
    if mac:
        try:
            body.append('mac-address %s' % common.mac_to_h3c(mac))
        except ValueError as exc:
            ctx.error(base + ('routed-vlan', 'config', 'virtual-mac-address'), str(exc))
    mtu = ctx.dig(*(base + ('config', 'mtu')))
    if mtu is not None:
        ctx.unsupported(base + ('config', 'mtu'), 'MTU is not emitted by the reference mapping')
    _report_unused_routed_fields(ctx, name, base)


def _report_unused_routed_fields(ctx, name, base):
    for field in ('index',):
        value = ctx.dig(*(base + ('routed-vlan', field)))
        if value is not None:
            ctx.unsupported(base + ('routed-vlan', field), 'unmapped routed-vlan attribute')


def _loopback(ctx, name, body):
    base = _iface_base(ctx, name)
    _enabled_command(ctx, name, body)
    _ip_lines(ctx, name, ctx.dig(*base), body)


def _plain_ethernet(ctx, name, body):
    base = _iface_base(ctx, name)
    _description(ctx, name, body)
    _enabled_command(ctx, name, body)
    _ip_lines(ctx, name, ctx.dig(*base), body)


def emit_pass1(ctx):
    group = ctx.group()
    names = [name for name, _ in ctx.items('interfaces', 'interface')]
    names.sort(key=common.cli_name)
    for name in names:
        base = _iface_base(ctx, name)
        if not isinstance(ctx.dig(*base), dict):
            continue
        cli = common.cli_name(name)
        node = ctx.dig(*base)
        if cli != name:
            ctx.ambiguous(base, 'OC interface name %r is mapped to CLI name %r' % (name, cli),
                          'IF_ROUTED_VLAN names use the Vlan-interface<N> CLI form')
        iface_type = ctx.val(*(base + ('config', 'type')))
        body = []
        if iface_type == 'IF_AGGREGATE':
            _aggregate(ctx, name, body)
        elif iface_type == 'IF_ETHERNET':
            if ctx.dig(*(base + ('ethernet',))) is not None:
                _ethernet(ctx, name, node, body)
            else:
                _plain_ethernet(ctx, name, body)
        elif iface_type == 'IF_LOOPBACK':
            _loopback(ctx, name, body)
        elif iface_type == 'IF_ROUTED_VLAN':
            _routed_vlan(ctx, name, body)
        else:
            ctx.unsupported(base, 'interface type %r has no implemented mapping; interface not emitted'
                            % iface_type)
            ctx.ignored_paths.add(tuple(str(p) for p in base))
            continue
        if body:
            group.append('interface %s' % cli)
            group.extend(body)
