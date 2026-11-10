import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ArrowUpRight, ShieldBan, ShieldCheck } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { useDebounce, useResource } from "../hooks/useResource";
import {
  Badge,
  Empty,
  Evidence,
  EventsTable,
  PageTitle,
  ResourceState,
  SearchBox,
  SectionHeader,
} from "../components/UI";
import { dateTime, shortTime } from "../services/admin";
export function Users({ live, onAction }) {
  const [search, setSearch] = useState(""),
    [offset, setOffset] = useState(0);
  const query = useDebounce(search),
    resource = useResource(
      `/admin/users?q=${encodeURIComponent(query)}&offset=${offset}&limit=25`,
      live.revision,
    );
  return (
    <>
      <PageTitle
        eyebrow="INVESTIGATION / USERS"
        title="Accounts under observation"
        text="Independent account risk, session evidence, and security controls."
      />
      <section className="panel">
        <div className="toolbar">
          <SearchBox
            value={search}
            onChange={(value) => {
              setSearch(value);
              setOffset(0);
            }}
            placeholder="Search username…"
          />
        </div>
        <ResourceState resource={resource}>
          {(data) => (
            <>
              {data.items.length ? (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Account</th>
                        <th>Effective risk</th>
                        <th>Status</th>
                        <th>Last assessed</th>
                        <th>Controls</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.items.map((user) => (
                        <tr key={user.id}>
                          <td>
                            <Link
                              className="user-name"
                              to={`/users/${user.id}`}
                            >
                              <span className="avatar">
                                {user.username.slice(-2)}
                              </span>
                              {user.username}
                              <ArrowUpRight size={13} />
                            </Link>
                          </td>
                          <td>
                            <div className="risk-cell">
                              <strong>{user.effective_score.toFixed(1)}</strong>
                              <span className="risk-track">
                                <i
                                  style={{ width: `${user.effective_score}%` }}
                                  className={user.level}
                                />
                              </span>
                            </div>
                          </td>
                          <td>
                            <Badge value={user.blocked ? "high" : "low"}>
                              {user.blocked ? "Blocked" : "Active"}
                            </Badge>
                          </td>
                          <td className="muted">
                            {dateTime(user.last_assessed_at)}
                          </td>
                          <td>
                            <button
                              className={`button small ${user.blocked ? "secondary" : "ghost-danger"}`}
                              onClick={() =>
                                onAction({
                                  kind: user.blocked
                                    ? "account_unblock"
                                    : "account_block",
                                  id: user.id,
                                  name: user.username,
                                })
                              }
                            >
                              {user.blocked ? (
                                <ShieldCheck size={14} />
                              ) : (
                                <ShieldBan size={14} />
                              )}{" "}
                              {user.blocked ? "Unblock" : "Block"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty text="No matching accounts." />
              )}
              <div className="pagination">
                <span>{data.total} accounts</span>
                <div>
                  <button
                    className="button small secondary"
                    disabled={!offset}
                    onClick={() => setOffset(Math.max(0, offset - 25))}
                  >
                    Previous
                  </button>
                  <button
                    className="button small secondary"
                    disabled={offset + 25 >= data.total}
                    onClick={() => setOffset(offset + 25)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </ResourceState>
      </section>
    </>
  );
}
export function UserDetail({ live, onAction }) {
  const { id } = useParams(),
    user = useResource(`/admin/users/${id}`, live.revision),
    risk = useResource(`/admin/users/${id}/risk?limit=50`, live.revision),
    blocks = useResource(`/admin/blocks?user_id=${id}`, live.revision);
  return (
    <>
      <Link className="back-link" to="/users">
        <ArrowLeft size={15} />
        All accounts
      </Link>
      <ResourceState resource={user}>
        {(data) => (
          <>
            <PageTitle
              eyebrow={`ACCOUNT / ${data.id}`}
              title={data.username}
              text={`Registered ${dateTime(data.created_at)}`}
            >
              <button
                className="button secondary"
                onClick={() =>
                  onAction({
                    kind: data.blocked ? "account_unblock" : "account_block",
                    id: data.id,
                    name: data.username,
                  })
                }
              >
                {data.blocked ? "Unblock account" : "Block account"}
              </button>
            </PageTitle>
            <div className="detail-stats">
              <article className="panel">
                <span className="muted">Effective risk</span>
                <strong>
                  {data.effective_score.toFixed(1)}
                  <small>/ 100</small>
                </strong>
                <Badge value={data.level}>{data.level}</Badge>
              </article>
              <article className="panel">
                <span className="muted">Account status</span>
                <strong>{data.blocked ? "Blocked" : "Active"}</strong>
                <span className="muted">Backend enforced</span>
              </article>
              <article className="panel">
                <span className="muted">Associated network addresses</span>
                <div className="ip-links">
                  {data.associated_ips.length
                    ? data.associated_ips.map((ip) => (
                        <Link key={ip.id} to={`/ips/${ip.id}`}>
                          {ip.address}
                        </Link>
                      ))
                    : "None recorded"}
                </div>
              </article>
            </div>
            <section className="panel">
              <SectionHeader title="Risk history" />
              <ResourceState resource={risk}>
                {(result) =>
                  result.history.length ? (
                    <>
                      <div className="risk-chart">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart
                            data={[...result.history].reverse()}
                            margin={{ left: 0, right: 30 }}
                          >
                            <XAxis
                              dataKey="created_at"
                              tickFormatter={shortTime}
                              minTickGap={70}
                              tick={{ fill: "#71717a", fontSize: 10 }}
                              axisLine={false}
                              tickLine={false}
                            />
                            <YAxis
                              domain={[0, 100]}
                              width={35}
                              tick={{ fill: "#71717a", fontSize: 10 }}
                              axisLine={false}
                              tickLine={false}
                            />
                            <Tooltip
                              labelFormatter={dateTime}
                              contentStyle={{
                                background: "#18181b",
                                border: "1px solid #3f3f46",
                              }}
                            />
                            <Line
                              dataKey="score"
                              name="Risk"
                              stroke="#3b82f6"
                              strokeWidth={2}
                              dot={false}
                              isAnimationActive={false}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="assessment">
                        <h3>Latest assessment</h3>
                        <p className="muted">
                          {result.history[0].evidence.reasons?.join(" · ")}
                        </p>
                        <Evidence value={result.history[0].evidence} />
                      </div>
                    </>
                  ) : (
                    <Empty text="No risk assessments yet." />
                  )
                }
              </ResourceState>
            </section>
            <section className="panel">
              <SectionHeader title="Session transitions" />
              {data.events
                .filter((event) => event.fsm)
                .slice(0, 8)
                .map((event) => (
                  <div className="transition-row" key={event.id}>
                    <span className="mono">{event.state_before}</span>
                    <span className="transition-event">
                      {event.event_type} →
                    </span>
                    <span className="mono">{event.state_after}</span>
                    <Badge value={event.fsm.valid ? "low" : "high"}>
                      {event.fsm.valid ? "Valid" : "Violation"}
                    </Badge>
                  </div>
                ))}
              {!data.events.some((event) => event.fsm) && (
                <Empty text="No versioned FSM evidence yet." />
              )}
            </section>
            <section className="panel">
              <SectionHeader title="Account event timeline" />
              <EventsTable events={data.events} />
            </section>
            <section className="panel">
              <SectionHeader title="Block history" />
              <ResourceState resource={blocks}>
                {(rows) =>
                  rows.length ? (
                    rows.map((row) => (
                      <div className="history-row" key={row.id}>
                        <div>
                          <strong>{row.source} block</strong>
                          <p>{row.reason}</p>
                          <small>{dateTime(row.created_at)}</small>
                        </div>
                        <Badge value={row.active ? "high" : "low"}>
                          {row.active ? "Active" : "Released"}
                        </Badge>
                      </div>
                    ))
                  ) : (
                    <Empty text="No account blocks recorded." />
                  )
                }
              </ResourceState>
            </section>
          </>
        )}
      </ResourceState>
    </>
  );
}
