const { test } = require("node:test");
const assert = require("node:assert/strict");
const proxy = require("../../api/proxy.js");
function response() {
  return {
    headers: {},
    statusCode: 200,
    setHeader(k, v) {
      this.headers[k] = v;
    },
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(body) {
      this.body = body;
      return this;
    },
    end(body) {
      this.body = body;
    },
  };
}
test("server-only origin validation rejects credentials, paths and non-HTTPS targets", () => {
  assert.equal(
    proxy.backendOrigin("https://backend.up.railway.app"),
    "https://backend.up.railway.app",
  );
  for (const value of [
    "http://backend.test",
    "https://a:b@backend.test",
    "https://backend.test/path",
    "https://backend.test?q=x",
    undefined,
  ])
    assert.throws(() => proxy.backendOrigin(value));
});
test("forwards sessions, CSRF and origin without trusting client proxy headers; preserves status/cookies", async () => {
  const originalFetch = global.fetch,
    originalOrigin = process.env.BACKEND_ORIGIN;
  process.env.BACKEND_ORIGIN = "https://backend.up.railway.app";
  let observed;
  global.fetch = async (url, options) => {
    observed = { url, options };
    return new Response('{"ok":true}', {
      status: 401,
      headers: {
        "Content-Type": "application/json",
        "Set-Cookie": "pg_admin=token; Secure; HttpOnly; SameSite=Strict",
      },
    });
  };
  try {
    const out = response();
    await proxy(
      {
        method: "POST",
        url: "/api/admin/auth/login?x=1",
        headers: {
          cookie: "pg_admin=old",
          "x-csrf-token": "csrf",
          origin: "https://front.vercel.app",
          "x-forwarded-for": "spoofed",
          host: "spoofed",
        },
        body: { username: "admin", password: "test-only" },
      },
      out,
    );
    assert.equal(out.statusCode, 401);
    assert.equal(
      String(observed.url),
      "https://backend.up.railway.app/api/admin/auth/login?x=1",
    );
    assert.equal(observed.options.headers.cookie, "pg_admin=old");
    assert.equal(observed.options.headers["x-csrf-token"], "csrf");
    assert.equal(observed.options.headers.origin, "https://front.vercel.app");
    assert(!observed.options.headers["x-forwarded-for"]);
    assert(!observed.options.headers.host);
    assert.equal(observed.options.redirect, "manual");
    assert(out.headers["Set-Cookie"][0].includes("HttpOnly"));
    assert.equal(out.headers["Cache-Control"], "private, no-store");
  } finally {
    global.fetch = originalFetch;
    if (originalOrigin === undefined) delete process.env.BACKEND_ORIGIN;
    else process.env.BACKEND_ORIGIN = originalOrigin;
  }
});
test("returns clear configuration, payload and upstream failures", async () => {
  const originalFetch = global.fetch,
    originalOrigin = process.env.BACKEND_ORIGIN;
  try {
    delete process.env.BACKEND_ORIGIN;
    let out = response();
    await proxy({ method: "GET", url: "/api/health", headers: {} }, out);
    assert.equal(out.statusCode, 503);
    process.env.BACKEND_ORIGIN = "https://backend.test";
    out = response();
    await proxy(
      {
        method: "POST",
        url: "/api/test",
        headers: {},
        body: "x".repeat(65537),
      },
      out,
    );
    assert.equal(out.statusCode, 413);
    global.fetch = async () => {
      throw Error("private upstream detail");
    };
    out = response();
    await proxy({ method: "GET", url: "/api/health", headers: {} }, out);
    assert.equal(out.statusCode, 502);
    assert(!JSON.stringify(out.body).includes("private upstream detail"));
  } finally {
    global.fetch = originalFetch;
    if (originalOrigin === undefined) delete process.env.BACKEND_ORIGIN;
    else process.env.BACKEND_ORIGIN = originalOrigin;
  }
});

test("converts a hosting wake-up page into retryable API feedback", async () => {
  const originalFetch = global.fetch,
    originalOrigin = process.env.BACKEND_ORIGIN;
  process.env.BACKEND_ORIGIN = "https://backend.test";
  global.fetch = async () =>
    new Response("<html>Hosting loading page</html>", {
      status: 503,
      headers: { "content-type": "text/html" },
    });
  try {
    const out = response();
    await proxy({ method: "GET", url: "/api/health", headers: {} }, out);
    assert.equal(out.statusCode, 503);
    assert.equal(out.headers["Retry-After"], "10");
    assert(out.body.detail.includes("starting"));
    assert(!JSON.stringify(out.body).includes("<html>"));
  } finally {
    global.fetch = originalFetch;
    if (originalOrigin === undefined) delete process.env.BACKEND_ORIGIN;
    else process.env.BACKEND_ORIGIN = originalOrigin;
  }
});

test("routes nested Vercel rewrites to the original backend path and preserves query filters", async () => {
  const originalFetch = global.fetch,
    originalOrigin = process.env.BACKEND_ORIGIN;
  process.env.BACKEND_ORIGIN = "https://backend.test";
  let observed;
  global.fetch = async (url) => {
    observed = String(url);
    return new Response("{}", {
      headers: { "content-type": "application/json" },
    });
  };
  try {
    for (const request of [
      { url: "/api/proxy?__pg_path=admin%2Fauth%2Fme", query: {} },
      {
        url: "/api/proxy?limit=10&after_id=2",
        query: { __pg_path: "admin/events" },
      },
      {
        url: "/api/admin/events?limit=10&__pg_path=admin/events",
        query: { __pg_path: "admin/events" },
      },
    ]) {
      const out = response();
      await proxy({ method: "GET", headers: {}, ...request }, out);
      assert.equal(out.statusCode, 200);
      assert(!observed.includes("__pg_path"));
      const target = new URL(observed);
      assert.equal(target.origin, "https://backend.test");
      assert.equal(
        target.pathname,
        request.url.includes("auth")
          ? "/api/admin/auth/me"
          : "/api/admin/events",
      );
      if (request.url.includes("limit"))
        assert.equal(target.searchParams.get("limit"), "10");
    }
    const out = response();
    await proxy(
      {
        method: "GET",
        headers: {},
        url: "/api/proxy?__pg_path=https%3A%2F%2Fevil.test",
      },
      out,
    );
    assert.equal(out.statusCode, 404);
  } finally {
    global.fetch = originalFetch;
    if (originalOrigin === undefined) delete process.env.BACKEND_ORIGIN;
    else process.env.BACKEND_ORIGIN = originalOrigin;
  }
});

test("visitor address comes from the Vercel edge and is signed independently of spoofed forwarding headers", () => {
  const clientIpHeaders = require("../../server/client-ip.cjs");
  const { createHmac } = require("node:crypto");
  const key = "public-test-key-only-not-for-production-12345";
  const request = {
    method: "POST",
    headers: {
      "x-vercel-forwarded-for": "203.0.113.15",
      "x-forwarded-for": "198.51.100.99",
    },
  };
  const url = new URL("https://backend.test/api/auth/login");
  const headers = clientIpHeaders(
    request,
    url,
    { VERCEL: "1", CLIENT_IP_SIGNING_SECRET: key },
    1700000000000,
  );
  assert.equal(headers["x-protocolguard-client-ip"], "203.0.113.15");
  assert.equal(
    headers["x-protocolguard-client-signature"],
    createHmac("sha256", key)
      .update("pg-ip-v1\n1700000000\nPOST\n/api/auth/login\n203.0.113.15")
      .digest("hex"),
  );
  assert.deepEqual(clientIpHeaders(request, url, {}, 1700000000000), {});
  assert.deepEqual(
    clientIpHeaders(
      request,
      url,
      { CLIENT_IP_SIGNING_SECRET: key },
      1700000000000,
    ),
    {},
  );
  assert.throws(() =>
    clientIpHeaders(request, url, {
      VERCEL: "1",
      CLIENT_IP_SIGNING_SECRET: "short",
    }),
  );
  assert.throws(() =>
    clientIpHeaders(
      { method: "POST", headers: { "x-forwarded-for": "203.0.113.15" } },
      url,
      { VERCEL: "1", CLIENT_IP_SIGNING_SECRET: key },
    ),
  );
  assert.throws(() =>
    clientIpHeaders(
      {
        method: "POST",
        headers: { "x-vercel-forwarded-for": "203.0.113.15, 198.51.100.99" },
      },
      url,
      { VERCEL: "1", CLIENT_IP_SIGNING_SECRET: key },
    ),
  );
});

test("API bridge attaches fresh signatures and never relays forged private metadata", async () => {
  const originalFetch = global.fetch,
    originalNow = Date.now;
  const names = ["BACKEND_ORIGIN", "CLIENT_IP_SIGNING_SECRET", "VERCEL"];
  const previous = Object.fromEntries(
    names.map((name) => [name, process.env[name]]),
  );
  process.env.BACKEND_ORIGIN = "https://backend.test";
  process.env.CLIENT_IP_SIGNING_SECRET =
    "public-test-key-only-not-for-production-12345";
  process.env.VERCEL = "1";
  Date.now = () => 1700000000000;
  let observed;
  global.fetch = async (_url, options) => {
    observed = options.headers;
    return new Response("{}", {
      headers: { "content-type": "application/json" },
    });
  };
  try {
    const out = response();
    await proxy(
      {
        method: "GET",
        url: "/api/auth/me",
        headers: {
          "x-vercel-forwarded-for": "203.0.113.15",
          "x-forwarded-for": "198.51.100.99",
          "x-protocolguard-client-ip": "198.51.100.99",
          "x-protocolguard-client-signature": "forged",
        },
      },
      out,
    );
    assert.equal(out.statusCode, 200);
    assert.equal(observed["x-protocolguard-client-ip"], "203.0.113.15");
    assert.equal(observed["x-protocolguard-client-time"], "1700000000");
    assert.equal(
      observed["x-protocolguard-client-signature"],
      require("node:crypto")
        .createHmac("sha256", process.env.CLIENT_IP_SIGNING_SECRET)
        .update("pg-ip-v1\n1700000000\nGET\n/api/auth/me\n203.0.113.15")
        .digest("hex"),
    );
    assert(
      !Object.keys(out.headers).some((name) =>
        name.startsWith("x-protocolguard-client-"),
      ),
    );
  } finally {
    global.fetch = originalFetch;
    Date.now = originalNow;
    for (const name of names)
      if (previous[name] === undefined) delete process.env[name];
      else process.env[name] = previous[name];
  }
});
