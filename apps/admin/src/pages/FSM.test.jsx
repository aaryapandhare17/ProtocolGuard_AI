// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import FSM from "./FSM";
import Alerts from "./Alerts";
import { api } from "../services/admin";
vi.mock("../services/admin", () => ({
  api: vi.fn(),
  dateTime: (value) => value,
}));
const definition = {
  version: "bank-session-v1",
  states: ["LOGGED_OUT", "AUTHENTICATING", "AUTHENTICATED", "CLOSED"],
  initial_state: "LOGGED_OUT",
  accepting_states: ["CLOSED"],
  alphabet: ["LOGIN_ATTEMPT", "LOGIN_SUCCESS", "LOGOUT"],
  transitions: [
    { from: "LOGGED_OUT", to: "AUTHENTICATING", event: "LOGIN_ATTEMPT", explicit: true },
  ],
};
vi.mock("../hooks/useResource", () => ({
  useResource: (path) => ({
    data:
      path === "/admin/fsm"
        ? definition
        : path === "/admin/alerts?limit=200"
          ? [{
              id: 1, user_id: 1, reason: "Automatic restriction",
              replay: { session_id: "recorded", event_id: 101 },
              evidence: { event_id: 101 },
              created_at: "2026-11-10T10:00:00Z",
            }, {
              id: 2, user_id: 2, reason: "Manual restriction",
              evidence: {},
              created_at: "2026-11-10T10:01:00Z",
            }]
          : [],
    error: "",
    refresh: vi.fn(),
  }),
}));
vi.mock("../components/FSMGraph", () => ({
  default: ({ currentState }) => <div data-testid="graph">{currentState}</div>,
}));
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
});
it("steps and pauses without sending a mutation, and labels partial evidence", async () => {
  const transitions = [
    {
      state_before: "LOGGED_OUT",
      state_after: "AUTHENTICATING",
      event: "LOGIN_ATTEMPT",
      valid: true,
    },
    {
      state_before: "AUTHENTICATING",
      state_after: "AUTHENTICATED",
      event: "LOGIN_SUCCESS",
      valid: true,
    },
    {
      state_before: "AUTHENTICATED",
      state_after: "CLOSED",
      event: "LOGOUT",
      valid: true,
    },
  ];
  api.mockResolvedValue({
    initial_state: "LOGGED_OUT",
    final_state: "CLOSED",
    complete_trace: false,
    classification: "accepted",
    user_id: 1,
    transitions,
    persisted_events: transitions.map((row, index) => ({
      id: index + 1,
      timestamp: "2026-11-10T10:00:00Z",
    })),
  });
  render(
    <MemoryRouter initialEntries={["/fsm?session=recorded"]}>
      <FSM live={{ revision: 0 }} />
    </MemoryRouter>,
  );
  await screen.findByText(/Partial historical trace/);
  expect(screen.getByTestId("graph").textContent).toBe("LOGGED_OUT");
  fireEvent.click(screen.getByRole("button", { name: "Next transition" }));
  expect(screen.getByTestId("graph").textContent).toBe("AUTHENTICATING");
  fireEvent.click(screen.getByRole("button", { name: "Reset replay" }));
  vi.useFakeTimers();
  fireEvent.click(screen.getByRole("button", { name: "Play replay" }));
  await act(async () => {
    vi.advanceTimersByTime(800);
  });
  expect(screen.getByTestId("graph").textContent).toBe("AUTHENTICATING");
  fireEvent.click(screen.getByRole("button", { name: "Pause replay" }));
  await act(async () => {
    vi.advanceTimersByTime(3000);
  });
  expect(screen.getByTestId("graph").textContent).toBe("AUTHENTICATING");
  fireEvent.change(screen.getByLabelText("Replay checkpoint"), {
    target: { value: "3" },
  });
  expect(screen.getByTestId("graph").textContent).toBe("CLOSED");
  expect(screen.getByRole("button", { name: "Next transition" }).disabled).toBe(
    true,
  );
  expect(api).toHaveBeenCalledTimes(1);
  expect(api.mock.calls[0][0]).toBe("/admin/fsm/sessions/recorded");
  expect(api.mock.calls[0][1].method).toBeUndefined();
});

it("links alert evidence to the exact transition without playing the session", async () => {
  api.mockResolvedValue({
    initial_state: "LOGGED_OUT",
    final_state: "AUTHENTICATED",
    complete_trace: true,
    classification: "valid prefix",
    user_id: 1,
    transitions: [
      {
        state_before: "LOGGED_OUT",
        state_after: "AUTHENTICATING",
        event: "LOGIN_ATTEMPT",
        valid: true,
      },
      {
        state_before: "AUTHENTICATING",
        state_after: "AUTHENTICATED",
        event: "LOGIN_SUCCESS",
        valid: true,
      },
    ],
    persisted_events: [
      { id: 78, timestamp: "2026-11-10T10:00:00Z" },
      { id: 101, timestamp: "2026-11-10T10:00:01Z" },
    ],
  });
  const live = { revision: 0 };
  render(
    <MemoryRouter initialEntries={["/alerts"]}>
      <Routes>
        <Route path="/alerts" element={<Alerts live={live} onAction={vi.fn()} />} />
        <Route path="/fsm" element={<FSM live={live} />} />
      </Routes>
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("link", { name: "Replay triggering event" }));
  await screen.findByText("Alert trigger");
  expect(screen.getByTestId("graph").textContent).toBe("AUTHENTICATED");
  expect(
    screen.getByRole("button", { name: "Replay through transition 2" }).getAttribute("aria-current"),
  ).toBe("step");
  expect(screen.getByRole("button", { name: "Play replay" })).toBeTruthy();
  expect(api).toHaveBeenCalledWith("/admin/fsm/sessions/recorded", {
    signal: expect.any(AbortSignal),
  });
});
