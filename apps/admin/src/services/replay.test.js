import { expect, it } from "vitest";
import { checkpoint, transitionGroups } from "./replay";
const report = {
  initial_state: "LOGGED_OUT",
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
    {
      state_before: "AUTHENTICATED",
      state_after: "CLOSED",
      event: "LOGOUT",
      valid: true,
    },
  ],
};
it("distinguishes initial/ongoing prefixes from accepted completion", () => {
  expect(checkpoint(report, 0, ["CLOSED"])).toMatchObject({
    state: "LOGGED_OUT",
    classification: "valid prefix",
    violations: 0,
  });
  expect(checkpoint(report, 2, ["CLOSED"])).toMatchObject({
    state: "AUTHENTICATED",
    classification: "valid prefix",
  });
  expect(checkpoint(report, 3, ["CLOSED"])).toMatchObject({
    state: "CLOSED",
    classification: "accepted",
  });
  expect(checkpoint(report, 99, ["CLOSED"]).position).toBe(3);
  expect(checkpoint(report, -1, ["CLOSED"]).position).toBe(0);
});
it("preserves violations and handles blocked and partial initial states", () => {
  const rejected = {
    initial_state: "AUTHENTICATED",
    transitions: [
      {
        state_before: "AUTHENTICATED",
        state_after: "REJECTED",
        event: "LOGIN_SUCCESS",
        valid: false,
      },
    ],
  };
  expect(checkpoint(rejected, 0, ["CLOSED"]).state).toBe("AUTHENTICATED");
  expect(checkpoint(rejected, 1, ["CLOSED"])).toMatchObject({
    classification: "suspicious",
    violations: 1,
    state: "REJECTED",
  });
  expect(
    checkpoint({ initial_state: "BLOCKED", transitions: [] }, 0, ["CLOSED"])
      .classification,
  ).toBe("suspicious");
});
it("groups explicit edges but adds only the selected default rejecting edge", () => {
  const definition = {
    transitions: [
      {
        from: "AUTHENTICATED",
        to: "VIEWING_ACCOUNT",
        event: "VIEW_BALANCE",
        explicit: true,
      },
      {
        from: "AUTHENTICATED",
        to: "VIEWING_ACCOUNT",
        event: "VIEW_HISTORY",
        explicit: true,
      },
      {
        from: "AUTHENTICATED",
        to: "REJECTED",
        event: "LOGIN_SUCCESS",
        explicit: false,
      },
      {
        from: "AUTHENTICATED",
        to: "BLOCKED",
        event: "BLOCK_ACCOUNT",
        explicit: true,
      },
    ],
  };
  expect(transitionGroups(definition, null)).toHaveLength(1);
  expect(transitionGroups(definition, null)[0].events).toEqual([
    "VIEW_BALANCE",
    "VIEW_HISTORY",
  ]);
  const current = {
    state_before: "AUTHENTICATED",
    state_after: "REJECTED",
    event: "LOGIN_SUCCESS",
    valid: false,
  };
  expect(
    transitionGroups(definition, current).find((edge) => edge.active),
  ).toMatchObject({ invalid: true, target: "REJECTED" });
  expect(transitionGroups(definition, null, true)).toHaveLength(2);
});
