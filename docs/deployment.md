# Deployment operations

The default `render.yaml` now uses a Free API-only web service and external Neon
PostgreSQL. It has **no persistent disk**. Follow the
[no-card deployment guide](free-deployment.md) for account setup and publishing.
The [Railway guide](railway-vercel.md) describes an alternative with potential
usage/volume charges; it is not the default no-card configuration.

## Database state

Hosted users, password hashes, sessions, events, risk, restrictions, settings, audits
and saved run records live in Neon. Rebuilding/restarting the backend does not erase
them. Deleting the Neon database/project does erase state; provider free-plan
retention/recovery limits apply. Export data before destructive changes.

Use Neon's documented PostgreSQL export/backup procedures and matching-version
`pg_dump` for a separate backup. Keep database URIs/passwords private and store
backups securely. A snapshot in the same database/project is not protection from
project deletion. Restoration requires an intentional database restore procedure.

The app creates missing tables at startup. It does not automatically migrate an
old SQLite file or rewrite incompatible PostgreSQL schema/indexes. Review migrations
and create backups before incompatible future changes. See [PostgreSQL](postgresql.md).

`REQUIRE_POSTGRES=true` rejects missing/wrong database configuration instead of
silently storing hosted state in an ephemeral SQLite file. SQLite remains supported
for local development and disposable simulation databases.

## Transport, cookies and origins

Vercel serves both websites and proxies `/api/...` to the backend. Configure exact
`BACKEND_ORIGIN` on Vercel and exact `CORS_ORIGINS` on the backend. HTTPS, host-only
Secure/HttpOnly/SameSite=Strict cookies and CSRF remain enforced. Add custom-domain
origins explicitly; wildcard origins are not a substitute for configuration.
The Vercel build uses authenticated polling, while direct/local hosting retains
WebSockets. Saved evaluation reports and detector artifacts are built together.

The optional [signed visitor-IP bridge](visitor-ip-forwarding.md) verifies Vercel's
edge address using a private shared key before Render uses it. Without that setup,
addresses can describe shared proxies. Keep `IP_AUTO_RESTRICT_ENABLED=false` until
the signed bridge is enabled and verified from two networks; account-level blocking
stays active. Production lab execution remains disabled.

## Browser verification

After publishing your own academic demo, configure the environment for:

```sh
# SMOKE_BASE_URL=https://your-project.vercel.app
# SMOKE_ALLOW_MUTATIONS=true
# SMOKE_LIVE_TRANSPORT=poll
# DEMO_USER_PASSWORD and DEMO_ADMIN_PASSWORD: set privately in your shell
npm run test:deployment
```

This records a transfer request, temporarily blocks/unblocks dedicated `demo10` and
resets its risk, leaving event/audit evidence. It verifies cookies, CSRF, unchanged
dummy balances, backend denial/recovery, old-session revocation, polled events,
model reports, deep-link reloads and mobile overflow. Do not run it against real
accounts or another person's deployment. `npm run test:proxy` checks the API bridge.

## Optional all-in-one hosting

`deploy/all-in-one.Dockerfile` builds both frontends into the FastAPI service, with
Admin at `/admin/` and native WebSockets. It uses SQLite on `/var/data` by default,
which requires durable storage and may incur hosting charges. Choose that path only
with an explicitly provisioned persistent volume and one instance/worker. Build it from the repository root with
`docker build -f deploy/all-in-one.Dockerfile -t protocolguard-all-in-one .`.
It is not the default no-card Blueprint. For local SQLite backups use its online backup API;
do not copy only a WAL database file during active writes.

## Troubleshooting

- **Backend unavailable on first request:** free compute may be waking. Wait about
  a minute and retry; inspect logs if it continues.
- **Startup fails:** verify the private Neon URI/TLS options, exact HTTPS origin,
  explicit provisioning flag and different valid provisioning passwords. Do not
  publish environment dumps or paste a connection string into chat.
- **API works directly but not through Vercel:** set `BACKEND_ORIGIN` on Production,
  then redeploy Vercel. Confirm the backend allows the stable Vercel origin.
- **Admin refresh fails:** use `/admin/` on the combined Vercel build and keep the
  project root at the repository root.
- **Hosted data appears empty:** verify you selected the intended Neon project,
  branch and database. Local SQLite data is not imported automatically.
- **Card/payment requested:** stop and inspect the selected plan/resource. The
  default configuration calls for Free compute, external Free database and no disk.
