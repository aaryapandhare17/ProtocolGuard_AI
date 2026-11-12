# No-card deployment: Vercel + Render Free + Neon Free

Use one Vercel Hobby project for both websites, one Render **Free web service** for
FastAPI/ML, and one Neon **Free PostgreSQL project** for persistent data.
There is no paid Render disk in this configuration. Keep all accounts on their free
plans and do not add a payment method or choose paid upgrades.

The earlier SQLite-on-Render configuration needed a paid disk. External PostgreSQL
removes that requirement. Hugging Face is not used: its current documentation says
new Docker Spaces require a paid plan, and Spaces restrict outbound network ports
(including PostgreSQL's normal 5432 port).

Provider terms checked on 11 November 2026:

- [Render Free](https://render.com/docs/free): free web services sleep after idle
  periods and have monthly runtime, build and bandwidth limits. Without a payment
  method, exhausted allowances can suspend service instead of buying extra usage.
- [Neon pricing](https://neon.com/pricing): the Free plan requires no credit card and
  has storage/compute limits. Select Free and avoid plan upgrades.
- [Vercel Hobby](https://vercel.com/docs/plans/hobby): use within its eligibility and
  usage limits for this personal academic demo.
- [Hugging Face Spaces](https://huggingface.co/docs/hub/spaces-overview): confirms
  the paid Docker creation requirement and outbound-port restrictions.

Providers may change signup/verification requirements. If any account asks for a
card or payment to continue, stop there; do not assume a paid selection is needed
for this repository's configuration. This is a free-tier demo with availability
limits, not a guaranteed continuously running service.

## Step 1: Vercel frontend

1. Sign up/sign in at [Vercel](https://vercel.com/signup) using GitHub.
2. Import `aaryapandhare17/ProtocolGuard_AI` as a new project.
3. Use the **repository root**, Framework Preset **Other**, and Node.js **22.x**.
   `vercel.json` supplies the build command, output directory and routes.
4. If Vercel lists individual applications, choose **Import single project** beside
   `admin`, then change **Root Directory** to `./` and **Framework Preset** to
   **Other** on the configuration screen. Do not use multi-service import.
   Confirm build command `npm run build:vercel` and output directory `dist`.
5. Deploy, then copy the stable production origin, for example
   `https://protocolguard-ai.vercel.app`.

SecureBank appears at `/` and Admin at `/admin/`. Login cannot complete until the
backend connection below is configured. Both websites share one Vercel project.

## Step 2: Neon persistent database

1. Sign up at [Neon](https://console.neon.tech/signup), select **Free**, and create
   a project. Choose a region near the Render service when available.
2. In **Connect**, select the application's database and copy its PostgreSQL
   connection string. The pooled endpoint is supported. Keep the supplied TLS
   query parameters, including `sslmode=require` and any channel-binding option.
3. Keep this string private. It contains the database password. You will paste it
   only into Render's `DATABASE_URL` secret, never into chat or GitHub.

The backend creates its tables at startup and provisions dummy accounts only when
explicitly enabled. This creates a fresh hosted database; it does not migrate your
local SQLite file automatically.

## Step 3: Render Free backend

1. Sign up at [Render](https://dashboard.render.com/register) using GitHub.
2. Open [Deploy to Render](https://render.com/deploy?repo=https://github.com/aaryapandhare17/ProtocolGuard_AI)
   or choose **New → Blueprint** and select this repository, branch `main`.
3. Review the Blueprint: it must show a **Free** web service and **no disk**.
   `render.yaml` selects `deploy/postgres.Dockerfile` and the Free plan explicitly.
   If the dashboard offers a paid disk/Starter service, do not deploy that selection.
4. Enter the private environment values prompted by the Blueprint:

   | Variable | Value |
   | --- | --- |
   | `DATABASE_URL` | The full private Neon PostgreSQL connection string |
   | `CORS_ORIGINS` | Exact Vercel production HTTPS origin, without a trailing slash |
   | `DEMO_USER_PASSWORD` | A private banking password, 12–256 characters |
   | `DEMO_ADMIN_PASSWORD` | A different private admin password, 12–256 characters |

   The file sets production mode, API-only serving, required PostgreSQL and initial
   demo provisioning. Simulation execution and unverified automatic IP bans are off.
5. Deploy and wait for the build/health check. The image generates synthetic data,
   trains the models and exports matching evaluation artifacts. No local model
   upload, database disk or GPU is required.
6. Copy the assigned `https://<service>.onrender.com` origin. Visit
   `<render-origin>/api/health`; it should report status `ok`. Root `/` returning
   404 is expected: the websites are on Vercel.

For manual service creation, choose a Docker web service, repository root,
Dockerfile `deploy/postgres.Dockerfile`, instance type **Free**, no disk, and health
path `/api/health`. Copy the non-secret settings from `render.yaml` as well as the
four private values above. Do not select the optional `deploy/all-in-one.Dockerfile` for this free setup.

## Step 4: Connect and verify

1. In Vercel **Settings → Environment Variables**, set server-only `BACKEND_ORIGIN`
   to the exact Render HTTPS origin. No path, credentials or `VITE_` prefix.
2. Redeploy Vercel so its API function receives the environment value.
3. Open `<vercel-origin>/api/health` to verify the proxy, then sign into SecureBank
   as `demo01` and Admin at `/admin/` as `admin`, using your chosen passwords.
4. The admin connection status is **Polling**, with authenticated updates roughly
   every three seconds. API requests, CSRF and host-only Secure/HttpOnly cookies
   remain on the Vercel domain; no third-party cookie permission is needed.
5. After successful initial provisioning, set Render's `PROVISION_DEMO_ACCOUNTS=false`
   and remove its two provisioning password variables, then redeploy. Password
   hashes and data stay in Neon. Keep `DATABASE_URL` as a private runtime secret.

## Free-tier behavior and operations

Render can sleep after inactivity. Its documentation describes wake-up taking about
a minute; a Vercel request may time out before that finishes. Wait and retry. The
bridge returns retryable API feedback for a hosting loading page rather than
pretending that page is valid JSON. Do not add artificial keep-alive traffic to
circumvent a provider's free-tier limits.

Neon data survives backend sleep, rebuilds and restarts. Its free compute can also
suspend when idle and resume on a connection. The app bounds its pool, checks stale
connections and serializes security transactions. Do not exceed the free storage
limit: event/audit history grows during use. No automatic destructive data purge is
included; export/retention needs an intentional policy.

Free availability, storage and usage limits can change. Monitor each dashboard and
stop the demo when done. The [operations guide](deployment.md) covers backups and
proxy limitations. The [database guide](postgresql.md) explains PostgreSQL behavior.
Publishing still requires your account sign-ins and private secret entry. Share
only the public Vercel/Render URLs for reachability checks.
