"""sFlow and per-flow load-sharing mapping (reference segment 601).

The native block concatenates two feature areas:

* ``ip load-sharing ...`` derived from ``system/hash`` (global ECMP algorithm and
  the outer-hash factor set),
* ``sflow ...`` derived from ``system/sampling/sflow`` (agent/source address from
  the configured source interface, collectors, per-interface sampling).

Fixed CLI keywords/constants that the OC document cannot express are recorded
with ``ctx.ambiguous``.
"""
from . import common

#: Collector text in the native block has no OC counterpart.
COLLECTOR_DESCRIPTION = 'netserver'

#: Outer-hash factors in the order the native commands list them, with the CLI
#: token spelling of each OC factor.  The OC does not carry an order or a CLI
#: token spelling, so both are fixed by this table (reported as ambiguous).
LOAD_SHARING_FACTORS = (
    ('src-ip', 'src-ip'),
    ('src-port', 'src-port'),
    ('dst-ip', 'dest-ip'),
    ('dst-port', 'dest-port'),
    ('protocol', 'ip-pro'),
)


def _interface_ip(ctx, name):
    """Return the first IPv4 address configured on an interface, if any."""
    base = ('interfaces', 'interface', name)
    subinterfaces = ctx.dig(*(base + ('subinterfaces', 'subinterface')))
    if not isinstance(subinterfaces, dict):
        return None
    for index in sorted(subinterfaces):
        addresses = ctx.dig(*(base + ('subinterfaces', 'subinterface', index,
                                     'ipv4', 'addresses', 'address')))
        if not isinstance(addresses, dict):
            continue
        for key in sorted(addresses):
            address = ctx.val(*(base + ('subinterfaces', 'subinterface', index,
                                        'ipv4', 'addresses', 'address', key,
                                        'config', 'ip')))
            if address:
                return address
    return None


def _emit_load_sharing(ctx, group):
    hashed = ('system', 'hash')
    algorithm = ctx.val(*(hashed + ('global', 'config', 'algorithm-ecmp')))
    outer = hashed + ('outer',)
    outer_enabled = ctx.bool_val(*(outer + ('config', 'enable')))
    factors = []
    for oc_key, cli_key in LOAD_SHARING_FACTORS:
        enabled = ctx.bool_val(*(outer + ('factors', 'config', oc_key)))
        if enabled:
            factors.append(cli_key)
    if algorithm is not None:
        group.append('ip load-sharing mode per-flow algorithm %s global' % algorithm)
        ctx.ambiguous(hashed + ('global', 'config', 'algorithm-ecmp'),
                      'per-flow load-sharing ECMP algorithm number is taken from the OC '
                      'hash configuration, but the "per-flow algorithm ... global" '
                      'keyword form is a fixed CLI choice',
                      'algorithm-ecmp is emitted as "per-flow algorithm <n> global"')
    if factors and outer_enabled is not False:
        group.append('ip load-sharing mode per-flow %s global' % ' '.join(factors))
        ctx.ambiguous(outer + ('factors', 'config'),
                      'the OC hash factor set carries no ordering and no CLI token '
                      'spelling; the factor order and the dst-ip->dest-ip / '
                      'protocol->ip-pro spellings are fixed by the translator table',
                      'factor order src-ip, src-port, dest-ip, dest-port, ip-pro')
    if isinstance(ctx.dig(*(outer + ('factors', 'config'))), dict) and \
            outer_enabled is False:
        ctx.ignored(outer + ('factors', 'config'),
                    'outer-hash factors are configured but outer hashing is disabled; '
                    'no load-sharing command is emitted')
    # Hash features with no command in the emitted configuration style.
    for area, message in (
            ('inner', 'inner-header hash configuration has no emitted CLI command; '
                      'input left unrepresented'),
            ('dhash', 'dynamic hash (dhash) group configuration has no implemented '
                      'mapping; input left unrepresented'),
            ('dlb', 'dynamic load-balancing (DLB) configuration has no implemented '
                    'mapping; input left unrepresented')):
        if isinstance(ctx.dig(*(hashed + (area,))), dict):
            ctx.unsupported(hashed + (area,), message)


def _emit_sflow(ctx, group):
    base = ('system', 'sampling', 'sflow')
    if not isinstance(ctx.dig(*base), dict):
        return
    enabled = ctx.bool_val(*(base + ('config', 'enable')))
    if enabled is False:
        ctx.ignored(base + ('config', 'enable'),
                    'sFlow is globally disabled; no sFlow commands are emitted')
        return
    for field, message in (
            ('datagram-size', 'sFlow datagram size has no implemented CLI mapping; '
                              'input left unrepresented'),
            ('cpu-rate-limit', 'sFlow CPU rate limit has no implemented CLI mapping; '
                               'input left unrepresented')):
        value = ctx.val(*(base + ('config', field)))
        if value is not None:
            ctx.unsupported(base + ('config', field), message)
    source_interface = ctx.val(*(base + ('config', 'source-interface')))
    if source_interface:
        address = _interface_ip(ctx, source_interface)
        if address:
            group.append('sflow agent ip %s' % address)
            group.append('sflow source ip %s' % address)
            ctx.ambiguous(base + ('config', 'source-interface'),
                          'the OC names only a source interface; the agent address and '
                          'the source address are both taken from the first IPv4 address '
                          'of that interface, and the "agent ip"/"source ip" command split '
                          'is a fixed CLI choice',
                          'address of source-interface %r used for both commands'
                          % source_interface)
        else:
            ctx.error(base + ('config', 'source-interface'),
                      'source interface %r has no IPv4 address in the OC document; '
                      'sflow agent/source commands not emitted' % source_interface)
    # Collectors: one command per collector server, in collector-id / address order.
    emitted_collector = False
    for collector_id, _node in sorted(ctx.items(*(base + ('collectors', 'collector')))):
        cnode = base + ('collectors', 'collector', collector_id)
        ctx.ignored(cnode + ('name',), 'duplicate of the collector map key')
        servers = ctx.dig(*(cnode + ('servers', 'server')))
        for address_key in sorted(servers or {}):
            snode = cnode + ('servers', 'server', address_key)
            address = ctx.val(*(snode + ('config', 'address')), default=address_key)
            port = ctx.val(*(snode + ('config', 'port')))
            ctx.ignored(snode + ('address',), 'duplicate of config/address')
            if port is None:
                ctx.error(snode + ('config', 'port'),
                          'collector server has no UDP port; command not emitted')
                continue
            group.append('sflow collector %s  ip %s port %s   description %s'
                         % (collector_id, address, port, COLLECTOR_DESCRIPTION))
            emitted_collector = True
    if emitted_collector:
        ctx.ambiguous(base + ('collectors',),
                      'the collector description text has no OC counterpart; it is a '
                      'fixed translator constant',
                      'description %r emitted for every collector' % COLLECTOR_DESCRIPTION)
    # Per-interface sampling, in interface-name order.
    interfaces = base + ('interfaces', 'interface')
    for name in sorted(ctx.dig(*interfaces) or {}):
        node = interfaces + (name,)
        config = node + ('config',)
        on = ctx.bool_val(*(config + ('enable',)))
        rate = ctx.val(*(config + ('sample-rate',)))
        direction = ctx.val(*(config + ('direction',)))
        collector = ctx.val(*(config + ('name',)))
        ctx.ignored(node + ('name',), 'duplicate of the interface map key')
        if on is False:
            ctx.ignored(node,
                        'sFlow is disabled on this interface; no sampling commands '
                        'are emitted')
            continue
        group.append('interface %s' % name)
        if collector is not None:
            group.append('sflow flow collector %s' % collector)
        if rate is not None:
            group.append('sflow sampling-rate %s' % rate)
        if direction is not None:
            group.append('sflow sampling-direction %s' % direction)


def emit_sflow(ctx):
    group = ctx.group()
    _emit_load_sharing(ctx, group)
    _emit_sflow(ctx, group)
