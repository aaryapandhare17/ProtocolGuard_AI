// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Simulation from "./Simulation";
import { api } from "../services/admin";
vi.mock("../services/admin", () => ({
  api: vi.fn(),
  dateTime: (value) => value,
}));
vi.mock("../hooks/useResource", () => ({
  useResource: (path) => ({
    data: path.includes("/scenarios")
      ? {
          enabled: true,
          accounts: ["demo01", "demo02"],
          scenarios: [
            {
              id: "normal",
              name: "Normal banking session",
              description: "Local only",
            },
          ],
        }
      : path.includes("/runs/")
        ? {
            id: "saved",
            scenario: "normal",
            status: "completed",
            started_at: "2026-11-11T10:00:00Z",
            result: {},
          }
        : [],
    error: "",
    refresh: vi.fn(),
  }),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
it("requires explicit isolation confirmation and submits only bounded scenario data", async () => {
  const user = userEvent.setup();
  api.mockResolvedValue({ id: "saved", status: "completed" });
  render(
    <MemoryRouter>
      <Simulation />
    </MemoryRouter>,
  );
  const run = screen.getByRole("button", { name: "Run simulation" });
  expect(run.disabled).toBe(true);
  expect(api).not.toHaveBeenCalled();
  await user.click(screen.getByLabelText("Use one shared simulated IP"));
  await user.click(
    screen.getByLabelText("I confirm this run uses isolated demo copies"),
  );
  expect(run.disabled).toBe(false);
  await user.click(run);
  expect(api).toHaveBeenCalledWith("/simulation/run", {
    method: "POST",
    body: {
      scenario: "normal",
      accounts: ["demo01", "demo02"],
      seed: 42,
      shared_ip: true,
      confirmed: true,
      note: "Controlled demonstration",
    },
  });
  expect(await screen.findByRole("status")).toHaveProperty(
    "textContent",
    "Simulation completed and audited.",
  );
});
it("shows errors without pretending a failed request completed", async () => {
  const user = userEvent.setup();
  api.mockRejectedValue(new Error("Two simulations are already running"));
  render(
    <MemoryRouter>
      <Simulation />
    </MemoryRouter>,
  );
  await user.click(
    screen.getByLabelText("I confirm this run uses isolated demo copies"),
  );
  await user.click(screen.getByRole("button", { name: "Run simulation" }));
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Two simulations are already running",
  );
  expect(screen.queryByText("Simulation completed and audited.")).toBeNull();
});
