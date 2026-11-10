import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Plus } from "lucide-react";
import { useResource } from "../hooks/useResource";
import {
  Badge,
  Empty,
  Evidence,
  PageTitle,
  ResourceState,
  SearchBox,
  SectionHeader,
} from "../components/UI";
import { dateTime } from "../services/admin";
export function IPs({ live, onAction }) {
  const [search, setSearch] = useState(""),
    [all, setAll] = useState(false),
    resource = useResource(
      `/admin/suspicious-ips?limit=200&suspicious_only=${!all}`,
      live.revision,
    );
  return (
    <>
      <PageTitle
        eyebrow="INVESTIGATION / NETWORK"
        title="Suspicious IP addresses"
        text="Network evidence and restrictions, kept independent of account risk."
      >
        <button
          className="button primary"
          onClick={() => onAction({ kind: "ip_block" })}
        >
          <Plus size={16} />
          Restrict an IP
        </button>
      </PageTitle>
      <section className="panel">
        <div className="toolbar">
          <SearchBox
            value={search}
            onChange={setSearch}
            placeholder="Filter IP address…"
          />
          <label className="checkbox inline">
            <input
              type="checkbox"
              checked={all}
              onChange={(e) => setAll(e.target.checked)}
            />
            Include benign addresses
          </label>
        </div>
        <ResourceState resource={resource}>
          {(data) => {
            const rows = data.filter((row) => row.ip_address.includes(search));
            return rows.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>IP address</th>
                      <th>Accounts</th>
                      <th>Suspicious events</th>
                      <th>IP risk</th>
                      <th>Status</th>
                      <th>Last activity</th>
                      <th>Controls</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <Link className="mono" to={`/ips/${row.id}`}>
                            {row.ip_address}
                          </Link>
                        </td>
                        <td>{row.associated_user_ids.length}</td>
                        <td>{row.suspicious_event_count}</td>
                        <td>{row.risk_score.toFixed(0)}</td>
                        <td>
                          <Badge value={row.blocked ? "high" : "neutral"}>
                            {row.blocked ? "Restricted" : "Observed"}
                          </Badge>
                        </td>
                        <td className="muted">{dateTime(row.last_seen)}</td>
                        <td>
                          <button
                            className={`button small ${row.blocked ? "secondary" : "ghost-danger"}`}
                            onClick={() =>
                              onAction({
                                kind: row.blocked ? "ip_unblock" : "ip_block",
                                address: row.ip_address,
                              })
                            }
                          >
                            {row.blocked ? "Unblock" : "Restrict"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty text="No matching IP records." />
            );
          }}
        </ResourceState>
      </section>
      <p className="page-footnote">
        An IP may be shared by many legitimate users. Restricting it affects
        every connection from that address.
      </p>
    </>
  );
}
export function IPDetail({ live, onAction }) {
  const { id } = useParams(),
    resource = useResource(`/admin/suspicious-ips/${id}`, live.revision);
  return (
    <>
      <Link className="back-link" to="/ips">
        <ArrowLeft size={15} />
        All IP addresses
      </Link>
      <ResourceState resource={resource}>
        {(data) => (
          <>
            <PageTitle
              eyebrow="NETWORK / ADDRESS DETAIL"
              title={data.ip_address}
              text={`First recorded ${dateTime(data.first_seen)}`}
            >
              <button
                className="button secondary"
                onClick={() =>
                  onAction({
                    kind: data.blocked ? "ip_unblock" : "ip_block",
                    address: data.ip_address,
                  })
                }
              >
                {data.blocked ? "Unblock address" : "Restrict address"}
              </button>
            </PageTitle>
            <div className="detail-stats">
              <article className="panel">
                <span className="muted">Network status</span>
                <strong>{data.blocked ? "Restricted" : "Observed"}</strong>
                <span className="muted">
                  {data.expires_at
                    ? `Expires ${dateTime(data.expires_at)}`
                    : data.blocked
                      ? "Persistent restriction"
                      : "No active restriction"}
                </span>
              </article>
              <article className="panel">
                <span className="muted">IP risk index</span>
                <strong>
                  {data.risk_score}
                  <small>/ 100</small>
                </strong>
                <span className="muted">
                  {data.suspicious_event_count} suspicious events recorded
                </span>
              </article>
              <article className="panel">
                <span className="muted">Associated accounts</span>
                <div className="ip-links">
                  {data.associated_user_ids.length
                    ? data.associated_user_ids.map((user) => (
                        <Link key={user} to={`/users/${user}`}>
                          User #{user}
                        </Link>
                      ))
                    : "None recorded"}
                </div>
              </article>
            </div>
            <section className="panel">
              <SectionHeader title="Recent IP evidence" />
              <div className="assessment">
                <p className="muted">
                  {data.block_reason ||
                    "No active restriction. Account risk is not included in this IP index."}
                </p>
                <Evidence value={data.risk_evidence} />
              </div>
            </section>
            <section className="panel">
              <SectionHeader title="Restriction history" />
              {data.restrictions.length ? (
                data.restrictions.map((row) => (
                  <div className="history-row" key={row.id}>
                    <div>
                      <strong>{row.source} restriction</strong>
                      <p>{row.reason}</p>
                      <small>{dateTime(row.created_at)}</small>
                      <Evidence value={row.evidence} />
                    </div>
                    <Badge value={row.active ? "high" : "low"}>
                      {row.active ? "Active" : "Released"}
                    </Badge>
                  </div>
                ))
              ) : (
                <Empty text="No restrictions recorded." />
              )}
            </section>
            <section className="panel">
              <SectionHeader title="Network event history" />
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Event</th>
                      <th>Account</th>
                      <th>Outcome</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.events.map((row) => (
                      <tr key={row.id}>
                        <td className="muted">{dateTime(row.created_at)}</td>
                        <td className="event-name">{row.type}</td>
                        <td>
                          {row.user_id ? (
                            <Link to={`/users/${row.user_id}`}>
                              User #{row.user_id}
                            </Link>
                          ) : (
                            "Unauthenticated"
                          )}
                        </td>
                        <td>{row.outcome}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </ResourceState>
    </>
  );
}
