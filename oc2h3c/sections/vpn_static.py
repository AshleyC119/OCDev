"""VRF instances, management-VRF bindings and static routes."""
from . import common


def _vrf_instances(ctx):
    entries = []
    for name, node in ctx.items('network-instances', 'network-instance'):
        vrf_type = ctx.val('network-instances', 'network-instance', name, 'config', 'type')
        entries.append((name, vrf_type))
    return sorted(entries)


def emit_vpn_instances(ctx):
    emitted = False
    for name, vrf_type in _vrf_instances(ctx):
        if vrf_type != 'L3VRF':
            continue
        group = ctx.group()
        emitted = True
        rd = ctx.val('network-instances', 'network-instance', name, 'config', 'route-distinguisher')
        group.append('ip vpn-instance %s' % name)
        if rd:
            group.append('route-distinguisher %s' % rd)
        else:
            ctx.unsupported(('network-instances', 'network-instance', name, 'config'),
                            'VRF %r has no route-distinguisher; route-distinguisher not emitted' % name)
    if not emitted:
        ctx.group()


def emit_mgmt_bindings(ctx):
    emitted = False
    for vrf, vrf_type in _vrf_instances(ctx):
        if vrf_type != 'L3VRF':
            continue
        for ifname in common.sorted_names(ctx, 'network-instances', 'network-instance', vrf,
                                          'interfaces', 'interface'):
            iface_id = ctx.val('network-instances', 'network-instance', vrf, 'interfaces',
                               'interface', ifname, 'id', default=ifname)
            group = ctx.group()
            emitted = True
            group.append('interface %s' % common.cli_name(iface_id))
            group.append('ip binding vpn-instance %s' % vrf)
    if not emitted:
        ctx.group()


def _static_protocols(ctx):
    """Yield (vrf, protocol_node_name) for STATIC protocol instances."""
    for vrf, vrf_type in _vrf_instances(ctx):
        if vrf_type not in ('L3VRF', 'DEFAULT_INSTANCE'):
            continue
        for proto in common.sorted_names(ctx, 'network-instances', 'network-instance', vrf,
                                         'protocols', 'protocol'):
            ident = ctx.val('network-instances', 'network-instance', vrf, 'protocols',
                            'protocol', proto, 'identifier')
            if ident == 'STATIC':
                yield vrf, proto, vrf_type


def _static_route_lines(ctx, vrf, proto, vrf_type):
    base = ('network-instances', 'network-instance', vrf, 'protocols', 'protocol', proto,
            'static-routes', 'static')
    route_prefixes = []
    for prefix in ctx.dig(*base) or {}:
        route_prefixes.append(prefix)
    for prefix in sorted(route_prefixes, key=common.ip_sort_key):
        addr, length = common.ip_and_len(prefix) if '/' in prefix else (prefix, 32)
        desc = ctx.val(*(base + (prefix, 'config', 'description')))
        hops = []
        for hop_id in (ctx.dig(*(base + (prefix, 'next-hops', 'next-hop'))) or {}):
            hop = base + (prefix, 'next-hops', 'next-hop', hop_id)
            next_hop = ctx.val(*(hop + ('config', 'next-hop')))
            metric = ctx.val(*(hop + ('config', 'metric')))
            iface = ctx.val(*(hop + ('interface-ref', 'config', 'interface')))
            hops.append((hop_id, next_hop, metric, iface))
        for hop_id, next_hop, metric, iface in sorted(hops):
            parts = ['ip route-static']
            if vrf_type == 'L3VRF':
                parts.extend(['vpn-instance', vrf])
            parts.extend([addr, str(length)])
            if iface:
                parts.append(common.cli_name(iface))
            if next_hop:
                parts.append(next_hop)
            line = ' '.join(parts)
            if metric:
                line += '  preference %s' % metric
            if desc:
                line += ' description %s' % desc
            yield line


def emit_static_routes(ctx):
    lines = []
    for vrf, proto, vrf_type in _static_protocols(ctx):
        lines.extend(_static_route_lines(ctx, vrf, proto, vrf_type))
    if lines:
        group = ctx.group()
        group.extend(lines)
    else:
        ctx.group()
