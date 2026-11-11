"""Single-instance HTTPS hosting entrypoint; provisioning is explicit and idempotent."""

import os
from ipaddress import ip_network
from urllib.parse import urlsplit

import uvicorn

from app.core.config import settings
from app.database.store import Base, configure
from app.seed import seed


def validate_hosting(config, trusted_proxies):
    if config.protocolguard_env != "production":
        raise ValueError("The hosting entrypoint requires PROTOCOLGUARD_ENV=production")
    for origin in config.cors_origins.split(","):
        parsed = urlsplit(origin.strip())
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError(
                "CORS_ORIGINS must contain exact HTTPS origins without trailing slashes"
            )
    if config.serve_frontends and not config.static_directory:
        raise ValueError("STATIC_DIRECTORY must point to the compiled frontends")
    # Arbitrary clients must not be able to choose their observed security address.
    for proxy in filter(None, (entry.strip() for entry in trusted_proxies.split(","))):
        ip_network(
            proxy, strict=False
        )  # Reject wildcard trust, hostnames and malformed entries.


def provision(config):
    if os.environ.get("PROVISION_DEMO_ACCOUNTS", "false").lower() != "true":
        return
    bank_password = os.environ.get("DEMO_USER_PASSWORD", "")
    admin_password = os.environ.get("DEMO_ADMIN_PASSWORD", "")
    engine, factory = configure(config.database_url)
    try:
        Base.metadata.create_all(engine)
        seed(factory, bank_password, admin_password)
    finally:
        engine.dispose()
    print(
        "Demo account provisioning checked; existing passwords were retained.",
        flush=True,
    )


def main():
    if os.environ.get("RENDER_EXTERNAL_URL") and not os.environ.get("CORS_ORIGINS"):
        settings.cors_origins = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
    trusted_proxies = os.environ.get("FORWARDED_ALLOW_IPS", "").strip()
    validate_hosting(settings, trusted_proxies)
    provision(settings)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "10000")),
        workers=1,
        proxy_headers=bool(trusted_proxies),
        forwarded_allow_ips=trusted_proxies,
    )


if __name__ == "__main__":
    main()
