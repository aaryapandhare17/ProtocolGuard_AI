/** Exercise a deployed academic demo with a dedicated account. Never print secrets. */
import assert from "node:assert/strict";
import { chromium } from "playwright";

const base = new URL(process.env.SMOKE_BASE_URL || "http://localhost:10000");
const user = process.env.SMOKE_USER || "demo10";
const bankPassword = process.env.DEMO_USER_PASSWORD;
const adminPassword = process.env.DEMO_ADMIN_PASSWORD;
assert(/^demo(0[1-9]|10)$/.test(user), "Choose a provisioned demo account");
assert(
  bankPassword && adminPassword,
  "Set both passwords through the environment",
);
assert.equal(
  process.env.SMOKE_ALLOW_MUTATIONS,
  "true",
  "This check records a transfer, blocks/unblocks the dedicated demo account and resets its risk; set SMOKE_ALLOW_MUTATIONS=true",
);
const browser = await chromium.launch({
  ...(process.env.CHROMIUM_PATH
    ? { executablePath: process.env.CHROMIUM_PATH }
    : {}),
  headless: true,
});
try {
  const contextOptions = {
    ignoreHTTPSErrors: process.env.SMOKE_LOCAL_TLS === "true",
  };
  assert(
    !contextOptions.ignoreHTTPSErrors ||
      ["localhost", "127.0.0.1"].includes(base.hostname),
    "Self-signed TLS is permitted only for the local container check",
  );
  const bankContext = await browser.newContext(contextOptions);
  const adminContext = await browser.newContext(contextOptions);
  const bank = await bankContext.newPage(),
    admin = await adminContext.newPage();
  const errors = [];
  for (const page of [bank, admin])
    page.on("pageerror", (error) => errors.push(error.message));
  const url = (path) => new URL(path, base).href;
  await admin.goto(url("/admin/"));
  await admin.getByLabel("Username", { exact: true }).fill("admin");
  await admin.getByLabel("Password", { exact: true }).fill(adminPassword);
  await admin.getByRole("button", { name: "Sign in", exact: true }).click();
  await admin.getByRole("heading", { name: "Security at a glance" }).waitFor();
  const csrf = await admin.evaluate(() => sessionStorage.getItem("admin_csrf"));
  async function api(path, body) {
    const response = await admin.request.fetch(url("/api" + path), {
      method: body ? "POST" : "GET",
      headers: { "X-CSRF-Token": csrf },
      ...(body ? { data: body } : {}),
    });
    assert(response.ok(), `API ${path} returned ${response.status()}`);
    return response.json();
  }
  const users = await api("/admin/users?q=" + encodeURIComponent(user));
  const actor = users.items.find((row) => row.username === user);
  assert(
    actor && !actor.blocked,
    "The dedicated smoke-test account must start unblocked",
  );
  await bank.goto(url("/login"));
  async function bankLogin() {
    await bank.getByLabel("Username", { exact: true }).fill(user);
    await bank.getByLabel("Password", { exact: true }).fill(bankPassword);
    await bank.getByRole("button", { name: "Sign in securely" }).click();
    await bank.getByRole("heading", { name: `Hello, ${user}.` }).waitFor();
  }
  await bankLogin();
  const before = await (
    await bank.request.get(url("/api/bank/balance"))
  ).json();
  await bank
    .getByRole("button", { name: "Request a transfer", exact: false })
    .click();
  await bank
    .getByLabel("Demo recipient", { exact: true })
    .fill("Smoke recipient");
  await bank.getByLabel("Amount (INR)", { exact: true }).fill("1.00");
  const transfer = bank.waitForResponse(
    (response) =>
      response.url().endsWith("/api/bank/transfer-request") &&
      response.request().method() === "POST",
  );
  await bank
    .getByRole("button", { name: "Record request", exact: false })
    .click();
  assert((await transfer).ok());
  const after = await (await bank.request.get(url("/api/bank/balance"))).json();
  assert.equal(after.balance_cents, before.balance_cents);
  const polling = process.env.SMOKE_LIVE_TRANSPORT === "poll";
  if (!polling)
    await admin.evaluate(
      () =>
        new Promise((resolve, reject) => {
          window.smokeMessages = [];
          const socket = new WebSocket(
            `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/admin/events`,
          );
          window.smokeSocket = socket;
          socket.onerror = () => reject(Error("WebSocket connection failed"));
          socket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            window.smokeMessages.push(message);
            if (message.type === "connected") resolve();
          };
          setTimeout(
            () => reject(Error("WebSocket connection timed out")),
            15000,
          );
        }),
    );
  let blocked = false;
  try {
    const latest = await api("/admin/events?limit=1");
    const cursor = latest[0]?.id || 0;
    const delivery = polling
      ? admin.waitForResponse(async (response) => {
          if (
            !response.url().includes("/api/admin/events?") ||
            !response.url().includes("order=asc") ||
            !response.ok()
          )
            return false;
          const rows = await response.json();
          return rows.some(
            (row) =>
              row.id > cursor &&
              row.event_type === "BLOCK_ACCOUNT" &&
              row.user_id === actor.id,
          );
        })
      : null;
    const result = await api(`/admin/users/${actor.id}/block`, {
      confirmed: true,
      note: "Deployment smoke verification",
    });
    blocked = true;
    await bank
      .getByRole("button", { name: "View balance", exact: false })
      .click();
    await bank.getByRole("heading", { name: "Access restricted" }).waitFor();
    if (polling) {
      await delivery;
      await admin.getByText("Polling", { exact: true }).first().waitFor();
    } else
      await admin.waitForFunction(
        (id) =>
          window.smokeMessages.some(
            (message) =>
              message.type === "security_alerts" &&
              message.alerts.some((alert) => alert.block_id === id),
          ),
        result.block_id,
      );
  } finally {
    if (blocked)
      await api(`/admin/users/${actor.id}/unblock`, {
        confirmed: true,
        note: "Deployment smoke recovery",
        reset_risk: true,
      });
    await admin.evaluate(() => window.smokeSocket?.close());
  }
  assert.equal(
    (await bank.request.get(url("/api/bank/balance"))).status(),
    401,
  );
  await bank.goto(url("/dashboard"));
  await bankLogin();
  assert.equal((await api("/admin/ml/metrics")).status, "available");
  assert.equal((await api("/admin/detectors/comparison")).status, "available");
  for (const [path, heading] of [
    ["/admin/fsm", "Follow every state transition"],
    ["/admin/analytics", "Models, measured and observed"],
    ["/admin/comparison", "One dataset. Four detectors."],
    ["/admin/simulation", "Explore threats in isolation"],
  ]) {
    await admin.goto(url(path));
    await admin.getByRole("heading", { name: heading, exact: true }).waitFor();
    await admin.reload();
    await admin.getByRole("heading", { name: heading, exact: true }).waitFor();
  }
  assert.equal((await api("/simulation/scenarios")).enabled, false);
  const rejected = await admin.request.post(url("/api/simulation/run"), {
    headers: { "X-CSRF-Token": csrf },
    data: {
      scenario: "normal",
      accounts: [user],
      confirmed: true,
      note: "Production guard smoke check",
    },
  });
  assert.equal(rejected.status(), 403);
  for (const page of [bank, admin]) {
    await page.setViewportSize({ width: 390, height: 900 });
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
  }
  if (base.protocol === "https:") {
    const cookies = await adminContext.cookies();
    assert(cookies.find((cookie) => cookie.name === "pg_admin")?.secure);
  }
  assert.deepEqual(errors, []);
  console.log(
    "PASS: hosted banking, unchanged dummy balance, account block/denial/recovery, revoked session, live alert delivery, model reports, admin deep links/reloads, production lab guard and mobile layout.",
  );
} finally {
  await browser.close();
}
