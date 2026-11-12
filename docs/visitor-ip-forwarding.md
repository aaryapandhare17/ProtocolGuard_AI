# Verified visitor addresses through Vercel

The browser connects to Vercel, and its API function connects to Render. Previously,
Render recorded that proxy connection. Two devices on different networks could
therefore appear to use the same server address. Historical rows keep their original
observed address; the fix applies to new requests.

## Enable on your deployed accounts

1. Deploy this commit to Render. Synchronize the service's Blueprint if necessary:
   `render.yaml` now declares `CLIENT_IP_SIGNING_SECRET` with `generateValue: true`.
   Render generates a private random 256-bit value when the variable does not already
   exist; it does not overwrite an existing value on later syncs.
2. In **Render → protocolguard-api → Environment**, reveal and copy that generated
   value privately. Do not put it in chat, Git, a screenshot or a public frontend
   variable. If manually configuring the service, generate a cryptographically
   random value of at least 32 bytes and store it under the same name.
3. In **Vercel → project → Environment Variables**, set the same exact value for
   `CLIENT_IP_SIGNING_SECRET` in **Production**. It is server-only: no `VITE_` prefix.
4. Redeploy Vercel so its function receives the key. Keep the existing
   `BACKEND_ORIGIN` and backend `CORS_ORIGINS` values.
5. After both deployments are ready, generate a fresh banking event from a device
   on Wi-Fi and another device on mobile data. Check those new events in Admin.
   Their addresses should match the public addresses observed by Vercel, rather
   than the shared Render connection.
6. After verifying both networks, set `REQUIRE_SIGNED_CLIENT_IP=true` on Render
   and deploy. This requires signed metadata for API requests and disables direct
   WebSocket access in this HTTP-polling deployment, preventing unsigned direct
   backend requests from bypassing IP controls. Keep automatic IP bans off until
   this strict mode and two-network check are verified.

Set the Render side first. Until the bridge has the key, unsigned requests retain
connection-based attribution; login continues to work. Once Vercel signs requests,
a mismatched backend key causes a clear validation error instead of accepting an
unverified address. Recopy the exact value if that happens. For rotation, first disable `REQUIRE_SIGNED_CLIENT_IP` on Render, then remove the
Vercel key to return to unsigned attribution while updating the backend key. Copy
the new key to Vercel, deploy and verify, then re-enable the requirement. Both
hosts must agree on the key.

## Trust boundary

The Vercel function reads only the platform's `x-vercel-forwarded-for` address when
running on Vercel. It does not select a user-supplied generic `X-Forwarded-For` chain.
Vercel documents overwriting forwarding headers to prevent IP spoofing:
[request headers](https://vercel.com/docs/headers/request-headers).
An additional proxy placed in front of Vercel can still affect which network edge
Vercel observes; this setup assumes the current direct Vercel production URL.

The bridge signs a versioned message containing the timestamp, method, API path and
address using HMAC-SHA256. Its signing key and outgoing signature are not returned
to the browser. Render verifies the signature, a 60-second clock-skew limit, address
syntax, method/path binding and unique security headers before changing the ASGI
client address. Unsigned ordinary forwarding headers never gain trust. Invalid
signed metadata receives HTTP 400 before authentication or event attribution.

Without a configured key, the existing connection-based behavior remains available.
Strict forwarding is off by default so initial secret setup does not interrupt
existing requests; requiring signatures is an explicit operator activation step.
A key shorter than 32 bytes is rejected. Direct native WebSocket deployments still
use their connection/proxy configuration; this feature covers the HTTP API bridge
used by the deployed polling dashboard.

## IP restrictions and history

Verified addresses flow through the existing IP gateway, security events and account
associations. A restriction on one verified IP is checked against that IP before
banking routes run. Account risk remains independent of IP identity. A shared public
IP can legitimately represent several devices on one Wi-Fi, carrier NAT or VPN.
An IP is not a unique device identifier.

Keep `IP_AUTO_RESTRICT_ENABLED=false` until the two-network deployment check passes.
Enabling automatic IP bans is a separate operator decision; correct forwarding does
not enable them automatically. Do not rewrite old proxy-address events or block a
shared historical proxy address to test the fix.

## Verification

Backend checks cover two clients behind the same transport address, distinct signed
visitor addresses, ordinary-header spoofing, IP-specific denial, wrong signatures,
changed method/path/address, stale timestamps, duplicate headers and IPv4-mapped IPv6.
Node tests cover Vercel-only edge extraction and matching signatures. Existing login,
CSRF, account enforcement and ML acceptance checks remain in place. Actual public
network attribution still needs the private key configured on both hosting accounts.
