import { Search, ArrowUpRight, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { dateTime } from "../services/admin";
export function Brand() {
  return (
    <span className="brand">
      <ShieldCheck size={23} />
      <span>
        ProtocolGuard<span className="brand-ai"> AI</span>
        <small>SECURITY OPERATIONS</small>
      </span>
    </span>
  );
}
export function Badge({ value, children }) {
  return <span className={`badge ${value || ""}`}>{children || value}</span>;
}
export function PageTitle({ eyebrow, title, text, children }) {
  return (
    <div className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow || "SECURITY OPERATIONS"}</p>
        <h1>{title}</h1>
        {text && <p className="muted">{text}</p>}
      </div>
      {children}
    </div>
  );
}
export function ResourceState({ resource, children }) {
  if (resource.error && resource.data === null)
    return (
      <div className="error" role="alert">
        {resource.error}
        <button onClick={resource.refresh}>Retry</button>
      </div>
    );
  if (resource.data === null)
    return (
      <div className="loading" role="status">
        Loading security data…
      </div>
    );
  return (
    <>
      {resource.error && (
        <div className="error" role="alert">
          {resource.error}
          <button onClick={resource.refresh}>Retry</button>
        </div>
      )}
      {children(resource.data)}
    </>
  );
}
export function Empty({ text = "No activity recorded yet." }) {
  return <div className="empty">{text}</div>;
}
export function SearchBox({ value, onChange, placeholder }) {
  return (
    <label className="search">
      <Search size={16} />
      <input
        aria-label={placeholder}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
export function EventsTable({ events, compact = false }) {
  if (!events.length) return <Empty />;
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Account</th>
            <th>Action</th>
            {!compact && <th>Source IP</th>}
            <th>Risk</th>
            <th>Outcome</th>
          </tr>
        </thead>
        <tbody>
          {events.map((row) => (
            <tr key={row.id} data-event-id={row.id}>
              <td className="muted nowrap">{dateTime(row.created_at)}</td>
              <td>
                {row.user_id ? (
                  <Link to={`/users/${row.user_id}`}>
                    {row.username || `User ${row.user_id}`}
                  </Link>
                ) : row.account_type === "admin" ? (
                  <span>
                    {row.username} <small className="muted">· Admin</small>
                  </span>
                ) : (
                  <span className="muted">Unauthenticated</span>
                )}
              </td>
              <td>
                <span className="event-name">{row.event_type}</span>
                {row.simulated && (
                  <small className="simulated">Simulated</small>
                )}
              </td>
              {!compact && <td className="mono">{row.ip}</td>}
              <td>
                {row.risk_score == null ? (
                  <span className="muted">—</span>
                ) : (
                  <span
                    className={`risk-number ${row.risk_score > 60 ? "high" : row.risk_score >= 30 ? "monitoring" : ""}`}
                  >
                    {row.risk_score.toFixed(1)}
                  </span>
                )}
              </td>
              <td>
                <Badge value={row.outcome === "success" ? "low" : "denied"}>
                  {row.outcome}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function SectionHeader({ title, to, children }) {
  return (
    <div className="section-header">
      <h2>{title}</h2>
      {to ? (
        <Link className="text-link" to={to}>
          View all <ArrowUpRight size={14} />
        </Link>
      ) : (
        children
      )}
    </div>
  );
}
export function Evidence({ value }) {
  return (
    <details className="evidence">
      <summary>Inspect evidence</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}
