# Deploy on Render

The repository includes a Docker image and `render.yaml` Blueprint for one web
service. It serves SecureBank at `/`, ProtocolGuard Admin at `/admin/`, API routes
at `/api/` and authenticated events at `/ws/admin/events` on the same HTTPS origin.
The production image builds both React apps, generates the synthetic dataset,
trains RF/IF models and creates a matching four-detector comparison report. Model
artifacts and private credentials do not need to be committed to Git.

## Deploy from GitHub

1. Open [Deploy to Render](https://render.com/deploy?repo=https://github.com/aaryapandhare17/ProtocolGuard_AI).
   Sign in, connect GitHub and grant access to this repository. Alternatively choose
   **New → Blueprint** in the Render dashboard and select `ProtocolGuard_AI`, branch
   `main`. The Blueprint is at the repository root.
2. Review the proposed **Starter web service and 1 GB persistent disk** and Render's
   current pricing. The persistent-disk configuration requires a paid service; this
   Blueprint is not a free-tier deployment. Keep one instance. Singapore is the
   configured region; change it before creating the service if needed.
3. Enter `DEMO_USER_PASSWORD` and `DEMO_ADMIN_PASSWORD` in Render's private environment
   inputs. Choose different passwords, each 12–256 characters. The former provisions
   `demo01`–`demo10`; the latter provisions `admin`. Do not put passwords in GitHub,
   chat, screenshots or a public frontend environment variable.
4. Choose **Deploy Blueprint**. The build installs dependencies, builds both apps,
   trains the models and evaluates them. First build takes several minutes. Follow
   the build and application logs, then wait for `/api/health` to pass.
5. Open Render's assigned `https://<service>.onrender.com` URL for the bank and append
   `/admin/` for the administrator site. Login with the accounts/passwords above.
   The service automatically uses Render's `RENDER_EXTERNAL_URL` as its allowed
   origin. There is no frontend API URL to configure.
6. After the first successful provisioning, set `PROVISION_DEMO_ACCOUNTS=false` in
   Render and remove the two provisioning password environment variables, then
   restart/deploy. Password hashes and accounts already exist on the disk. Retaining
   those variables is not needed for later logins. Re-enabling provisioning never
   resets existing passwords.

The repository's GitHub workflow checks backend tests, frontend tests and builds, followed by a production Docker build and HTTP smoke checks.
The Blueprint enables automatic deployments after checks pass. A rejected build or
failing check must be fixed before treating that revision as deployed.

## Persistent state

`DATABASE_URL=sqlite:////var/data/protocolguard.db` stores users, password hashes,
sessions, events, risk, alerts, restrictions, settings, audits and saved lab results
on the attached disk. Restarts/redeploys keep that state. Deleting the service/disk
or changing the database path does not preserve it automatically. Keep one instance
and one Uvicorn worker; this release does not coordinate streams across processes.

Back up SQLite using its online backup API, not by copying only the `.db` file
while WAL writes are active. From the Render shell, for example:

```sh
python -c "import sqlite3; source=sqlite3.connect('/var/data/protocolguard.db'); target=sqlite3.connect('/var/data/backup.db'); source.backup(target); target.close(); source.close()"
```

This creates a snapshot on the same disk. Download/store an encrypted copy elsewhere
for protection from disk deletion; a same-disk snapshot alone is not disaster recovery.
Restoration needs a stopped service or a documented SQLite restore procedure.
Schema tables are created at startup; future incompatible schema changes require
explicit migrations and a backup before deployment.

## HTTPS, domains and proxy addresses

Production cookies are Secure, HttpOnly and SameSite=Strict. Render terminates HTTPS;
keep the public endpoint on HTTPS. For a custom domain, configure the domain in
Render and set `CORS_ORIGINS` to the exact HTTPS origins you use, separated by commas,
without paths or trailing slashes. That explicit value overrides the assigned URL.
The same allowlist applies to login and WebSocket origins.

The hosting entrypoint does **not** trust forwarded IP headers by default. Behind
Render, observed addresses may therefore identify a proxy instead of the visitor.
The Blueprint sets `IP_AUTO_RESTRICT_ENABLED=false` to prevent automatic restrictions
on that unverified shared address. Account risk/blocking, authentication and account
session revocation remain active. Do not manually block the shared proxy address.

Before enabling IP enforcement, verify the provider's current proxy topology and
configure `FORWARDED_ALLOW_IPS` with only the verified proxy IPs/CIDRs. Test two
separate client networks and confirm that fabricated client forwarding headers
cannot choose the observed address. Wildcard `*` and hostnames are rejected by the
hosting entrypoint. Once addresses are trustworthy, set
`IP_AUTO_RESTRICT_ENABLED=true`. Do not claim per-visitor IP enforcement is verified
until that hosted check passes.

`SIMULATION_ENABLED=false` and the production environment deny lab execution. Saved
lab history is still admin-readable. Run the six attack demonstrations locally in
development; normal hosted banking and admin recovery use the real deployed APIs.

## Local production container check

```sh
docker build -t protocolguard-ai .
docker volume create protocolguard-data
# Put private values in a local ignored environment file, never in the image:
# CORS_ORIGINS=https://your-exact-domain.example
# PROVISION_DEMO_ACCOUNTS=true
# DEMO_USER_PASSWORD=...
# DEMO_ADMIN_PASSWORD=...
docker run --rm -p 10000:10000 --env-file .env.hosted \
  --mount source=protocolguard-data,target=/var/data protocolguard-ai
```

Serve that port behind HTTPS for browser login, since production cookies require a
secure origin. `STATIC_DIRECTORY` points to the compiled `bank` and `admin` folders;
Vite's development servers are not used in this container. The health endpoint can
be checked with HTTP inside the hosting network.

A repeatable Chromium check is included:

```sh
npm ci
npx playwright install chromium
# Set SMOKE_BASE_URL to the HTTPS service origin and supply both private password
# variables in your shell. Use a dedicated dummy account, default demo10.
# Set SMOKE_ALLOW_MUTATIONS=true: this records a dummy transfer, blocks/unblocks
# that account, resets its risk, and leaves persistent audit/event evidence.
npm run test:deployment
```

The check verifies bank/admin login, dummy balance preservation, actual account
block/denial/recovery, revoked old sessions, WebSocket alerts, measured reports,
admin deep-link reloads, the production lab guard and mobile overflow. Run it only
against your own academic demo. `CHROMIUM_PATH` can select a locally installed
browser. `SMOKE_LOCAL_TLS=true` allows a self-signed certificate only for localhost.

## Troubleshooting

- **Build failure:** read the first failing build step. The models are generated at
  image build time; missing local `.joblib` files are expected. Retry only after
  correcting the actual dependency/build error.
- **Startup failure:** check that the persistent disk is mounted at `/var/data`,
  the provisioning passwords differ and meet length requirements, and the allowed
  origin is HTTPS. Never publish a full environment dump.
- **Login works locally but fails hosted:** use HTTPS and the same origin for both
  websites and API. Check the exact `CORS_ORIGINS` value if you added a custom domain.
- **Admin refresh fails:** the URL must start `/admin/`; the image builds its asset
  and router base for that path.
- **No live updates:** confirm the `/ws/admin/events` WebSocket upgrades successfully,
  the admin session is valid and the public origin is allowed.
- **State disappears after deploy:** verify the SQLite URL uses the attached disk,
  not the container's ephemeral `/app` filesystem.
