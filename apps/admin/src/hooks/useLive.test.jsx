// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../services/admin";
import { useLive } from "./useLive";
vi.mock("../services/admin", () => ({ api: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});
it("polls ordered events through the same-origin API without creating a WebSocket", async () => {
  vi.useFakeTimers();
  vi.stubEnv("VITE_LIVE_TRANSPORT", "poll");
  const socket = vi.fn();
  vi.stubGlobal("WebSocket", socket);
  api
    .mockResolvedValueOnce([{ id: 4 }, { id: 3 }])
    .mockResolvedValueOnce([{ id: 5 }, { id: 6 }]);
  const view = renderHook(() => useLive());
  await act(async () => {});
  expect(view.result.current.status).toBe("Polling");
  expect(socket).not.toHaveBeenCalled();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
  });
  expect(api).toHaveBeenLastCalledWith(
    "/admin/events?limit=200&after_id=4&order=asc",
  );
  expect(view.result.current.events.map((e) => e.id)).toEqual([6, 5, 4, 3]);
  view.unmount();
  const count = api.mock.calls.length;
  await act(async () => {
    await vi.advanceTimersByTimeAsync(6000);
  });
  expect(api).toHaveBeenCalledTimes(count);
});
it("stops polling after authentication loss", async () => {
  vi.useFakeTimers();
  vi.stubEnv("VITE_LIVE_TRANSPORT", "poll");
  api.mockRejectedValue(Object.assign(new Error("Expired"), { status: 401 }));
  const view = renderHook(() => useLive());
  await act(async () => {});
  expect(view.result.current.status).toBe("Unavailable");
  await act(async () => {
    await vi.advanceTimersByTimeAsync(9000);
  });
  expect(api).toHaveBeenCalledTimes(1);
});
