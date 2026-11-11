import { useEffect, useState, lazy, Suspense } from "react";
import {
  Navigate,
  NavLink,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import {
  Activity,
  Bell,
  ChartNoAxesCombined,
  ChevronRight,
  GitBranch,
  Globe,
  LayoutDashboard,
  LogOut,
  Menu,
  RefreshCw,
  Settings as SettingsIcon,
  ShieldAlert,
  SlidersHorizontal,
  TestTube2,
  Users as UsersIcon,
  X,
} from "lucide-react";
import { api } from "./services/admin";
import { useLive } from "./hooks/useLive";
import { Brand } from "./components/UI";
import ConfirmDialog from "./components/ConfirmDialog";
import Login from "./pages/Login";
const Simulation = lazy(() => import("./pages/Simulation"));
const Analytics = lazy(() => import("./pages/Analytics"));
const Comparison = lazy(() => import("./pages/Comparison"));
const FSM = lazy(() => import("./pages/FSM"));
const Overview = lazy(() => import("./pages/Overview"));
import Monitoring from "./pages/Monitoring";
const Users = lazy(() =>
  import("./pages/Users").then((module) => ({ default: module.Users })),
);
const UserDetail = lazy(() =>
  import("./pages/Users").then((module) => ({ default: module.UserDetail })),
);
import { IPs, IPDetail } from "./pages/IPs";
import Alerts from "./pages/Alerts";
import Settings from "./pages/Settings";

const navigation = [
  ["Overview", "/", LayoutDashboard],
  ["Live monitoring", "/monitoring", Activity],
  ["Users", "/users", UsersIcon],
  ["Suspicious IPs", "/ips", Globe],
  ["Security alerts", "/alerts", Bell],
];
function describe(action) {
  if (action.kind === "account_block")
    return {
      ...action,
      title: `Block ${action.name}?`,
      message:
        "All active banking sessions for this account will be revoked. Other accounts and IP restrictions remain independent.",
    };
  if (action.kind === "account_unblock")
    return {
      ...action,
      title: `Unblock ${action.name}?`,
      message:
        "The account will require a fresh login. Historical evidence is preserved. Reset current risk to prevent stale activity from immediately blocking it again.",
    };
  if (action.kind === "ip_block")
    return {
      ...action,
      title: "Restrict network address?",
      message:
        "This will deny requests from the IP, including administrator requests. Restricting your own address may require local development recovery.",
    };
  if (action.kind === "ip_unblock")
    return {
      ...action,
      title: "Unblock network address?",
      message:
        "Release only this IP restriction and reset its recent abuse baseline. Account blocks remain in force.",
    };
  if (action.kind === "alert_resolve")
    return {
      ...action,
      title: "Resolve this alert?",
      message:
        "Mark the alert reviewed. Its account remains blocked until separately unblocked.",
    };
  return {
    ...action,
    title: "Apply security policy?",
    message: `Set automatic account blocking to ${action.values.auto_block_enabled ? "enabled" : "disabled"}, above risk ${action.values.block_threshold}. Existing blocks remain unchanged.`,
  };
}
function Dashboard({ identity, onLogout }) {
  const live = useLive(),
    location = useLocation();
  const [mobile, setMobile] = useState(false),
    [action, setAction] = useState(null),
    [notice, setNotice] = useState("");
  useEffect(() => setMobile(false), [location.pathname]);
  const onAction = (value) => {
    setNotice("");
    setAction(describe(value));
  };
  async function confirm(body) {
    const paths = {
      account_block: `/admin/users/${action.id}/block`,
      account_unblock: `/admin/users/${action.id}/unblock`,
      ip_block: "/admin/ips/block",
      ip_unblock: "/admin/ips/unblock",
      alert_resolve: `/admin/alerts/${action.id}/resolve`,
      settings: "/admin/settings/security",
    };
    await api(paths[action.kind], {
      method: "POST",
      body: { ...body, ...(action.values || {}) },
    });
    setAction(null);
    setNotice("Security action saved and audited.");
    live.refresh();
  }
  const title =
    navigation.find(([, path]) =>
      path === "/"
        ? location.pathname === "/"
        : location.pathname.startsWith(path),
    )?.[0] ||
    (location.pathname.startsWith("/simulation")
      ? "Simulation lab"
      : location.pathname.startsWith("/analytics")
        ? "ML analytics"
        : location.pathname.startsWith("/comparison")
          ? "Detector comparison"
          : location.pathname.startsWith("/fsm")
            ? "FSM visualizer"
            : location.pathname.startsWith("/settings")
              ? "Settings"
              : "Security operations");
  return (
    <div className="admin-shell">
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <Brand />
        <div className="workspace-label">
          <span className="workspace-icon">PG</span>
          <div>
            Banking security<small>Development workspace</small>
          </div>
          <ChevronRight size={14} />
        </div>
        <span className="nav-label">WORKSPACE</span>
        <nav aria-label="Main navigation">
          {navigation.map(([label, path, Icon]) => (
            <NavLink key={path} to={path} end={path === "/"}>
              <Icon size={17} />
              {label}
            </NavLink>
          ))}
          <span className="nav-label analysis-label">ANALYSIS</span>
          <NavLink to="/fsm">
            <GitBranch size={17} />
            FSM visualizer
          </NavLink>
          <NavLink to="/analytics">
            <ChartNoAxesCombined size={17} />
            ML analytics
          </NavLink>
          <NavLink to="/comparison">
            <SlidersHorizontal size={17} />
            Detector comparison
          </NavLink>
          <NavLink to="/simulation">
            <TestTube2 size={17} />
            Simulation lab
          </NavLink>
          <NavLink to="/settings">
            <SettingsIcon size={17} />
            Settings
          </NavLink>
        </nav>
        <div className="sidebar-footer">
          <span className="small-dot" />
          <div>
            ProtocolGuard AI<small>Academic demonstration</small>
          </div>
        </div>
      </aside>
      {mobile && (
        <button
          className="sidebar-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <div className="workspace">
        <header className="topbar">
          <div className="topbar-title">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobile(!mobile)}
            >
              <Menu size={21} />
            </button>
            <span className="breadcrumb">Workspace</span>
            <ChevronRight size={13} />
            <strong>{title}</strong>
          </div>
          <div className="topbar-actions">
            <span
              className={`connection ${live.status === "Live" ? "online" : ""}`}
            >
              <i />
              {live.status}
            </span>
            <button
              className="icon-button"
              aria-label="Refresh dashboard"
              onClick={live.refresh}
            >
              <RefreshCw size={16} />
            </button>
            <span className="profile">
              <span className="avatar">
                {identity.username.slice(0, 2).toUpperCase()}
              </span>
              <span>
                {identity.username}
                <small>Administrator</small>
              </span>
            </span>
            <button
              className="icon-button"
              aria-label="Log out"
              onClick={onLogout}
            >
              <LogOut size={17} />
            </button>
          </div>
        </header>
        <main className="dashboard-content">
          {notice && (
            <div className="notice" role="status">
              {notice}
              <button
                aria-label="Dismiss notification"
                className="icon-button"
                onClick={() => setNotice("")}
              >
                <X size={14} />
              </button>
            </div>
          )}
          {live.status !== "Live" && (
            <div className="connection-note">
              {live.status === "Connecting"
                ? "Connecting to live monitoring…"
                : "Live stream unavailable. Data panels refresh periodically; restricted connections require review."}
            </div>
          )}
          <Suspense
            fallback={
              <div className="loading" role="status">
                Loading workspace…
              </div>
            }
          >
            <Routes>
              <Route path="/" element={<Overview live={live} />} />
              <Route path="/simulation" element={<Simulation />} />
              <Route path="/analytics" element={<Analytics live={live} />} />
              <Route path="/comparison" element={<Comparison live={live} />} />
              <Route path="/fsm" element={<FSM live={live} />} />
              <Route path="/monitoring" element={<Monitoring live={live} />} />
              <Route
                path="/users"
                element={<Users live={live} onAction={onAction} />}
              />
              <Route
                path="/users/:id"
                element={<UserDetail live={live} onAction={onAction} />}
              />
              <Route
                path="/ips"
                element={<IPs live={live} onAction={onAction} />}
              />
              <Route
                path="/ips/:id"
                element={<IPDetail live={live} onAction={onAction} />}
              />
              <Route
                path="/alerts"
                element={<Alerts live={live} onAction={onAction} />}
              />
              <Route
                path="/settings"
                element={<Settings live={live} onAction={onAction} />}
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
          <footer className="dashboard-footer">
            ProtocolGuard AI
            <span>Dummy banking data · Evidence-based security decisions</span>
          </footer>
        </main>
      </div>
      {action && (
        <ConfirmDialog
          key={`${action.kind}-${action.id || action.address || ""}`}
          action={action}
          onCancel={() => setAction(null)}
          onConfirm={confirm}
        />
      )}
    </div>
  );
}
export default function App() {
  const [identity, setIdentity] = useState(undefined),
    [restricted, setRestricted] = useState(false),
    [error, setError] = useState("");
  async function check(signal) {
    setError("");
    try {
      const result = await api("/admin/auth/me", { signal });
      setRestricted(false);
      setIdentity(sessionStorage.getItem("admin_csrf") ? result : null);
    } catch (err) {
      if (err.name === "AbortError") return;
      if (err.status === 401) setIdentity(null);
      else if (err.status === 403) setRestricted(true);
      else setError(err.message);
    }
  }
  useEffect(() => {
    const controller = new AbortController();
    check(controller.signal);
    const lost = () => setIdentity(null),
      denied = () => setRestricted(true);
    window.addEventListener("admin:unauthorized", lost);
    window.addEventListener("admin:restricted", denied);
    return () => {
      controller.abort();
      window.removeEventListener("admin:unauthorized", lost);
      window.removeEventListener("admin:restricted", denied);
    };
  }, []);
  async function logout() {
    try {
      await api("/admin/auth/logout", { method: "POST" });
      sessionStorage.removeItem("admin_csrf");
      setIdentity(null);
    } catch (err) {
      setError(err.message);
    }
  }
  if (restricted)
    return (
      <main className="admin-restricted">
        <Brand />
        <ShieldAlert size={42} />
        <h1>Network access restricted</h1>
        <p>
          This IP address cannot access administrative services. Review the
          restriction from an unrestricted connection or use the documented
          local recovery process.
        </p>
        <button className="button secondary" onClick={() => check()}>
          Try again
        </button>
      </main>
    );
  if (error)
    return (
      <main className="admin-restricted">
        <Brand />
        <h1>Unable to connect</h1>
        <p role="alert">{error}</p>
        <button className="button secondary" onClick={() => check()}>
          Retry connection
        </button>
      </main>
    );
  if (identity === undefined)
    return (
      <main className="admin-loading">
        <Brand />
        <p role="status">Verifying administrator session…</p>
      </main>
    );
  return identity ? (
    <Dashboard identity={identity} onLogout={logout} />
  ) : (
    <Login onLogin={setIdentity} />
  );
}
