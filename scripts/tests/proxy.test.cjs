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
