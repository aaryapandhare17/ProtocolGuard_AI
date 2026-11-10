// @vitest-environment jsdom
import { afterEach, beforeAll, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConfirmDialog from "./ConfirmDialog";
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
afterEach(cleanup);
it("requires a meaningful note and explicit confirmation before unblocking", async () => {
  const user = userEvent.setup(),
    onConfirm = vi.fn().mockResolvedValue(undefined),
    onCancel = vi.fn();
  render(
    <ConfirmDialog
      action={{
        kind: "account_unblock",
        title: "Unblock demo01?",
        message: "Fresh login required",
      }}
      onConfirm={onConfirm}
      onCancel={onCancel}
    />,
  );
  const button = screen.getByRole("button", { name: "Confirm action" });
  expect(button.disabled).toBe(true);
  await user.type(screen.getByLabelText("Review note"), "Reviewed the session");
  expect(button.disabled).toBe(true);
  await user.click(screen.getByLabelText("I confirm this security action"));
  expect(button.disabled).toBe(false);
  await user.click(button);
  expect(onConfirm).toHaveBeenCalledWith({
    confirmed: true,
    note: "Reviewed the session",
    reset_risk: true,
  });
  expect(onCancel).not.toHaveBeenCalled();
});
it("canceling a restriction does not send a mutation", async () => {
  const user = userEvent.setup(),
    onConfirm = vi.fn(),
    onCancel = vi.fn();
  render(
    <ConfirmDialog
      action={{
        kind: "ip_block",
        title: "Restrict address?",
        message: "Network action",
      }}
      onConfirm={onConfirm}
      onCancel={onCancel}
    />,
  );
  expect(screen.getByText(/including administrators/)).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(onCancel).toHaveBeenCalledOnce();
  expect(onConfirm).not.toHaveBeenCalled();
});
it("preserves the review note and displays failed mutation errors", async () => {
  const user = userEvent.setup(),
    onConfirm = vi.fn().mockRejectedValue(new Error("Invalid CSRF token"));
  render(
    <ConfirmDialog
      action={{
        kind: "account_block",
        title: "Block demo01?",
        message: "Account action",
      }}
      onConfirm={onConfirm}
      onCancel={() => {}}
    />,
  );
  await user.type(screen.getByLabelText("Review note"), "Review complete");
  await user.click(screen.getByLabelText("I confirm this security action"));
  await user.click(screen.getByRole("button", { name: "Confirm action" }));
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Invalid CSRF token",
  );
  expect(screen.getByLabelText("Review note").value).toBe("Review complete");
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Confirm action" }).disabled,
    ).toBe(false),
  );
});
