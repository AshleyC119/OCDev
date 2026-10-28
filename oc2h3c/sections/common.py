"""Helpers shared by mapping sections."""
import ipaddress

from ..context import cli_name  # re-exported for section modules  # noqa: F401


def sorted_names(ctx, *parts):
    return sorted(name for name, _ in ctx.items(*parts))


def as_list(value):
    """OC may serialise a list as a JSON array, a scalar, or a dict of members."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    if value is None:
        return []
    return [value]


def iface_type(ctx, name):
    return ctx.val('interfaces', 'interface', name, 'config', 'type')


def ip_and_len(prefix):
    """Split '10.0.0.1/24' into ('10.0.0.1', 24). Raises ValueError."""
    if '/' not in prefix:
        raise ValueError('prefix without mask length: %r' % prefix)
    addr, length = prefix.rsplit('/', 1)
    ipaddress.IPv4Address(addr)
    return addr, int(length)


def wildcard_mask(prefix_len):
    mask = (1 << 32) - 1
    if not 0 <= prefix_len <= 32:
        raise ValueError('prefix length out of range: %d' % prefix_len)
    inv = mask ^ ((mask << (32 - prefix_len)) & mask) if prefix_len else mask
    return str(ipaddress.IPv4Address(inv))


def netmask(prefix_len):
    if not 0 <= prefix_len <= 32:
        raise ValueError('prefix length out of range: %d' % prefix_len)
    return str(ipaddress.IPv4Network('0.0.0.0/%d' % prefix_len, strict=False).netmask)


def mac_to_h3c(value):
    """00:00:5e:00:01:09 -> 0000-5e00-0109."""
    digits = value.replace(':', '').replace('-', '').replace('.', '').lower()
    if len(digits) != 12:
        raise ValueError('not a 48-bit MAC address: %r' % value)
    return '%s-%s-%s' % (digits[0:4], digits[4:8], digits[8:12])


def ip_sort_key(text):
    try:
        return (0, ipaddress.IPv4Address(text))
    except ValueError:
        return (1, text)


def truthy(node_value):
    """Interpret OC boolean-ish scalars, returning None when absent/unknown."""
    if isinstance(node_value, bool):
        return node_value
    if node_value is None:
        return None
    text = str(node_value).strip().lower()
    if text == 'true':
        return True
    if text == 'false':
        return False
    return None


def int_scalar(node_value, default=None):
    try:
        return int(str(node_value).strip())
    except (TypeError, ValueError):
        return default


def speed_kbps(port_speed):
    """OC port-speed is bits/s; the CLI uses kbit/s."""
    value = int_scalar(port_speed)
    if value is None or value % 1000 != 0:
        return None
    return value // 1000


def seconds_from_ms(value):
    millis = int_scalar(value)
    if millis is None or millis % 1000 != 0:
        return None
    return millis // 1000


def iface_number(aggregate_id):
    """'Bridge-Aggregation103' -> 103."""
    if not aggregate_id:
        return None
    digits = ''.join(ch for ch in aggregate_id if ch.isdigit())
    return int(digits) if digits else None
