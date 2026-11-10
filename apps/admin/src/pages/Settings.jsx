import { useEffect, useState } from "react";
import { useResource } from "../hooks/useResource";
import {
  Badge,
  Empty,
  PageTitle,
  ResourceState,
  SectionHeader,
} from "../components/UI";
import { dateTime } from "../services/admin";
export default function Settings({ live, onAction }) {
  const security = useResource("/admin/settings/security", live.revision, 0),
    policy = useResource("/admin/risk/policy", live.revision),
    audit = useResource("/admin/audit-logs?limit=30", live.revision);
  const [form, setForm] = useState(null);
  useEffect(() => {
    if (security.data && !form)
      setForm({
        threshold: security.data.threshold,
        enabled: security.data.automatic_blocking,
      });
  }, [security.data, form]);
  return (
    <>
      <PageTitle
        eyebrow="ADMINISTRATION / SETTINGS"
        title="Security policy & oversight"
        text="Review enforcement settings, detector coverage, and the administrative audit trail."
      />
      <div className="settings-grid">
        <section className="panel">
          <SectionHeader title="Account enforcement" />
          <ResourceState resource={security}>
            {(data) =>
              form && (
                <form
                  className="settings-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    onAction({
                      kind: "settings",
                      values: {
                        block_threshold: Number(form.threshold),
                        auto_block_enabled: form.enabled,
                      },
                    });
                  }}
                >
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={form.enabled}
                      onChange={(e) =>
                        setForm({ ...form, enabled: e.target.checked })
                      }
                    />
                    Enable automatic account blocking
                  </label>
                  <label htmlFor="threshold">Block above risk score</label>
                  <input
                    id="threshold"
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    required
                    value={form.threshold}
                    onChange={(e) =>
                      setForm({ ...form, threshold: e.target.value })
                    }
                  />
                  <p className="muted">
                    Scores must strictly exceed the threshold. Disabling
                    automatic enforcement does not release existing blocks.
                  </p>
                  <button className="button primary" type="submit">
                    Review changes
                  </button>
                  <small className="muted">
                    Saved threshold: {data.threshold} ·{" "}
                    {data.automatic_blocking ? "Enabled" : "Disabled"}
                  </small>
                </form>
              )
            }
          </ResourceState>
        </section>
        <section className="panel">
          <SectionHeader title="Hybrid detector coverage" />
          <ResourceState resource={policy}>
            {(data) => (
              <div className="policy-details">
                <div className="policy-status">
                  <span>Machine learning</span>
                  <Badge
                    value={data.ml_status === "ready" ? "low" : "monitoring"}
                  >
                    {data.ml_status.replaceAll("_", " ")}
                  </Badge>
                </div>
                {[
                  ["Finite-state evidence", data.fsm_weight],
                  ["Random Forest", data.rf_weight],
                  ["Isolation Forest", data.if_weight],
                  ["Behavioral evidence", data.behavior_weight],
                ].map(([name, value]) => (
                  <div className="policy-row" key={name}>
                    <span>{name}</span>
                    <strong>{Math.round(value * 100)}%</strong>
                  </div>
                ))}
                <p className="muted">
                  Missing model evidence is marked explicitly. Risk decays with
                  a {data.half_life_seconds / 60}-minute half-life. Scores are
                  indices, not probabilities.
                </p>
              </div>
            )}
          </ResourceState>
        </section>
      </div>
      <section className="panel">
        <SectionHeader title="Administrator audit log" />
        <ResourceState resource={audit}>
          {(rows) =>
            rows.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Action</th>
                      <th>Actor</th>
                      <th>Review note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.id}>
                        <td className="muted nowrap">
                          {dateTime(row.created_at)}
                        </td>
                        <td className="event-name">{row.action}</td>
                        <td>
                          {row.admin_id
                            ? `Admin #${row.admin_id}`
                            : row.evidence.actor === "development_cli"
                              ? "Local recovery"
                              : "System"}
                        </td>
                        <td>{row.evidence.note || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty text="No administrative actions recorded." />
            )
          }
        </ResourceState>
      </section>
    </>
  );
}
