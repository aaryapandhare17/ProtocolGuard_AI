"""Canonical addresses from trusted ASGI connection information only."""
from ipaddress import ip_address, IPv6Address


def canonical_ip(value):
    if not isinstance(value,str) or '%' in value:
        raise ValueError("Use one IPv4 or IPv6 address without a zone, port or CIDR")
    address=ip_address(value)
    if isinstance(address,IPv6Address) and address.ipv4_mapped:
        address=address.ipv4_mapped
    return str(address)


def connection_ip(scope):
    client=scope.get('client')
    try:
        return canonical_ip(client[0]) if client else None
    except ValueError:
        return None
