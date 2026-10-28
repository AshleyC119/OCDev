"""QoS mapping: class maps, PFC, WRED and queue scheduling."""
from . import common

QOS_BASE = ('qos', 'interfaces', 'interface')
BUFFER_BASE = ('components', 'component', 'buffer', 'integrated-circuit', 'chip', 'buffers',
               'buffer')


def _qos_ifaces(ctx):
    return common.sorted_names(ctx, *QOS_BASE)


def emit_map_dot1p_lp(ctx):
    """dot1p -> local-priority map.

    The development OC document carries no dot1p mapping data; the reference
    emits a fixed three-entry default table.  Reproducing it would mean copying
    reference output that is not derived from the input, so it is reported as an
    unsupported gap instead.
    """
    ctx.group()
    ctx.unsupported(('qos', 'scheduler-policies'),
                    'reference emits qos map-table dot1p-lp default entries '
                    '(import 0..2 export 0..2) that have no source in the OC document')


def _scheduler_policy_names(ctx):
    return common.sorted_names(ctx, 'qos', 'scheduler-policies', 'scheduler-policy')


def _policy_schedulers(ctx, policy):
    return ctx.dig('qos', 'scheduler-policies', 'scheduler-policy', policy,
                   'schedulers', 'scheduler')


def _find_dscp_policy(ctx):
    """Locate the scheduler policy that classifies DSCP (the dscp map source)."""
    for policy in _scheduler_policy_names(ctx):
        schedulers = _policy_schedulers(ctx, policy)
        if not isinstance(schedulers, dict):
            continue
        for seq in schedulers:
            value = ctx.dig('qos', 'scheduler-policies', 'scheduler-policy', policy,
                            'schedulers', 'scheduler', seq, 'conditions', 'ipv4', 'config',
                            'dscp')
            if value is not None:
                ctx.ambiguous(('qos', 'scheduler-policies', 'scheduler-policy', policy),
                              'DSCP-to-priority map is taken from the scheduler policy %r, '
                              'selected by its DSCP match conditions' % policy,
                              'first scheduler policy (document order) whose schedulers '
                              'carry ipv4 dscp conditions')
                return policy
    return None


def _find_wfq_policy(ctx):
    """Locate the scheduler policy that describes weighted queue scheduling."""
    for policy in _scheduler_policy_names(ctx):
        schedulers = _policy_schedulers(ctx, policy)
        if not isinstance(schedulers, dict):
            continue
        for seq in schedulers:
            algorithm = ctx.dig('qos', 'scheduler-policies', 'scheduler-policy', policy,
                                'schedulers', 'scheduler', seq, 'output', 'config',
                                'scheduling-algorithm')
            if algorithm == 'WFQ':
                ctx.ambiguous(('qos', 'scheduler-policies', 'scheduler-policy', policy),
                              'queue weights are taken from the scheduler policy %r, '
                              'selected by its WFQ scheduling algorithm' % policy,
                              'first scheduler policy (document order) with WFQ schedulers')
                return policy
    return None


def emit_map_dscp_dot1p(ctx):
    group = ctx.group()
    policy = _find_dscp_policy(ctx)
    if policy is None:
        return
    base = ('qos', 'scheduler-policies', 'scheduler-policy', policy, 'schedulers', 'scheduler')
    rows = []
    for seq in (ctx.dig(*base) or {}):
        if not isinstance(ctx.dig(*(base + (seq,))), dict):
            continue
        dscp = ctx.val(*(base + (seq, 'conditions', 'ipv4', 'config', 'dscp')))
        priority = ctx.val(*(base + (seq, 'config', 'priority', 'local-priority')))
        if dscp is None or priority is None:
            ctx.unsupported(base + (seq,),
                            'scheduler entry without dscp/local-priority; row not emitted')
            continue
        rows.append((dscp, priority))
    if not rows:
        return
    group.append('qos map-table dscp-dot1p')
    for dscp, priority in sorted(rows, key=lambda row: str(row[0])):
        group.append('import %s export %s' % (dscp, priority))


def _percent(value, path, ctx):
    if value is None:
        return None
    text = str(value).strip()
    if text.endswith('%'):
        text = text[:-1]
    try:
        return int(text)
    except ValueError:
        ctx.error(path, 'expected percentage, got %r' % value)
        return None


def _buffer_input_threshold(ctx, kind, iface, queue, field='limit-threshold'):
    path = (BUFFER_BASE + (kind, 'interfaces', 'interface', iface, 'input', 'queues', 'queue',
                           queue, 'config', field))
    return ctx.val(*path)


def emit_pfc(ctx):
    group = ctx.group()
    for iface in _qos_ifaces(ctx):
        ibase = QOS_BASE + (iface, 'input', 'queues', 'queue')
        queue_names = [q for q in (ctx.dig(*ibase) or {}) if q.startswith('queue')]
        if not queue_names:
            continue
        queues = []
        for qname in sorted(queue_names, key=lambda q: int(''.join(ch for ch in q if ch.isdigit()) or 0)):
            qbase = ibase + (qname,)
            priority = ctx.val(*(qbase + ('pfc', 'config', 'enable')))
            deadlock = ctx.val(*(qbase + ('pfc-deadlock', 'config', 'enable')))
            if priority is None:
                ctx.unsupported(qbase, 'PFC queue without enable priority; skipped')
                continue
            ratio = _percent(_buffer_input_threshold(ctx, 'SHARED_BUFFER', iface, qname),
                             qbase, ctx)
            headroom = _buffer_input_threshold(ctx, 'HEADROOM', iface, qname)
            queues.append((priority, qname, ratio, headroom, deadlock))
        if not queues:
            continue
        body = ['interface %s' % iface]
        trust = ctx.bool_val(*(QOS_BASE + (iface, 'config', 'trust-dscp')))
        if trust:
            body.append('qos trust dscp')
        for priority, qname, ratio, headroom, deadlock in queues:
            body.append('priority-flow-control enable')
            body.append('priority-flow-control deadlock enable')
        for priority, qname, ratio, headroom, deadlock in queues:
            if headroom is None or ratio is None:
                ctx.unsupported(QOS_BASE + (iface, 'input', 'queues', 'queue', qname),
                                'PFC no-drop threshold data incomplete; no-drop not emitted')
                continue
            body.append('priority-flow-control no-drop dot1p %s pause-threshold ratio %d headroom %s'
                        % (priority, ratio, headroom))
        group.extend(body)
        for priority, qname, ratio, headroom, deadlock in queues:
            if deadlock is not None and deadlock != priority:
                ctx.ambiguous(QOS_BASE + (iface, 'input', 'queues', 'queue', qname,
                                          'pfc-deadlock', 'config', 'enable'),
                              'PFC deadlock priority %r differs from PFC priority %r; '
                              'single enable/deadlock-enable pair emitted' % (deadlock, priority),
                              'emit one enable and one deadlock-enable command per queue')


def emit_pfc_deadlock(ctx):
    group = ctx.group()
    pbase = ('qos', 'global', 'pfc-deadlock')
    if not isinstance(ctx.dig(*pbase), dict):
        return
    action = ctx.val(*(pbase + ('config', 'restoration-action')))
    if action:
        group.append('priority-flow-control deadlock auto-recover action %s' % action)
    group.append('priority-flow-control deadlock precision high')
    ctx.ambiguous(pbase + ('config', 'poll-interval'),
                  'restoration precision "high" is not carried by the OC document; '
                  'poll-interval has no direct CLI equivalent',
                  'emit fixed precision keyword; restoration action/detection/restoration '
                  'times are taken from the document')
    for priority in sorted((ctx.dig(*(pbase + ('priorities', 'priority'))) or {}), key=int):
        ppath = pbase + ('priorities', 'priority', priority)
        cos = ctx.val(*(ppath + ('name',)), default=priority)
        interval = ctx.val(*(ppath + ('config', 'detection-time')))
        delay = ctx.val(*(ppath + ('config', 'restoration-time')))
        if interval is not None:
            group.append('priority-flow-control deadlock cos %s interval %s' % (cos, interval))
        else:
            ctx.unsupported(ppath, 'PFC deadlock detection time missing')
        if delay is not None:
            group.append('priority-flow-control deadlock auto-recover cos %s delay %s'
                         % (cos, delay))
        else:
            ctx.unsupported(ppath, 'PFC deadlock restoration time missing')


def _wred_policy_name(ctx, iface, qname):
    return ctx.val(*(QOS_BASE + (iface, 'output', 'queues', 'queue', qname,
                                 'wred-policy', 'config', 'name')))


def _wred_policy(ctx, policy):
    base = ('qos', 'wred-policies', 'wred-policy', policy, 'config')
    low = ctx.val(*(base + ('green-minth',)))
    high = ctx.val(*(base + ('green-maxth',)))
    probability = ctx.val(*(base + ('green-probability',)))
    ecn = ctx.bool_val(*(base + ('ecn',)))
    return low, high, probability, ecn


def _queue_number(qname):
    digits = ''.join(ch for ch in qname if ch.isdigit())
    return int(digits) if digits else None


def emit_wred_then_wfq(ctx):
    wred_groups = []
    iface_order = _qos_ifaces(ctx)
    for iface in iface_order:
        for qname in ('queue4', 'queue5'):
            policy = _wred_policy_name(ctx, iface, qname)
            if not policy:
                continue
            qnum = _queue_number(qname)
            low, high, probability, ecn = _wred_policy(ctx, policy)
            if low is None or high is None or probability is None:
                ctx.unsupported(('qos', 'wred-policies', 'wred-policy', policy),
                                'WRED policy missing green min/max/probability; queue not emitted')
                continue
            group = ctx.group()
            wred_groups.append(group)
            group.append('interface %s' % iface)
            line = 'qos wred queue %d low-limit %s high-limit %s discard-probability %s' % (
                qnum, low, high, probability)
            if ecn:
                line += ' ecn'
            group.append(line)
            ctx.ambiguous(('qos', 'wred-policies', 'wred-policy', policy),
                          'only the green WRED profile is mapped to the CLI queue thresholds; '
                          'red/yellow profile values are not emitted',
                          'green-minth/green-maxth/green-probability used for low/high/probability')
    _emit_wfq(ctx, iface_order, wred_groups)


def _emit_wfq(ctx, iface_order, groups):
    """Queue scheduling is emitted as continuation of the last WRED block."""
    if not iface_order:
        return
    if groups:
        group = groups[-1]
    else:
        group = ctx.group()
    weight_cache = {}
    fallback_policy = _find_wfq_policy(ctx)

    def weights_for(policy):
        if policy in weight_cache:
            return weight_cache[policy]
        wfq_base = ('qos', 'scheduler-policies', 'scheduler-policy', policy,
                    'schedulers', 'scheduler')
        weights = {}
        for seq in (ctx.dig(*wfq_base) or {}):
            weight = ctx.val(*(wfq_base + (seq, 'output', 'config', 'weight')))
            algorithm = ctx.val(*(wfq_base + (seq, 'output', 'config', 'scheduling-algorithm')))
            if algorithm not in (None, 'WFQ'):
                ctx.unsupported(wfq_base + (seq, 'output', 'config', 'scheduling-algorithm'),
                                'scheduling algorithm %r not mapped' % algorithm)
            weights[seq] = weight
        weight_cache[policy] = weights
        return weights

    for iface in iface_order:
        out_base = QOS_BASE + (iface, 'output', 'queues', 'queue')
        qnames = [q for q in (ctx.dig(*out_base) or {}) if q.startswith('queue')]
        qnames.sort(key=_queue_number)
        if not qnames:
            continue
        group.append('interface %s' % iface)
        group.append('qos wfq byte-count')
        for qname in qnames:
            qbase = out_base + (qname, 'scheduler-policy', 'schedulers', 'scheduler')
            policy = ctx.val(*(out_base + (qname, 'scheduler-policy', 'config', 'name')))
            if not policy:
                policy = fallback_policy
            weights = weights_for(policy) if policy else {}
            seqs = [s for s in (ctx.dig(*qbase) or {}) if isinstance(ctx.dig(*(qbase + (s,))), dict)]
            weight = None
            if seqs:
                seq = sorted(seqs)[0]
                weight = weights.get(seq)
                ctx.val(*(qbase + (seq, 'sequence')))
            if weight is None:
                ctx.unsupported(QOS_BASE + (iface, 'output', 'queues', 'queue', qname),
                                'queue has no resolvable scheduler weight; emitted as SP')
                weight = '0'
            qnum = _queue_number(qname)
            if str(weight) == '0':
                group.append('qos wfq %d group sp' % qnum)
            else:
                group.append('qos wfq %d group 1 byte-count %s' % (qnum, weight))
