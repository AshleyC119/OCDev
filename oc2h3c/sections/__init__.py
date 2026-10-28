"""Ordered mapping steps.

Each step appends one or more ``system-view`` blocks to the translation context.
The order is part of the frozen implementation identity: it follows the section
order observed in the paired development reference so that the generated script
is structurally comparable to native output.
"""
from . import (aaa, acl, bfd_routing, bgp, buffer, interfaces, int_ifa, lacp,
               lines, lldp, monitor, qos, relay, sflow, system, telemetry,
               telemetry_mod, vlan, vpn_static)


def _empty(ctx):
    """A deliberate empty block (kept so section positions are stable)."""
    ctx.group()


STEPS = [
    _empty,                                  # index 1: preamble block
    vpn_static.emit_vpn_instances,           # 2
    vpn_static.emit_mgmt_bindings,           # 3
    vpn_static.emit_static_routes,           # 4
    vlan.emit_vlans,                         # 5
    acl.emit_acls,                           # 6
    interfaces.emit_pass1,                   # 7
    _empty,                                  # 8: reserved (no supported source)
    _empty,                                  # 9: reserved (no supported source)
    qos.emit_map_dot1p_lp,                   # 10
    qos.emit_map_dscp_dot1p,                 # 11
    qos.emit_pfc,                            # 12
    qos.emit_pfc_deadlock,                   # 13
    qos.emit_wred_then_wfq,                  # 14..397 (+ wfq tail)
    lldp.emit_lldp,                          # 398
    relay.emit_dhcp,                         # 399
    lacp.emit_lacp,                          # 400
    bfd_routing.emit_bfd_and_routing,        # 401
    bgp.emit_bgp,                            # 402
    int_ifa.emit_int,                        # 403
    lines.emit_line_aux,                     # 404
    lines.emit_line_vty,                     # 405
    monitor.emit_monitor_link,               # 406
    monitor.emit_monitor_link_ports,         # 407..598
    _empty,                                  # 599: reserved (no supported source)
    system.emit_system,                      # 600
    sflow.emit_sflow,                        # 601
    _empty,                                  # 602: reserved (no supported source)
    aaa.emit_aaa,                            # 603
    telemetry.emit_telemetry,                # 604
    buffer.emit_threshold_headroom_alarm,    # 605
    buffer.emit_headroom_usage,              # 606..989
    buffer.emit_pfc_pool_alarms,             # 990
    buffer.emit_egress_ingress,              # 991..1182
    telemetry_mod.emit_mod,                  # 1183
]
