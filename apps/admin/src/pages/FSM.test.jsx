// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import FSM from "./FSM";
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
  transitions: [],
};
vi.mock("../hooks/useResource", () => ({
  useResource: (path) => ({
    data: path === "/admin/fsm" ? definition : [],
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
