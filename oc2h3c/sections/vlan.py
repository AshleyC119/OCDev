"""VLAN definitions."""


def emit_vlans(ctx):
    vlans = []
    base = ('network-instances', 'network-instance')
    for ni, _ in ctx.items(*base):
        vlan_map = ctx.dig(*(base + (ni, 'vlans', 'vlan')))
        if isinstance(vlan_map, dict):
            for vlan_id in vlan_map:
                vlans.append((ni, vlan_id))
    vlans.sort(key=lambda item: (item[0], int(item[1]) if str(item[1]).isdigit() else item[1]))
    group = ctx.group()
    for ni, vlan_id in vlans:
        path = base + (ni, 'vlans', 'vlan', vlan_id)
        vid = ctx.val(*(path + ('config', 'vlan-id')), default=vlan_id)
        name = ctx.val(*(path + ('config', 'name')))
        group.append('vlan %s' % vid)
        if name:
            group.append('description %s' % name)
    if vlans:
        group.append('system-view')
        group.append('#')
