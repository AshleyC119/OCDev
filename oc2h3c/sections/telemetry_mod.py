"""MOD telemetry mapping (``system/mod``).

The reference renders the ``telemetry mod`` view.  The applied flow group and the
entered MOD view are fixed device keywords (the OC document has no flow-group
model), the drop reasons come from ``system/mod/telemetry/config/drop-reasons``
in document order, and the device id / reporting interval come from the same
telemetry config.
"""
MOD = ('system', 'mod')
MOD_TELEMETRY = MOD + ('telemetry', 'config')

# Values documented by the selected H3C command reference (table 1-2 of the MOD
# section).  The development reference also uses values from a later release.
DOCUMENTED_REASONS = frozenset((
    'denied-vlan',
    'dip-miss',
    'inbound-ttl',
    'invalid-tpid',
    'ip-multicast-error',
    'l3-header-error',
    'mmu-drop',
    'parity-error',
    'smac-zero',
    'source-miss',
    'tunnel-header-error',
))


def _drop_reasons(ctx):
    node = ctx.dig(*(MOD_TELEMETRY + ('drop-reasons',)))
    reasons = []
    if isinstance(node, list):
        for index in range(len(node)):
            value = ctx.val(*(MOD_TELEMETRY + ('drop-reasons', str(index))))
            if value is not None:
                reasons.append(value)
    elif node is not None:
        value = ctx.val(*(MOD_TELEMETRY + ('drop-reasons',)))
        if value is not None:
            reasons.append(value)
    return reasons


def _report_unmapped(ctx):
    for key, _node in ctx.items(*MOD):
        if key == 'telemetry':
            continue
        bind = ctx.val(*(MOD + (key, 'config', 'bind-mirror-id')))
        if bind is not None:
            ctx.unsupported(MOD + (key, 'config', 'bind-mirror-id'),
                            'MOD mirror binding %r is not represented by any command in '
                            'the reference MOD section' % bind)


def emit_mod(ctx):
    group = ctx.group()
    _report_unmapped(ctx)

    group.append('telemetry apply flow-group system-defined ip')
    ctx.ambiguous(MOD,
                  'the applied Flow Group name "system-defined ip" is a device-defined '
                  'constant; the OC document has no Flow Group model',
                  'the fixed reference command is emitted before entering MOD view')

    group.append('telemetry mod')
    reasons = _drop_reasons(ctx)
    for reason in reasons:
        group.append('reason-list %s' % reason)

    undocumented = [reason for reason in reasons
                    if reason not in DOCUMENTED_REASONS]
    if undocumented:
        ctx.ambiguous(MOD_TELEMETRY + ('drop-reasons',),
                      'drop reason(s) %s are not documented in the selected H3C command '
                      'reference' % ', '.join(undocumented),
                      'the reference transcript uses them, so they are emitted verbatim '
                      '(release difference of the paired device)')

    device_id = ctx.val(*(MOD_TELEMETRY + ('device-id',)))
    if device_id is not None:
        group.append('device-id %s' % device_id)

    interval = ctx.val(*(MOD_TELEMETRY + ('interval',)))
    if interval is not None:
        group.append('reporting-interval %s' % interval)
        ctx.ambiguous(MOD_TELEMETRY + ('interval',),
                      'the OC leaf is named "interval"; the selected H3C command '
                      'reference for Release 9323 has no reporting-interval command in '
                      'MOD view',
                      'the OC interval is rendered as the reference reporting-interval '
                      'value in seconds')
