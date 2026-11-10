import { useState } from "react";
import { ArrowRight, Eye, EyeOff, LockKeyhole } from "lucide-react";
import { api } from "../services/admin";
import { Brand } from "../components/UI";
export default function Login({ onLogin }) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [show, setShow] = useState(false);
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const result = await api("/admin/auth/login", {
        method: "POST",
        body: {
          username: form.get("username"),
          password: form.get("password"),
        },
      });
      sessionStorage.setItem("admin_csrf", result.csrf_token);
      onLogin(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="admin-login">
      <div className="login-brand">
        <Brand />
        <span className="subtle-label">RESTRICTED ADMINISTRATOR ACCESS</span>
      </div>
      <div className="login-grid">
        <section className="login-story">
          <p className="eyebrow">CLARITY AT EVERY TRANSITION</p>
          <h1>
            Understand the activity.
            <br />
            <span>Act on the evidence.</span>
          </h1>
          <p>
            One view of session behavior, anomaly evidence, and the accounts
            that need your attention.
          </p>
          <div className="login-rule">
            <span />
            <span />
            <span />
            <span />
          </div>
          <p className="login-footnote">
            Protocol analysis · Machine learning · Human oversight
          </p>
        </section>
        <section className="login-panel">
          <span className="login-lock">
            <LockKeyhole size={22} />
          </span>
          <h2>Administrator sign in</h2>
          <p className="muted">Access your security operations workspace.</p>
          <form onSubmit={submit}>
            <label htmlFor="admin-user">Username</label>
            <input
              id="admin-user"
              name="username"
              autoComplete="username"
              maxLength={80}
              required
              placeholder="Administrator username"
            />
            <label htmlFor="admin-password">Password</label>
            <div className="password-wrap">
              <input
                id="admin-password"
                name="password"
                autoComplete="current-password"
                type={show ? "text" : "password"}
                maxLength={256}
                required
                placeholder="Enter your password"
              />
              <button
                className="icon-button"
                type="button"
                aria-label={show ? "Hide password" : "Show password"}
                onClick={() => setShow(!show)}
              >
                {show ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <button className="button primary full" disabled={busy}>
              {busy ? "Verifying…" : "Sign in"}
              <ArrowRight size={17} />
            </button>
          </form>
          <p className="secure-caption">Verified administrator sessions only</p>
        </section>
      </div>
      <footer className="login-footer">
        ProtocolGuard AI<span>Academic banking security platform</span>
      </footer>
    </main>
  );
}
