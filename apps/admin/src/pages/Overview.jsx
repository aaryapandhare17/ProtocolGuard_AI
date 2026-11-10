import {
  Activity,
  Users,
  ShieldAlert,
  ShieldBan,
  Globe,
  Radio,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  BarChart,
  Bar,
  Cell,
} from "recharts";
import { Link } from "react-router-dom";
import { useResource } from "../hooks/useResource";
import {
  Badge,
  Empty,
  EventsTable,
  PageTitle,
  ResourceState,
  SectionHeader,
} from "../components/UI";
import { dateTime, number, shortTime } from "../services/admin";
export default function Overview({ live }) {
  const resource = useResource("/admin/overview", live.revision);
  return (
    <>
      <PageTitle
        eyebrow="OPERATIONS / OVERVIEW"
        title="Security at a glance"
        text="A connected view of banking activity and the evidence behind every decision."
      />
      <ResourceState resource={resource}>
        {(data) => (
          <>
            <div className="metric-grid">
              {[
                [
                  "Registered users",
                  data.total_users,
                  Users,
                  "Demo banking accounts",
                ],
                [
                  "Active sessions",
                  data.active_sessions,
                  Radio,
                  "Unexpired banking sessions",
                ],
                [
                  "Events analyzed",
                  data.events_analyzed,
                  Activity,
                  "Persisted detection assessments",
                ],
                [
                  "Suspicious users",
                  data.suspicious_users,
                  ShieldAlert,
                  "Effective risk of 30 or above",
                ],
                [
                  "Blocked accounts",
                  data.blocked_accounts,
                  ShieldBan,
                  "Account restrictions",
                ],
                [
                  "Blocked IPs",
                  data.blocked_ips,
                  Globe,
                  "Active network restrictions",
                ],
              ].map(([title, value, Icon, caption]) => (
                <article className="metric" key={title}>
                  <div>
                    <span>{title}</span>
                    <Icon size={17} />
                  </div>
                  <strong>{number(value)}</strong>
                  <small>{caption}</small>
                </article>
              ))}
            </div>
            <div className="chart-grid">
              <section className="panel">
                <SectionHeader title="Security activity">
                  <span className="muted">Last 24 hours</span>
                </SectionHeader>
                <div className="activity-chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={data.activity}
                      margin={{ left: 0, right: 20, top: 10, bottom: 0 }}
                    >
                      <XAxis
                        dataKey="timestamp"
                        tickFormatter={shortTime}
                        minTickGap={55}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: "#71717a", fontSize: 10 }}
                      />
                      <YAxis
                        allowDecimals={false}
                        axisLine={false}
                        tickLine={false}
                        width={35}
                        tick={{ fill: "#71717a", fontSize: 10 }}
                      />
                      <Tooltip
                        labelFormatter={dateTime}
                        contentStyle={{
                          background: "#18181b",
                          border: "1px solid #3f3f46",
                          borderRadius: 8,
                        }}
                      />
                      <Area
                        dataKey="count"
                        name="Security events"
                        type="monotone"
                        stroke="#3b82f6"
                        fill="#3b82f61c"
                        strokeWidth={2}
                        isAnimationActive={false}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </section>
              <section className="panel">
                <SectionHeader title="Threat distribution">
                  <span className="muted">Current user risk</span>
                </SectionHeader>
                <div className="distribution-chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={data.threat_distribution}
                      layout="vertical"
                      margin={{ left: 15, right: 25 }}
                    >
                      <XAxis type="number" allowDecimals={false} hide />
                      <YAxis
                        dataKey="level"
                        type="category"
                        axisLine={false}
                        tickLine={false}
                        width={75}
                        tick={{ fill: "#a1a1aa", fontSize: 12 }}
                      />
                      <Tooltip
                        contentStyle={{
                          background: "#18181b",
                          border: "1px solid #3f3f46",
                        }}
                      />
                      <Bar
                        dataKey="count"
                        name="Users"
                        radius={[0, 4, 4, 0]}
                        barSize={14}
                        isAnimationActive={false}
                      >
                        {data.threat_distribution.map((row, index) => (
                          <Cell
                            key={row.level}
                            fill={["#4d866b", "#b78a40", "#bd555c"][index]}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="chart-summary">
                  <span>Alerts in the last 24 hours</span>
                  <strong>{data.alerts_24h}</strong>
                </div>
              </section>
            </div>
            <section className="panel">
              <SectionHeader title="Recent incidents" to="/alerts" />
              {data.recent_incidents.length ? (
                <div className="incidents">
                  {data.recent_incidents.map((item) => (
                    <div
                      className="incident"
                      key={`${item.entity_type}-${item.id}`}
                    >
                      <span
                        className={`incident-dot ${item.resolved_at ? "resolved" : ""}`}
                      />
                      <div>
                        <strong>{item.target}</strong>
                        <p>{item.reason}</p>
                      </div>
                      <div className="incident-end">
                        <Badge value={item.resolved_at ? "low" : "high"}>
                          {item.resolved_at ? "Resolved" : "Open"}
                        </Badge>
                        <small>{dateTime(item.created_at)}</small>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty text="No security incidents recorded." />
              )}
            </section>
            <section className="panel">
              <SectionHeader title="Latest security events" to="/monitoring" />
              <EventsTable events={live.events.slice(0, 8)} compact />
            </section>
            <p className="page-footnote">
              Model coverage:{" "}
              <Badge value={data.ml_status === "ready" ? "low" : "monitoring"}>
                {data.ml_status.replaceAll("_", " ")}
              </Badge>{" "}
              <Link to="/settings">Review detector configuration</Link>
            </p>
          </>
        )}
      </ResourceState>
    </>
  );
}
