// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { api } from "./admin";
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
});
it("sends same-origin credentials and the CSRF header on protected mutations", async () => {
  sessionStorage.setItem("admin_csrf", "test-csrf");
  const fetch = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => ({ blocked: true }) });
  vi.stubGlobal("fetch", fetch);
  await expect(
    api("/admin/users/1/block", {
      method: "POST",
      body: { confirmed: true, note: "Reviewed" },
    }),
  ).resolves.toEqual({ blocked: true });
  const [path, options] = fetch.mock.calls[0];
  expect(path).toBe("/api/admin/users/1/block");
  expect(options.credentials).toBe("same-origin");
  expect(options.headers["X-CSRF-Token"]).toBe("test-csrf");
  expect(JSON.parse(options.body).confirmed).toBe(true);
});
it("signals expired authentication when an API returns 401", async () => {
  const dispatch = vi.spyOn(window, "dispatchEvent");
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: "Authentication required" }),
      }),
  );
  await expect(api("/admin/overview")).rejects.toThrow(
    "Authentication required",
  );
  expect(dispatch.mock.calls.map(([event]) => event.type)).toContain(
    "admin:unauthorized",
  );
});
it("distinguishes IP denial from a rejected CSRF mutation", async () => {
  const dispatch = vi.spyOn(window, "dispatchEvent");
  const fetch = vi
    .fn()
    .mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({ detail: "Invalid CSRF token" }),
    })
    .mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({ detail: "IP access restricted" }),
    });
  vi.stubGlobal("fetch", fetch);
  await expect(api("/admin/users/1/block")).rejects.toThrow(
    "Invalid CSRF token",
  );
  expect(dispatch).not.toHaveBeenCalled();
  await expect(api("/admin/overview")).rejects.toThrow("IP access restricted");
  expect(dispatch.mock.calls[0][0].type).toBe("admin:restricted");
});
it("preserves cancellation so obsolete loads do not show error banners", async () => {
  const controller = new AbortController();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new DOMException("Canceled", "AbortError")),
  );
  await expect(
    api("/admin/overview", { signal: controller.signal }),
  ).rejects.toHaveProperty("name", "AbortError");
});
