"""Verify visitor-IP metadata signed by our Vercel bridge, never raw forwarding headers."""

import hashlib
import hmac
import re
import time

from app.security.ip import canonical_ip

IP_HEADER = b"x-protocolguard-client-ip"
TIME_HEADER = b"x-protocolguard-client-time"
SIGNATURE_HEADER = b"x-protocolguard-client-signature"


def signing_secret(config):
    value = config.client_ip_signing_secret.get_secret_value()
    if value and len(value.encode()) < 32:
        raise ValueError("CLIENT_IP_SIGNING_SECRET must contain at least 32 bytes")
    return value


def verified_client_ip(scope, secret, *, timestamp=None):
    if not secret or scope["type"] != "http":
        return None
    values = {
        name: [value for key, value in scope.get("headers", []) if key.lower() == name]
        for name in (IP_HEADER, TIME_HEADER, SIGNATURE_HEADER)
    }
    if not any(values.values()):
        return None
    if any(len(value) != 1 for value in values.values()):
        raise ValueError("Invalid signed visitor address")
    try:
        address = values[IP_HEADER][0].decode("ascii")
        sent = values[TIME_HEADER][0].decode("ascii")
        signature = values[SIGNATURE_HEADER][0].decode("ascii")
        if not re.fullmatch(r"[0-9]{1,12}", sent) or not re.fullmatch(
            r"[0-9a-f]{64}", signature
        ):
            raise ValueError()
        current = time.time() if timestamp is None else timestamp
        if abs(current - int(sent)) > 60:
            raise ValueError()
        path = scope.get("raw_path", scope["path"].encode("utf-8")).decode("ascii")
        message = "\n".join(("pg-ip-v1", sent, scope["method"].upper(), path, address))
        expected = hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        return canonical_ip(address)
    except (UnicodeError, ValueError, TypeError, OverflowError) as error:
        raise ValueError("Invalid signed visitor address") from error
