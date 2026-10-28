"""BGP mapping (reference segment 402).

Emits the BGP process, peer groups, neighbors and the IPv4-unicast address
family in the native order: process/global options, peer groups, neighbors,
then ``address-family ipv4 unicast`` with redistribution, multipath, preference,
additional-paths, ``network`` statements and the per-peer-group AF commands.

Values come from ``network-instances/network-instance/*/protocols/protocol``
(BGP).  Fixed keywords and translator policy constants are recorded with
``ctx.ambiguous``.
"""
from . import common

#: OC BGP peer type -> native peer-group keyword.
PEER_TYPE = {
    'EXTERNAL': 'external',
    'INTERNAL': 'internal',
}

#: OC route-source identity -> native import-route keyword.
IMPORT_PROTOCOL = {
    'DIRECTLY_CONNECTED': 'direct',
    'STATIC': 'static',
    'BGP': 'bgp',
    'OSPF': 'ospf',
    'ISIS': 'isis',
    'RIP': 'rip',
}

#: The OC add-paths send-max has no native counterpart in the emitted block; the
#: select-best value is a fixed translator constant (reported as ambiguous).
SELECT_BEST = 16

#: Interactive confirmation answer the native CLI expects after enabling a peer
#: in the address family and after making it a next hop.  The OC cannot express
#: the terminal interaction, so the answer line is a fixed artifact.
PROMPT_ANSWER = 'Y'


def _find_bgp(ctx):
    """Return the protocol node path of the first BGP protocol instance."""
    instances = ('network-instances', 'network-instance')
    for vrf in sorted(ctx.dig(*instances) or {}):
        protocols = instances + (vrf, 'protocols', 'protocol')
        for key in sorted(ctx.dig(*protocols) or {}):
            node = protocols + (key,)
            identifier = ctx.val(*(node + ('identifier',)))
            if identifier != 'BGP':
                continue
            # Identity duplicates of the protocol instance map key.
            ctx.ignored(node + ('name,identifier',), 'combined identity key duplicate')
            ctx.ignored(node + ('name',), 'duplicate of the protocol map key')
            ctx.ignored(node + ('config', 'identifier'),
                        'duplicate of the protocol identifier')
            ctx.ignored(node + ('config', 'name'), 'duplicate of the protocol map key')
            return node
    return None


def _emit_process(ctx, group, bgp):
    """Emit bgp/global and return the local AS number (or None)."""
    global_node = bgp + ('global',)
    config = global_node + ('config',)
    local_as = ctx.val(*(config + ('as',)))
    router_id = ctx.val(*(config + ('router-id',)))
    if local_as is None:
        ctx.error(config, 'BGP instance has no local AS number; process block not emitted')
        return None
    group.append('bgp %s' % local_as)
    if router_id:
        group.append('router-id %s' % router_id)
    delay = global_node + ('startup-update-delay', 'config')
    if isinstance(ctx.dig(*delay), dict):
        enabled = ctx.bool_val(*(delay + ('enable',)))
        time = ctx.val(*(delay + ('time',)))
        if enabled and time is not None:
            group.append('bgp update-delay on-startup %s' % time)
    advertise = global_node + ('advertise-delay', 'config')
    if isinstance(ctx.dig(*advertise), dict):
        time = ctx.val(*(advertise + ('time',)))
        if time is not None:
            ctx.unsupported(advertise + ('time',),
                            'the OC BGP advertise-delay has no implemented CLI '
                            'mapping; input left unrepresented')
    always_compare = ctx.bool_val(*(global_node + ('route-selection-options', 'config',
                                                   'always-compare-med')))
    if always_compare:
        group.append('compare-different-as-med')
        ctx.ambiguous(global_node + ('route-selection-options', 'config',
                                     'always-compare-med'),
                      'OC "always-compare-med" is emitted as the native '
                      '"compare-different-as-med" command; fixed keyword equivalence',
                      'always-compare-med -> compare-different-as-med')
    return local_as


def _group_kind(ctx, gnode, local_as, kinds):
    """Return the native external/internal keyword for a peer group (cached)."""
    if gnode in kinds:
        return kinds[gnode]
    config = gnode + ('config',)
    peer_type = ctx.val(*(config + ('peer-type',)))
    if peer_type is not None:
        kind = PEER_TYPE.get(peer_type)
        if kind is None:
            ctx.unsupported(config + ('peer-type',),
                            'unsupported BGP peer type %r; external emitted' % peer_type)
            kind = 'external'
        kinds[gnode] = kind
        return kind
    peer_as = ctx.val(*(config + ('peer-as',)))
    if peer_as is not None and local_as is not None and str(peer_as) == str(local_as):
        kind = 'internal'
    else:
        kind = 'external'
    kinds[gnode] = kind
    ctx.ambiguous(gnode,
                  'the peer group carries no peer-type; it is inferred from the peer '
                  'AS number (equal to the local AS means internal)',
                  '%s inferred from peer-as %r' % (kind, peer_as))
    return kind


def _emit_peer_groups(ctx, group, bgp, local_as, kinds):
    groups = bgp + ('peer-groups', 'peer-group')
    for name in sorted(ctx.dig(*groups) or {}):
        gnode = groups + (name,)
        config = gnode + ('config',)
        ctx.ignored(gnode + ('peer-group-name',),
                    'duplicate of the peer-group map key')
        ctx.ignored(config + ('peer-group-name',), 'duplicate of the peer-group map key')
        kind = _group_kind(ctx, gnode, local_as, kinds)
        peer_as = ctx.val(*(config + ('peer-as',)))
        group.append('group %s %s' % (name, kind))
        if peer_as is not None and str(peer_as) != str(local_as):
            group.append('peer %s as-number %s' % (name, peer_as))
        elif peer_as is not None:
            ctx.ignored(config + ('peer-as',),
                        'peer AS number equals the local AS; the native iBGP peer '
                        'group does not repeat it')
        bfd = ctx.bool_val(*(gnode + ('enable-bfd', 'config', 'enabled')))
        if bfd:
            group.append('peer %s bfd' % name)
        interval = ctx.val(*(gnode + ('timers', 'config',
                                      'minimum-advertisement-interval')))
        if interval is not None:
            group.append('peer %s route-update-interval %s' % (name, interval))
        password = ctx.val(*(config + ('auth-password',)))
        if password is not None:
            group.append('peer %s password simple %s' % (name, password))
            ctx.ambiguous(config + ('auth-password',),
                          'the OC carries only the password text; the native command '
                          'needs a storage keyword and "simple" (plaintext) is the '
                          'fixed choice',
                          'password simple emitted')
        ctx.ignored(config + ('send-community',),
                    'send-community is emitted as advertise-community in the address '
                    'family, once per peer group')
        addpath = ctx.val(*(config + ('addpath-tx-all-paths',)))
        if addpath is not None:
            ctx.ignored(config + ('addpath-tx-all-paths',),
                        'the send-all-paths flag is emitted per address family from '
                        'the AF add-paths settings')


def _emit_neighbors(ctx, group, bgp):
    neighbors = bgp + ('neighbors', 'neighbor')
    for address in sorted(ctx.dig(*neighbors) or {}):
        node = neighbors + (address,)
        config = node + ('config',)
        group_name = ctx.val(*(config + ('peer-group',)))
        update_source = ctx.val(*(config + ('update-source',)))
        local_interface = ctx.val(*(node + ('transport', 'config', 'local-interface')))
        description = ctx.val(*(config + ('description',)))
        ctx.ignored(node + ('neighbor-address',),
                    'duplicate of the neighbor map key')
        ctx.ignored(config + ('neighbor-address',),
                    'duplicate of the neighbor map key')
        if group_name is not None:
            group.append('peer %s group %s' % (address, group_name))
        interface = update_source or local_interface
        if interface is not None:
            group.append('peer %s connect-interface %s' % (address, interface))
        if update_source is not None and local_interface is not None:
            ctx.ignored(node + ('transport', 'config', 'local-interface'),
                        'duplicate of config/update-source')
        if description is not None:
            group.append('peer %s description %s' % (address, description))
        if ctx.dig(*(node + ('afi-safis',))) is not None:
            ctx.ignored(node + ('afi-safis',),
                        'the per-neighbor AFI-SAFI entry carries the neighbor address '
                        'instead of an AFI/SAFI name and is inherited from the peer '
                        'group; not emitted')
        for field, message in (
                ('peer-type', 'peer type is emitted once per peer group; the '
                              'per-neighbor value is inherited and not repeated'),
                ('send-community', 'advertise-community is emitted once per peer '
                                   'group; the per-neighbor value is inherited'),
                ('addpath-tx-all-paths', 'send-all-paths is emitted per address '
                                         'family; the per-neighbor value is inherited')):
            value = ctx.val(*(config + (field,)))
            if value is not None:
                ctx.ignored(config + (field,), message)
        if ctx.dig(*(node + ('route-reflector',))) is not None:
            ctx.ignored(node + ('route-reflector',),
                        'neighbor route-reflector-client duplicates the peer-group '
                        'setting, which is emitted in the address family; not repeated')


def _multipath_lines(ctx, group, af):
    multipath = af + ('use-multiple-paths',)
    enabled = ctx.bool_val(*(multipath + ('config', 'enabled')))
    ebgp = multipath + ('ebgp', 'config')
    maximum = ctx.val(*(ebgp + ('maximum-paths',)))
    relax = ctx.bool_val(*(ebgp + ('balance-as-path-relax',)))
    if maximum is not None and enabled is not False:
        group.append('balance %s' % maximum)
    distance = af + ('default-route-distance', 'config')
    external = ctx.val(*(distance + ('external-route-distance',)))
    internal = ctx.val(*(distance + ('internal-route-distance',)))
    local = ctx.val(*(distance + ('local-route-distance',)))
    if None not in (external, internal, local):
        group.append('preference %s %s %s' % (external, internal, local))
    if relax:
        group.append('balance  as-path-relax')


def _emit_import_routes(ctx, group, af):
    routes = af + ('ipv4-unicast', 'redistribute-routes', 'redistribute-route')
    for key in sorted(ctx.dig(*routes) or {}):
        node = routes + (key,)
        protocol = ctx.val(*(node + ('config', 'protocol')), default=key)
        keyword = IMPORT_PROTOCOL.get(protocol)
        ctx.ignored(node + ('protocol',), 'duplicate of config/protocol')
        if keyword is None:
            ctx.unsupported(node + ('config', 'protocol'),
                            'unsupported redistribute protocol %r; import-route not '
                            'emitted' % protocol)
            continue
        policies = ctx.dig(*(node + ('config', 'import-policy')))
        if isinstance(policies, list) and policies:
            ctx.used.add(tuple(str(part) for part in node + ('config',
                                                             'import-policy')))
            if len(policies) > 1:
                ctx.ambiguous(node + ('config', 'import-policy'),
                              'the native import-route command accepts a single '
                              'route-policy; the first policy is emitted',
                              'first of %d policies emitted' % len(policies))
            group.append('import-route %s route-policy %s' % (keyword, policies[0]))
        else:
            group.append('import-route %s' % keyword)


def _emit_networks(ctx, group, af):
    advertised = af + ('ipv4-unicast', 'advertise-routes', 'advertise-route')
    lines = []
    for key in ctx.dig(*advertised) or {}:
        node = advertised + (key,)
        prefix = ctx.val(*(node + ('config', 'prefix')), default=key)
        policy = ctx.val(*(node + ('config', 'policy')))
        mode = ctx.val(*(node + ('config', 'mode')))
        ctx.ignored(node + ('prefix',), 'duplicate of config/prefix')
        if mode is not None:
            ctx.ignored(node + ('config', 'mode'),
                        'the OC advertisement mode %r has no counterpart in the '
                        'native network statement' % mode)
        if not prefix:
            ctx.error(node, 'network statement has no prefix; not emitted')
            continue
        try:
            address, length = common.ip_and_len(prefix)
        except ValueError as exc:
            ctx.error(node + ('config', 'prefix'),
                      'malformed network prefix %r: %s; not emitted' % (prefix, exc))
            continue
        line = 'network %s %s' % (address, common.netmask(length))
        if policy:
            line += ' route-policy %s' % policy
        lines.append((common.ip_sort_key(address), line))
    for _key, line in sorted(lines):
        group.append(line)


def _emit_af_peer(ctx, group, group_name, gnode, kinds):
    afs = gnode + ('afi-safis', 'afi-safi')
    for af_name in sorted(ctx.dig(*afs) or {}):
        af = afs + (af_name,)
        if af_name != 'IPV4_UNICAST':
            ctx.unsupported(af, 'peer-group address family %r has no implemented '
                                'mapping; not emitted' % af_name)
            continue
        config = af + ('config',)
        enabled = ctx.bool_val(*(config + ('enabled',)))
        ctx.ignored(af + ('afi-safi-name',), 'duplicate of the AFI-SAFI map key')
        ctx.ignored(config + ('afi-safi-name',),
                    'duplicate of the AFI-SAFI map key')
        if enabled is not False:
            group.append('peer %s enable' % group_name)
            group.append(PROMPT_ANSWER)
            ctx.ambiguous(config + ('enabled',),
                          'the native CLI asks for an interactive confirmation (Y) '
                          'after enabling a peer in the address family; the answer '
                          'line is a fixed artifact',
                          'Y emitted')
        policy = af + ('apply-policy', 'config')
        for direction, field in (('import', 'import-policy'), ('export', 'export-policy')):
            policies = ctx.dig(*(policy + (field,)))
            if not isinstance(policies, list):
                continue
            ctx.used.add(tuple(str(part) for part in policy + (field,)))
            if len(policies) > 1:
                ctx.ambiguous(policy + (field,),
                              'the native command accepts a single route-policy per '
                              'direction; commands are emitted for each OC policy',
                              'all %d policies emitted in list order' % len(policies))
            for route_policy in policies:
                group.append('peer %s route-policy %s %s'
                             % (group_name, route_policy, direction))
        send_community = ctx.bool_val(*(gnode + ('config', 'send-community')))
        if send_community:
            group.append('peer %s advertise-community' % group_name)
        kind = _group_kind(ctx, gnode, None, kinds)
        if kind == 'internal':
            group.append('peer %s next-hop-local' % group_name)
            group.append(PROMPT_ANSWER)
            ctx.ambiguous(gnode,
                          'the OC does not express next-hop-local; it is emitted for '
                          'every internal peer group as a fixed BGP policy, together '
                          'with the interactive confirmation answer',
                          'next-hop-local for internal peer groups')
        reflect = ctx.bool_val(*(gnode + ('route-reflector', 'config',
                                          'route-reflector-client')))
        if reflect:
            # The native block keeps a leading space in front of this clause.
            group.append(' peer %s reflect-client' % group_name)
        addpaths = af + ('add-paths', 'config')
        receive = ctx.bool_val(*(addpaths + ('receive',)))
        send = ctx.bool_val(*(addpaths + ('send',)))
        send_max = ctx.val(*(addpaths + ('send-max',)))
        tokens = []
        if receive:
            tokens.append('receive')
        if send:
            tokens.append('send')
        if tokens:
            group.append('peer %s additional-paths %s'
                         % (group_name, ' '.join(tokens)))
        if send_max is not None:
            ctx.unsupported(addpaths + ('send-max',),
                            'the OC per-AF add-paths send-max has no implemented CLI '
                            'mapping; input left unrepresented')
        distance = af + ('default-route-distance', 'config')
        if isinstance(ctx.dig(*distance), dict):
            for field in ('external-route-distance', 'internal-route-distance',
                          'local-route-distance'):
                ctx.val(*(distance + (field,)))
            ctx.ignored(distance,
                        'the per-peer-group default route distance is not emitted; '
                        'the address-family preference is used')


def _emit_address_families(ctx, group, bgp, kinds):
    global_node = bgp + ('global',)
    afs = global_node + ('afi-safis', 'afi-safi')
    groups = bgp + ('peer-groups', 'peer-group')
    for af_name in sorted(ctx.dig(*afs) or {}):
        af = afs + (af_name,)
        if af_name != 'IPV4_UNICAST':
            ctx.unsupported(af, 'address family %r has no implemented mapping; '
                                'not emitted' % af_name)
            continue
        enabled = ctx.bool_val(*(af + ('config', 'enabled')))
        ctx.ignored(af + ('afi-safi-name',), 'duplicate of the AFI-SAFI map key')
        ctx.ignored(af + ('config', 'afi-safi-name'),
                    'duplicate of the AFI-SAFI map key')
        if enabled is False:
            ctx.ignored(af, 'the address family is disabled; no commands emitted')
            continue
        group.append('address-family ipv4 unicast')
        _emit_import_routes(ctx, group, af)
        _multipath_lines(ctx, group, af)
        send_max = ctx.val(*(af + ('add-paths', 'config', 'send-max')))
        if send_max is not None:
            group.append('additional-paths select-best %d' % SELECT_BEST)
            ctx.ambiguous(af + ('add-paths', 'config', 'send-max'),
                          'the OC add-paths send-max value has no counterpart in the '
                          'emitted command; "additional-paths select-best" is a fixed '
                          'translator constant',
                          'select-best %d emitted' % SELECT_BEST)
            ctx.unsupported(af + ('add-paths', 'config', 'send-max'),
                            'the OC address-family add-paths send-max is not '
                            'represented by the emitted command')
        _emit_networks(ctx, group, af)
        for group_name in sorted(ctx.dig(*groups) or {}):
            _emit_af_peer(ctx, group, group_name, groups + (group_name,), kinds)


def emit_bgp(ctx):
    group = ctx.group()
    node = _find_bgp(ctx)
    if node is None:
        ctx.ignored(('network-instances',),
                    'no BGP protocol instance in the OC document; no BGP block emitted')
        return
    bgp = node + ('bgp',)
    local_as = _emit_process(ctx, group, bgp)
    if local_as is None:
        return
    kinds = {}
    _emit_peer_groups(ctx, group, bgp, local_as, kinds)
    _emit_neighbors(ctx, group, bgp)
    _emit_address_families(ctx, group, bgp, kinds)
