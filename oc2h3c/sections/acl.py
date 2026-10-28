"""Basic (control-plane) ACL mapping.

The OC document carries no ACL numbers; the native reference numbers the basic
ACLs in the 2000-2999 range.  Numbering is therefore a translator policy:
allocation follows the document order of ACL sets, emission follows the ACL set
key order.  This is recorded as an ambiguity in the report.
"""
from . import common

BASIC_TYPE = 'ACL_CTRL'
BASIC_RANGE_START = 2000


def _sets(ctx):
    return ctx.items('acl', 'acl-sets', 'acl-set')


def _allocate(ctx):
    """Map (set_key, acl_name) -> ACL number, in document order of basic ACLs."""
    numbers = {}
    index = 0
    for key, _node in _sets(ctx):
        acl_type = ctx.val('acl', 'acl-sets', 'acl-set', key, 'config', 'type')
        if acl_type == BASIC_TYPE:
            numbers[key] = BASIC_RANGE_START + index
            index += 1
    return numbers


def _rule_line(seq, action, vrf, source):
    if vrf is None:
        prefix = 'rule %s %s  ' % (seq, action)
    else:
        prefix = 'rule %s %s  vpn-instance %s' % (seq, action, vrf)
    if source in (None, 'any'):
        return prefix + '    '
    addr, length = common.ip_and_len(source)
    return '%s source %s %s    ' % (prefix, addr, common.wildcard_mask(length))


def _emit_set(ctx, key, number, group):
    base = ('acl', 'acl-sets', 'acl-set', key)
    name = ctx.val(*(base + ('config', 'name')))
    description = ctx.val(*(base + ('config', 'description')))
    group.append('acl number %d ' % number)
    group.append('acl basic %d' % number)
    if description:
        group.append('description %s' % description)
    entries = []
    entry_map = ctx.dig(*(base + ('acl-entries', 'acl-entry')))
    if isinstance(entry_map, dict):
        for entry_key in entry_map:
            seq_raw = ctx.val(*(base + ('acl-entries', 'acl-entry', entry_key, 'sequence-id')),
                              default=entry_key)
            try:
                seq = int(seq_raw)
            except (TypeError, ValueError):
                ctx.error(base + ('acl-entries', 'acl-entry', entry_key),
                          'ACL entry has non-numeric sequence id %r' % seq_raw)
                continue
            entries.append((seq, entry_key))
    for seq, entry_key in sorted(entries):
        ebase = base + ('acl-entries', 'acl-entry', entry_key)
        action = ctx.val(*(ebase + ('actions', 'config', 'forwarding-action')))
        vrf = ctx.val(*(ebase + ('network-instance', 'config', 'name')))
        source = ctx.val(*(ebase + ('ipv4', 'config', 'source-address')))
        destination = ctx.val(*(ebase + ('ipv4', 'config', 'destination-address')))
        protocol = ctx.val(*(ebase + ('ipv4', 'config', 'protocol')))
        if action not in ('permit', 'deny'):
            ctx.unsupported(ebase + ('actions', 'config', 'forwarding-action'),
                            'unsupported ACL forwarding action %r; rule %d not emitted'
                            % (action, seq))
            continue
        if destination not in (None, 'any'):
            ctx.unsupported(ebase + ('ipv4', 'config', 'destination-address'),
                            'ACL destination matching not supported; rule %d not emitted' % seq)
            continue
        if protocol not in (None, 'ip'):
            ctx.ignored(ebase + ('ipv4', 'config', 'protocol'),
                        'ACL protocol field %r has no effect in the emitted basic rule' % protocol)
        ctx.ignored(ebase + ('transport', 'config'),
                    'ACL source/destination ports are not represented in the emitted basic rule')
        group.append(_rule_line(seq, action, vrf, source))


def emit_acls(ctx):
    numbers = _allocate(ctx)
    group = ctx.group()
    if not numbers:
        return
    for key in sorted(numbers):
        acl_type = ctx.val('acl', 'acl-sets', 'acl-set', key, 'config', 'type')
        number = numbers[key]
        _emit_set(ctx, key, number, group)
        ctx.ambiguous(('acl', 'acl-sets', 'acl-set', key),
                      'ACL number %d for type %s is not present in the OC document; '
                      'assigned by translator policy (basic ACLs numbered from %d in document order)'
                      % (number, acl_type, BASIC_RANGE_START),
                      'deterministic allocation: %d + index among %s sets in document order'
                      % (BASIC_RANGE_START, BASIC_TYPE))
    # ACL sets with an unsupported type are reported, not emitted.
    for key, _node in _sets(ctx):
        acl_type = ctx.val('acl', 'acl-sets', 'acl-set', key, 'config', 'type')
        if acl_type != BASIC_TYPE:
            ctx.unsupported(('acl', 'acl-sets', 'acl-set', key),
                            'ACL set type %r has no implemented mapping; not emitted' % acl_type)
    reserved = ctx.dig('acl', 'interfaces')
    if reserved:
        ctx.unsupported(('acl', 'interfaces'),
                        'ACL interface bindings are not mapped; input left unrepresented')
    group.append('system-view')
    group.append('#')
