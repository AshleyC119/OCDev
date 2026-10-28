"""Data-buffer thresholds, usage alarms and PFC headroom."""
from . import common

BUFFER = ('components', 'component', 'buffer', 'integrated-circuit', 'chip', 'buffers', 'buffer')


def _queues(ctx, kind, iface, direction):
    base = BUFFER + (kind, 'interfaces', 'interface', iface, direction, 'queues', 'queue')
    names = [q for q in (ctx.dig(*base) or {}) if q.startswith('queue')]
    names.sort(key=lambda q: int(''.join(ch for ch in q if ch.isdigit()) or 0))
    return base, names


def _config(ctx, base, queue, field, default=None):
    return ctx.val(*(base + (queue, 'config', field)), default=default)


def _monitor_config(ctx, field):
    return ctx.val('components', 'component', 'buffer', 'integrated-circuit', 'chip',
                   'buffer-monitor', 'config', field)


def emit_threshold_headroom_alarm(ctx):
    group = ctx.group()
    monitor = ctx.dig('components', 'component', 'buffer', 'integrated-circuit', 'chip',
                      'buffer-monitor', 'config')
    if not isinstance(monitor, dict):
        return
    interval = _monitor_config(ctx, 'suppress-time')
    group.append('buffer threshold alarm headroom enable')
    if interval is not None:
        group.append('buffer threshold alarm headroom interval %s' % interval)
    else:
        ctx.unsupported(('components', 'component', 'buffer', 'integrated-circuit', 'chip',
                         'buffer-monitor', 'config'), 'buffer monitor interval missing')


def _interfaces(ctx, kind):
    base = BUFFER + (kind, 'interfaces', 'interface')
    return common.sorted_names(ctx, *base), base


def emit_headroom_usage(ctx):
    names, _base = _interfaces(ctx, 'HEADROOM')
    for iface in names:
        queued, qnames = _queues(ctx, 'HEADROOM', iface, 'input')
        for qname in qnames:
            alarm = _config(ctx, queued, qname, 'alarm-threshold')
            if alarm is None:
                ctx.unsupported(queued + (qname,), 'headroom queue alarm threshold missing')
                continue
            group = ctx.group()
            group.append('interface %s' % iface)
            group.append('buffer usage threshold headroom queue %s ratio %s'
                         % (_queue_number(qname), alarm))


def _queue_number(qname):
    digits = ''.join(ch for ch in qname if ch.isdigit())
    return int(digits) if digits else 0


def emit_pfc_pool_alarms(ctx):
    group = ctx.group()
    pool = ctx.val(*(BUFFER + ('HEADROOM', 'slices', 'slice', 'sliceall', 'input', 'config',
                               'limit-threshold')))
    if pool is not None:
        group.append('priority-flow-control poolid 0 headroom %s' % pool)
    monitor = ctx.dig('components', 'component', 'buffer', 'integrated-circuit', 'chip',
                      'buffer-monitor', 'config')
    if not isinstance(monitor, dict):
        return
    interval = _monitor_config(ctx, 'suppress-time')
    group.append('buffer threshold alarm egress enable')
    group.append('buffer threshold alarm ingress enable')
    if interval is not None:
        group.append('buffer threshold alarm egress interval %s' % interval)
        group.append('buffer threshold alarm ingress interval %s' % interval)
    else:
        ctx.unsupported(('components', 'component', 'buffer', 'integrated-circuit', 'chip',
                         'buffer-monitor', 'config'), 'buffer monitor interval missing')


def emit_egress_ingress(ctx):
    names, _base = _interfaces(ctx, 'SHARED_BUFFER')
    for iface in names:
        out_base, out_qs = _queues(ctx, 'SHARED_BUFFER', iface, 'output')
        in_base, in_qs = _queues(ctx, 'SHARED_BUFFER', iface, 'input')
        lines = ['interface %s' % iface]
        for qname in out_qs:
            shared = _config(ctx, out_base, qname, 'limit-threshold')
            usage = _config(ctx, out_base, qname, 'alarm-threshold')
            if shared is None or usage is None:
                ctx.unsupported(out_base + (qname,), 'egress buffer threshold missing')
                continue
            lines.append('buffer egress cell queue %s shared ratio %s'
                         % (_queue_number(qname), shared))
            lines.append('buffer egress usage threshold queue %s ratio %s'
                         % (_queue_number(qname), usage))
        for qname in in_qs:
            usage = _config(ctx, in_base, qname, 'alarm-threshold')
            if usage is None:
                ctx.unsupported(in_base + (qname,), 'ingress buffer threshold missing')
                continue
            lines.append('buffer ingress usage threshold queue %s ratio %s'
                         % (_queue_number(qname), usage))
        if len(lines) > 1:
            group = ctx.group()
            group.extend(lines)
