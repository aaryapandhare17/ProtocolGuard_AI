import { useState } from "react";
import { Link } from "react-router-dom";
import { useResource } from "../hooks/useResource";
import {
  Badge,
  Empty,
  Evidence,
  PageTitle,
  ResourceState,
} from "../components/UI";
import { dateTime } from "../services/admin";
export default function Alerts({ live, onAction }) {
  const [open, setOpen] = useState(true),
    accounts = useResource("/admin/alerts?limit=200", live.revision),
    ips = useResource("/admin/ip-alerts?limit=200", live.revision);
  return (
    <>
      <PageTitle
        eyebrow="OPERATIONS / SECURITY ALERTS"
        title="Incidents that need attention"
        text="Persistent alerts with the evidence behind every restriction."
      />
      <div className="alert-filters">
        <label className="checkbox inline">
          <input
            type="checkbox"
            checked={open}
            onChange={(e) => setOpen(e.target.checked)}
          />
          Unresolved only
        </label>
      </div>
      <ResourceState resource={accounts}>
        {(accountRows) => (
          <ResourceState resource={ips}>
            {(ipRows) => {
              const rows = [
                ...accountRows.map((row) => ({ ...row, kind: "account" })),
                ...ipRows.map((row) => ({ ...row, kind: "ip" })),
              ]
                .filter((row) => !open || !row.resolved_at)
                .sort(
                  (a, b) => new Date(b.created_at) - new Date(a.created_at),
                );
              return rows.length ? (
                <div className="alert-list">
                  {rows.map((row) => (
                    <article
                      className="panel alert-card"
                      key={`${row.kind}-${row.id}`}
                    >
                      <div className="alert-card-top">
                        <Badge value={row.resolved_at ? "low" : "high"}>
                          {row.resolved_at ? "Resolved" : "High severity"}
                        </Badge>
                        <span className="muted">
                          {dateTime(row.created_at)}
                        </span>
                      </div>
                      <h2>
                        {row.kind === "account"
                          ? `Account restriction · User #${row.user_id}`
                          : `Network restriction · ${row.ip_address}`}
                      </h2>
                      <p>{row.reason}</p>
                      <Evidence value={row.evidence} />
                      <div className="alert-actions">
                        {row.kind === "account" ? (
                          <>
                            <Link
                              className="button small secondary"
                              to={`/users/${row.user_id}`}
                            >
                              Review account
                            </Link>
                            {!row.resolved_at && (
                              <button
                                className="button small secondary"
                                onClick={() =>
                                  onAction({
                                    kind: "alert_resolve",
                                    id: row.id,
                                  })
                                }
                              >
                                Resolve alert
                              </button>
                            )}
                          </>
                        ) : (
                          <button
                            className="button small secondary"
                            disabled={Boolean(row.resolved_at)}
                            onClick={() =>
                              onAction({
                                kind: "ip_unblock",
                                address: row.ip_address,
                              })
                            }
                          >
                            Review and unblock IP
                          </button>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <section className="panel">
                  <Empty text="No alerts match this view." />
                </section>
              );
            }}
          </ResourceState>
        )}
      </ResourceState>
    </>
  );
}
