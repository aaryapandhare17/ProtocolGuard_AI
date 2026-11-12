# Railway backend + Vercel frontend

For the current no-card setup use [Vercel + Render Free + Neon](free-deployment.md).

This is an optional usage-based split deployment. One Vercel project serves SecureBank at `/`
and ProtocolGuard Admin at `/admin/`. One Railway service runs FastAPI, the loaded
ML models and SQLite on an attached volume. No custom domain is required.

Railway is usage-based: trial credits and plan/volume charges depend on your account.
Do not assume this is indefinitely free. Check Railway's current billing screen
before deploying. Vercel's Hobby eligibility and limits also apply.

## How authentication works

The browser calls `/api/...` on the Vercel domain. The Vercel Node function forwards
that request to the configured Railway HTTPS origin and returns its response,
including Set-Cookie. The cookies are therefore host-only on Vercel and retain
Secure, HttpOnly and SameSite=Strict. The frontend does not depend on third-party
cookies or expose credentials in build variables.

The bridge forwards only the request's content type, accept, cookie, origin and
CSRF header. It does not trust client-supplied forwarding headers. Protected routes
still perform all authorization and enforcement in FastAPI. The proxy allows only
an exact HTTPS backend origin, disables caching, bounds request bodies and times out
upstream requests. HTTP status codes remain intact so expired/restricted sessions
still produce the correct UI behavior.

Vercel functions do not provide this project's persistent WebSocket endpoint.
The Vercel build selects authenticated polling every three seconds and labels its
status **Polling**. Ordered event pages preserve the cursor without skipping a
batch. Dashboard revisions refresh alert/settings projections as well as events.
The existing local/direct-host WebSocket mode remains available.

## 1. Create the Vercel project

1. Sign in at [Vercel](https://vercel.com/signup) using GitHub.
2. Choose **Add New → Project**, import `aaryapandhare17/ProtocolGuard_AI` and use the
   repository root. Do not select `apps/admin` or `apps/securebank` as the root.
3. Framework preset: **Other**. The committed `vercel.json` supplies:
   build command `npm run build:vercel`, output directory `dist`, Node API functions
   and the two SPA route rewrites. Use Node.js 22.x.
4. Deploy and note the stable production origin, for example
   `https://protocolguard-ai.vercel.app`. Both login screens can load before the
   backend is connected; API requests return a clear configuration error until then.

## 2. Create the Railway backend

1. Sign in at [Railway](https://railway.com) and create a project using
   **Deploy from GitHub repo**. Authorize access to this repository and select it.
2. Keep the service root at the repository root. Set the Railway configuration
   file path to `deploy/railway.json`, which selects `deploy/railway.Dockerfile`.
   These optional Railway files are outside the root to avoid Vercel service inference. The image trains its own trusted
   models and matching comparison report during the build. No model upload is needed.
3. Attach one persistent volume mounted at `/var/data`. Keep one replica.
   SQLite state must not be written to ephemeral container storage.
4. Set these private service variables before the final deployment:

   | Variable | Value |
   | --- | --- |
   | `CORS_ORIGINS` | Exact Vercel production HTTPS origin, without a trailing slash |
   | `DATABASE_URL` | `sqlite:////var/data/protocolguard.db` |
   | `PROTOCOLGUARD_ENV` | `production` |
   | `SERVE_FRONTENDS` | `false` |
   | `PROVISION_DEMO_ACCOUNTS` | `true` for initial provisioning |
   | `DEMO_USER_PASSWORD` | Your private banking password, 12–256 characters |
   | `DEMO_ADMIN_PASSWORD` | A different private administrator password, 12–256 characters |
   | `IP_AUTO_RESTRICT_ENABLED` | `false` until proxy addresses are verified |
   | `SIMULATION_ENABLED` | `false` |

   The image supplies the non-secret defaults above except CORS and provisioning
   credentials. Never enter those passwords in Git, chat or a `VITE_` variable.
5. Deploy. In Networking choose **Generate Domain** and use Railway's injected
   `PORT`/detected service port. Copy the assigned HTTPS origin, for example
   `https://protocolguard-api-production.up.railway.app`.
6. Check `<railway-origin>/api/health`. It should return status `ok`. The backend
   root and `/admin/` intentionally return 404 in this API-only image.

## 3. Connect Vercel to Railway

1. In the Vercel project, open **Settings → Environment Variables**.
2. Add `BACKEND_ORIGIN` with the exact Railway HTTPS origin, no path or trailing
   query. It is a server-side variable: do not prefix it with `VITE_`.
3. Apply it to Production and redeploy Vercel so the function receives the value.
   Use the stable production Vercel URL for login. Preview URLs are separate
   origins and are denied unless explicitly added to the backend allowlist.
4. Open `<vercel-origin>/api/health`, then sign into the bank as `demo01` and Admin
   at `<vercel-origin>/admin/` as `admin`. Verify the admin status reads **Polling**.
5. After provisioning works, set `PROVISION_DEMO_ACCOUNTS=false` on Railway and
   remove its two provisioning password variables, then redeploy. The volume keeps
   the hashes and accounts. Re-provisioning never resets existing passwords.

## Validation and limits

Run the existing deployment browser check against your own dedicated dummy account:

```sh
# Set both private password variables in your shell.
# SMOKE_BASE_URL=https://your-project.vercel.app
# SMOKE_ALLOW_MUTATIONS=true
# SMOKE_LIVE_TRANSPORT=poll
npm run test:deployment
```

This records a dummy transfer and temporarily blocks/unblocks `demo10`, resetting
its risk. It leaves audit/event evidence. The check verifies cookie authentication,
CSRF, actual protected-route denial/recovery, polled block events, model reports,
admin deep links and mobile layouts. `npm run test:proxy` checks the bridge itself.

Keep production simulation execution disabled. Demonstrate the isolated attack lab
locally. Neither Railway's nor Vercel's proxy addresses should automatically be
interpreted as visitor IPs. Leave automatic IP restrictions off and avoid manually
blocking a shared proxy address until the forwarding topology is verified end to
end. Account-level enforcement remains active. Verified per-visitor attribution
requires configuring the signed visitor-IP bridge on both hosts as described below.

Backups, one-worker operation and SQLite migration guidance are in
[the deployment operations guide](deployment.md). Its Render launch instructions
are an alternative; use the Railway/Vercel steps above for this deployment.

For correct visitor attribution, configure the optional [signed visitor-IP bridge](visitor-ip-forwarding.md).
