import { useEffect, useRef, useState } from "react";
import { AlertTriangle, X } from "lucide-react";
export default function ConfirmDialog({ action, onCancel, onConfirm }) {
  const dialog = useRef(null);
  const [note, setNote] = useState(""),
    [confirmed, setConfirmed] = useState(false),
    [reset, setReset] = useState(true);
  const [address, setAddress] = useState(action.address || ""),
    [duration, setDuration] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    const element = dialog.current;
    element.showModal();
    return () => element.close();
  }, []);
  async function submit(event) {
    event.preventDefault();
    if (!confirmed || note.trim().length < 3) return;
    setBusy(true);
    setError("");
    try {
      await onConfirm({
        confirmed: true,
        note: note.trim(),
        ...(action.kind === "account_unblock" ? { reset_risk: reset } : {}),
        ...(action.kind.startsWith("ip_") ? { ip_address: address } : {}),
        ...(action.kind === "ip_block" && duration
          ? { duration_seconds: Number(duration) }
          : {}),
      });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }
  return (
    <dialog
      ref={dialog}
      className="confirm-dialog"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onCancel();
      }}
      aria-labelledby="confirm-title"
    >
      <form onSubmit={submit}>
        <div className="dialog-heading">
          <span className="dialog-icon">
            <AlertTriangle size={22} />
          </span>
          <button
            type="button"
            className="icon-button"
            disabled={busy}
            onClick={onCancel}
            aria-label="Close confirmation"
          >
            <X size={20} />
          </button>
        </div>
        <h2 id="confirm-title">{action.title}</h2>
        <p className="muted">{action.message}</p>
        {action.kind.startsWith("ip_") && (
          <>
            <label htmlFor="ip-address">IP address</label>
            <input
              id="ip-address"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              required
              readOnly={Boolean(action.address)}
            />
            <p className="warning">
              IP restrictions affect every user sharing this address, including
              administrators.
            </p>
          </>
        )}
        {action.kind === "ip_block" && (
          <>
            <label htmlFor="duration">
              Duration in seconds{" "}
              <span className="muted">(blank for persistent)</span>
            </label>
            <input
              id="duration"
              type="number"
              min="5"
              max="86400"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
            />
          </>
        )}
        {action.kind === "account_unblock" && (
          <label className="checkbox">
            <input
              type="checkbox"
              checked={reset}
              onChange={(e) => setReset(e.target.checked)}
            />
            Reset current risk and exclude pre-review activity
          </label>
        )}
        <label htmlFor="admin-note">Review note</label>
        <textarea
          id="admin-note"
          minLength={3}
          maxLength={500}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Explain the reason for this action"
          required
        />
        <label className="checkbox">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          I confirm this security action
        </label>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-actions">
          <button
            type="button"
            className="button secondary"
            disabled={busy}
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            className="button danger"
            disabled={busy || !confirmed || note.trim().length < 3}
          >
            {busy ? "Applying…" : "Confirm action"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
