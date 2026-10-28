"""BFD interface timers and routing-policy mapping (reference segment 401).

The native segment concatenates two blocks inside one ``system-view`` group:

* per-interface BFD timers from ``bfd/interfaces`` (interface-name order),
* route-policy nodes from ``routing-policy/policy-definitions`` followed by the
  community lists and prefix lists they reference (name order).

Fixed protocol keywords/formats that the OC cannot express are reported with
``ctx.ambiguous``; defined sets that carry no CLI representation are reported
with ``ctx.ignored``.
"""
from . import common

#: Default prefix-list sequence number when the OC entry carries none.  The OC
#: has no sequence-id for some prefix entries and the native form always shows an
#: explicit index (reported as ambiguous).
PREFIX_DEFAULT_INDEX = 5

#: OC route-policy result -> native node keyword.
NODE_ACTION = {
    'ACCEPT_ROUTE': 'permit',
    'REJECT_ROUTE': 'deny',
}


def _emit_bfd(ctx, group):
    base = ('bfd', 'interfaces', 'interface')
    for name in sorted(ctx.dig(*base) or {}):
        node = base + (name,)
        config = node + ('config',)
        multiplier = ctx.val(*(config + ('detection-multiplier',)))
        tx_interval = ctx.val(*(config + ('desired-minimum-tx-interval',)))
        rx_interval = ctx.val(*(config + ('required-minimum-receive',)))
        enabled = ctx.bool_val(*(config + ('enabled',)))
        ctx.ignored(node + ('id',), 'duplicate of the interface map key')
        if enabled is False:
            ctx.ignored(node, 'BFD is disabled on this interface; no commands emitted')
            continue
        group.append('interface %s' % common.cli_name(name))
        if multiplier is not None:
            group.append('bfd detect-multiplier %s' % multiplier)
        if tx_interval is not None:
            group.append('bfd min-transmit-interval %s' % tx_interval)
        if rx_interval is not None:
            group.append('bfd min-receive-interval %s' % rx_interval)


def _route_references(ctx):
    """Collect prefix sets / community sets referenced by route-policy conditions."""
    prefix_refs = set()
    community_refs = set()
    policies = ('routing-policy', 'policy-definitions', 'policy-definition')
    for name in ctx.dig(*policies) or {}:
        statements = ctx.dig(*(policies + (name, 'statements', 'statement')))
        for statement in statements or {}:
            conditions = policies + (name, 'statements', 'statement', statement,
                                     'conditions')
            prefix = ctx.val(*(conditions + ('match-prefix-set', 'config',
                                            'prefix-set')))
            if prefix:
                prefix_refs.add(prefix)
            community = ctx.val(*(conditions + ('bgp-conditions', 'config',
                                                'community-set')))
            if community:
                community_refs.add(community)
    return prefix_refs, community_refs


def _statement_key(name):
    return (0, int(name)) if str(name).isdigit() else (1, str(name))


def _if_match_lines(ctx, statement_base):
    """Return the if-match clause lines for one route-policy statement."""
    lines = []
    conditions = statement_base + ('conditions',)
    community_set = ctx.val(*(conditions + ('bgp-conditions', 'config',
                                            'community-set')))
    interface = ctx.val(*(conditions + ('match-interface', 'config', 'interface')))
    prefix_set = ctx.val(*(conditions + ('match-prefix-set', 'config', 'prefix-set')))
    if community_set:
        if str(community_set).isdigit():
            lines.append('if-match community %s' % community_set)
        else:
            lines.append('if-match community name %s' % community_set)
    if interface:
        lines.append('if-match interface %s' % interface)
    if prefix_set:
        lines.append('if-match ip address prefix-list %s' % prefix_set)
    return lines


def _apply_lines(ctx, statement_base):
    """Return the apply clause lines for one route-policy statement."""
    lines = []
    actions = statement_base + ('actions',)
    bgp_actions = actions + ('bgp-actions',)
    communities = ctx.dig(*(bgp_actions + ('set-community', 'inline', 'config',
                                           'communities')))
    if isinstance(communities, list) and communities:
        ctx.used.add(tuple(str(part) for part in bgp_actions
                          + ('set-community', 'inline', 'config', 'communities')))
        lines.append('apply community  %s'
                     % ' '.join(str(value) for value in communities))
    med = ctx.val(*(bgp_actions + ('config', 'set-med')))
    if med is not None:
        lines.append('apply cost %s' % med)
    weight = ctx.val(*(bgp_actions + ('config', 'set-weight')))
    if weight is not None:
        # The native block keeps a leading space in front of this clause.
        lines.append(' apply preferred-value %s' % weight)
    return lines


def _emit_policies(ctx, group):
    policies = ('routing-policy', 'policy-definitions', 'policy-definition')
    for name in sorted(ctx.dig(*policies) or {}):
        node = policies + (name,)
        ctx.ignored(node + ('name',), 'duplicate of the policy-definition map key')
        ctx.ignored(node + ('config', 'name'),
                    'duplicate of the policy-definition map key')
        statements = ctx.dig(*(node + ('statements', 'statement')))
        for statement in sorted(statements or {}, key=_statement_key):
            sbase = node + ('statements', 'statement', statement)
            ctx.ignored(sbase + ('name',), 'duplicate of the statement map key')
            ctx.ignored(sbase + ('config', 'name'),
                        'duplicate of the statement map key')
            result = ctx.val(*(sbase + ('actions', 'config', 'policy-result')))
            action = NODE_ACTION.get(result)
            if action is None:
                ctx.unsupported(sbase + ('actions', 'config', 'policy-result'),
                                'unsupported route-policy result %r; node %s of policy '
                                '%r not emitted' % (result, statement, name))
                continue
            group.append('route-policy %s %s node %s' % (name, action, statement))
            for line in _if_match_lines(ctx, sbase):
                group.append(line)
            for line in _apply_lines(ctx, sbase):
                group.append(line)


def _emit_community_lists(ctx, group, referenced):
    sets = ('routing-policy', 'defined-sets', 'bgp-defined-sets', 'community-sets',
            'community-set')
    for name in sorted(ctx.dig(*sets) or {}):
        node = sets + (name,)
        if name not in referenced:
            ctx.ignored(node,
                        'community set is not referenced by any route-policy '
                        'condition; no community list is emitted for it')
            continue
        ctx.ignored(node + ('community-set-name',),
                    'duplicate of the community-set map key')
        ctx.ignored(node + ('config', 'community-set-name'),
                    'duplicate of the community-set map key')
        action = ctx.val(*(node + ('config', 'forwarding-action')))
        members = ctx.dig(*(node + ('config', 'community-member')))
        ctx.used.add(tuple(str(part) for part in node + ('config',
                                                         'community-member')))
        if not isinstance(members, list):
            continue
        for member in members:
            if str(name).isdigit():
                group.append('ip community-list %s %s %s'
                             % (name, action or 'permit', member))
            else:
                group.append('ip community-list basic %s %s %s'
                             % (name, action or 'permit', member))


def _prefix_range_clause(ctx, parts, masklength_range):
    if masklength_range is None:
        return ''
    text = str(masklength_range)
    if '..' in text:
        low, high = text.split('..', 1)
        return 'greater-equal %s less-equal %s ' % (low, high)
    if text.isdigit():
        return 'greater-equal %s ' % text
    if text == 'exact':
        ctx.ambiguous(parts,
                      'the OC marks the prefix mask length as exact; the native form '
                      'expresses exact matching by leaving out greater-equal/less-equal',
                      'no range keywords emitted for exact matching')
        return ''
    ctx.ambiguous(parts,
                  'unsupported prefix mask-length range %r; no range keywords emitted'
                  % text,
                  'no range keywords emitted')
    return ''


def _emit_prefix_lists(ctx, group, referenced):
    sets = ('routing-policy', 'defined-sets', 'prefix-sets', 'prefix-set')
    for name in sorted(ctx.dig(*sets) or {}):
        node = sets + (name,)
        if name not in referenced:
            ctx.ignored(node,
                        'prefix set is not referenced by any route-policy condition; '
                        'no prefix list is emitted for it')
            continue
        ctx.ignored(node + ('name',), 'duplicate of the prefix-set map key')
        ctx.ignored(node + ('config', 'name'),
                    'duplicate of the prefix-set map key')
        mode = ctx.val(*(node + ('config', 'mode')))
        if mode is not None:
            ctx.ignored(node + ('config', 'mode'),
                        'prefix-set address-family mode %r is implied by the emitted '
                        'IPv4 prefix list' % mode)
        prefixes = ctx.dig(*(node + ('prefixes', 'prefix')))
        entries = []
        for key in (prefixes or {}):
            entry = node + ('prefixes', 'prefix', key)
            sequence = ctx.val(*(entry + ('config', 'sequence-id')))
            if sequence is None:
                index = PREFIX_DEFAULT_INDEX
                ctx.ambiguous(entry,
                              'the OC prefix entry has no sequence-id; the native '
                              'form always shows an explicit index',
                              'default index %d emitted' % PREFIX_DEFAULT_INDEX)
            else:
                try:
                    index = int(sequence)
                except (TypeError, ValueError):
                    ctx.error(entry + ('config', 'sequence-id'),
                              'prefix entry has a non-numeric sequence-id %r; '
                              'entry not emitted' % sequence)
                    continue
            entries.append((index, key, entry))
        for index, key, entry in sorted(entries):
            action = ctx.val(*(entry + ('actions', 'config', 'policy-result')))
            prefix = ctx.val(*(entry + ('config', 'ip-prefix')))
            masklength_range = ctx.val(*(entry + ('config', 'masklength-range')))
            ctx.ignored(entry + ('masklength-range',),
                        'duplicate of config/masklength-range')
            ctx.ignored(entry + ('ip-prefix',), 'duplicate of config/ip-prefix')
            ctx.ignored(entry + ('ip-prefix,masklength-range',),
                        'combined prefix/range key duplicate')
            if not prefix:
                ctx.error(entry, 'prefix entry has no ip-prefix; entry not emitted')
                continue
            try:
                address, length = common.ip_and_len(prefix)
            except ValueError as exc:
                ctx.error(entry + ('config', 'ip-prefix'),
                          'malformed prefix %r: %s; entry not emitted' % (prefix, exc))
                continue
            if action is None:
                action = 'permit'
                ctx.ambiguous(entry,
                              'the OC prefix entry carries no policy result; the native '
                              'form always names permit/deny',
                              'permit emitted as the default action')
            group.append('ip prefix-list %s index %d  %s %s  %d  %s'
                         % (name, index, action, address, length,
                            _prefix_range_clause(ctx, entry + ('config',
                                                               'masklength-range'),
                                                 masklength_range)))


def emit_bfd_and_routing(ctx):
    group = ctx.group()
    _emit_bfd(ctx, group)
    group.append('system-view')
    group.append('#')
    prefix_refs, community_refs = _route_references(ctx)
    _emit_policies(ctx, group)
    _emit_community_lists(ctx, group, community_refs)
    _emit_prefix_lists(ctx, group, prefix_refs)
    ctx.ambiguous(('routing-policy', 'policy-definitions'),
                  'the OC condition/action containers carry no ordering; the if-match '
                  'order (community, interface, prefix-list) and the apply order '
                  '(community, cost, preferred-value) are fixed by the translator',
                  'stable clause order defined by this mapping')
    ctx.ambiguous(('routing-policy', 'defined-sets'),
                  'defined sets that no route-policy condition references are not '
                  'emitted; the native configuration style only carries referenced '
                  'sets',
                  'dangling defined sets reported and omitted')
    ctx.ambiguous(('routing-policy', 'policy-definitions'),
                  'BGP set-med is emitted as "apply cost" and set-weight as '
                  '"apply preferred-value"; these are fixed protocol key/token '
                  'equivalences',
                  'set-med -> apply cost, set-weight -> apply preferred-value')
