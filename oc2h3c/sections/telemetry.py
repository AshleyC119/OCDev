"""gRPC / Telemetry Dial-out mapping (``telemetry-system``).

The OC document models the Dial-out configuration as sensor groups, destination
groups and persistent subscriptions.  The native transcript renders them in the
order sensor groups -> destination groups -> subscriptions, with the sensor
paths of a group sorted by path name.  Two reference formatting quirks are
reproduced byte-for-byte: a trailing space after a destination ``port`` value
and a trailing space on a subscription ``sensor-group <name>`` line whose
``sample-interval`` is absent (event-triggered sampling).
"""
TELEMETRY = ('telemetry-system',)
SENSOR_GROUPS = TELEMETRY + ('sensor-groups', 'sensor-group')
DESTINATION_GROUPS = TELEMETRY + ('destination-groups', 'destination-group')
SUBSCRIPTIONS = TELEMETRY + (
    'subscriptions', 'persistent-subscriptions', 'persistent-subscription')

GRPC = ('system', 'grpc', 'config')


def _num_key(text):
    text = str(text)
    return (0, int(text)) if text.isdigit() else (1, text)


def _ordered_items(ctx, *parts):
    return sorted(ctx.items(*parts), key=lambda item: _num_key(item[0]))


def _emit_grpc(ctx, group):
    enabled = ctx.bool_val(*(GRPC + ('enable',)))
    if enabled is True:
        group.append('grpc enable')
    elif enabled is False:
        group.append('undo grpc enable')
        ctx.ambiguous(GRPC + ('enable',),
                      'the OC gRPC enable leaf is false but the reference transcript '
                      'only shows the enabled form',
                      'a disabled gRPC service is rendered as undo grpc enable')
    for field, reason in (
            ('username', 'gRPC user name is not modelled by any command in the selected '
                         'H3C reference manual; the reference only emits grpc enable'),
            ('password', 'gRPC password is not modelled by any command in the selected '
                         'H3C reference manual; the reference only emits grpc enable'),
            ('tls-type', 'gRPC TLS mode is not modelled by any command in the selected '
                         'H3C reference manual; the reference only emits grpc enable')):
        value = ctx.val(*(GRPC + (field,)))
        if value is not None:
            ctx.unsupported(GRPC + (field,), reason)


def _sensor_paths(ctx, group_name):
    base = SENSOR_GROUPS + (group_name, 'sensor-paths', 'sensor-path')
    paths = []
    for path_key, _node in ctx.items(*base):
        pbase = base + (path_key,)
        leaf_path = ctx.val(*(pbase + ('path',)))
        config_path = ctx.val(*(pbase + ('config', 'path')))
        paths.append(config_path or leaf_path or path_key)
    paths.sort()
    return paths


def _emit_sensor_groups(ctx, group):
    for name, _node in _ordered_items(ctx, *SENSOR_GROUPS):
        base = SENSOR_GROUPS + (name,)
        ctx.val(*(base + ('sensor-group-id',)))
        group_id = ctx.val(*(base + ('config', 'sensor-group-id')), default=name) or name
        group.append('sensor-group %s' % group_id)
        for path in _sensor_paths(ctx, name):
            group.append('sensor path %s' % path)


def _emit_destination_groups(ctx, group):
    seen_destination = False
    for name, _node in _ordered_items(ctx, *DESTINATION_GROUPS):
        base = DESTINATION_GROUPS + (name,)
        ctx.val(*(base + ('group-id',)))
        group_id = ctx.val(*(base + ('config', 'group-id')), default=name) or name
        group.append('destination-group %s' % group_id)
        destinations = []
        dest_base = base + ('destinations', 'destination')
        for dest_key, _dest in ctx.items(*dest_base):
            dbase = dest_base + (dest_key,)
            ctx.val(*(dbase + ('destination-address,destination-port',)))
            ctx.val(*(dbase + ('destination-address',)))
            ctx.val(*(dbase + ('destination-port',)))
            address = ctx.val(*(dbase + ('config', 'destination-address')))
            port = ctx.val(*(dbase + ('config', 'destination-port')))
            destinations.append((address or '', port or ''))
        for address, port in sorted(destinations):
            line = 'ipv4-address %s' % address
            if port:
                line += ' port %s' % port
            # reference transcript keeps a trailing separator after the port
            group.append(line + ' ')
            seen_destination = True
    if seen_destination:
        ctx.ambiguous(DESTINATION_GROUPS,
                      'the reference transcript keeps a trailing space after the '
                      'destination collector port',
                      'the trailing separator is reproduced for a byte-identical '
                      'transcript')


def _emit_subscriptions(ctx, group):
    seen_interval = False
    seen_missing_interval = False
    for name, _node in _ordered_items(ctx, *SUBSCRIPTIONS):
        base = SUBSCRIPTIONS + (name,)
        ctx.val(*(base + ('name',)))
        subscription = ctx.val(*(base + ('config', 'name')), default=name) or name
        group.append('subscription %s' % subscription)
        source = ctx.val(*(base + ('config', 'local-source-address')))
        if source:
            group.append('source-address %s' % source)

        profiles = []
        profile_base = base + ('sensor-profiles', 'sensor-profile')
        for profile_key, _profile in ctx.items(*profile_base):
            pbase = profile_base + (profile_key,)
            leaf_group = ctx.val(*(pbase + ('sensor-group',)))
            sensor_group = ctx.val(*(pbase + ('config', 'sensor-group')),
                                   default=leaf_group)
            interval = ctx.val(*(pbase + ('config', 'sample-interval')))
            if sensor_group is None:
                ctx.unsupported(pbase, 'subscription sensor profile without a sensor '
                                       'group cannot be emitted')
                continue
            profiles.append((sensor_group, interval))
        for sensor_group, interval in sorted(profiles,
                                             key=lambda item: _num_key(item[0])):
            if interval is None:
                group.append('sensor-group %s ' % sensor_group)
                seen_missing_interval = True
            else:
                group.append('sensor-group %s sample-interval %s'
                             % (sensor_group, interval))
                seen_interval = True

        destination_groups = []
        dest_base = base + ('destination-groups', 'destination-group')
        for dest_key, _dest in ctx.items(*dest_base):
            dbase = dest_base + (dest_key,)
            leaf_group = ctx.val(*(dbase + ('group-id',)))
            group_id = ctx.val(*(dbase + ('config', 'group-id')),
                               default=leaf_group or dest_key)
            destination_groups.append(group_id)
        for group_id in sorted(destination_groups, key=_num_key):
            group.append('destination-group %s' % group_id)

    if seen_missing_interval:
        ctx.ambiguous(SUBSCRIPTIONS + ('sensor-profiles',),
                      'a subscription sensor profile has no sample-interval in the OC '
                      'document (event-triggered sampling)',
                      'the reference keeps a trailing space where the sample-interval '
                      'argument would be; reproduced for a byte-identical transcript')
    if seen_interval:
        ctx.ambiguous(SUBSCRIPTIONS + ('sensor-profiles',),
                      'a subscription sensor profile carries a sample-interval in the '
                      'OC document',
                      'emitted as sensor-group <name> sample-interval <seconds>')


def emit_telemetry(ctx):
    group = ctx.group()
    _emit_grpc(ctx, group)
    group.append('telemetry')
    _emit_sensor_groups(ctx, group)
    _emit_destination_groups(ctx, group)
    _emit_subscriptions(ctx, group)
