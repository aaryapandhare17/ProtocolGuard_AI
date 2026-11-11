import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Play, FlaskConical } from "lucide-react";
import { useResource } from "../hooks/useResource";
import { api, dateTime } from "../services/admin";
import {
  Badge,
  Empty,
  Evidence,
  PageTitle,
  ResourceState,
  SectionHeader,
} from "../components/UI";
function RunResult({ id }) {
  const [interval, setPolling] = useState(2000),
    resource = useResource(`/simulation/runs/${id}`, 0, interval),
    [visible, setVisible] = useState(100);
  useEffect(() => {
    if (resource.data && resource.data.status !== "running") setPolling(0);
  }, [resource.data]);
  return (
    <ResourceState resource={resource}>
      {(run) => (
        <section className="simulation-result">
          <div className="section-header">
            <h2>Run {run.id.slice(0, 8)}</h2>
            <Badge
              value={
                run.status === "completed"
                  ? "low"
                  : run.status === "running"
                    ? "monitoring"
                    : "high"
              }
            >
              {run.status.replaceAll("_", " ")}
            </Badge>
          </div>
          <p className="simulation-caption">
            Simulated only · {run.scenario.replaceAll("_", " ")} ·{" "}
            {dateTime(run.started_at)}
          </p>
          {run.status === "running" ? (
            <section className="panel">
              <Empty text="Isolated sessions are executing. Results will appear here when the run finishes." />
            </section>
          ) : run.result.error ? (
            <p className="error" role="alert">
              {run.result.error}
            </p>
          ) : (
            run.result.summary && (
              <>
                <div className="metric-grid">
                  {[
                    ["Demo actors", run.result.summary.actors],
                    ["Simulated requests", run.result.summary.requests],
                    ["Recorded events", run.result.summary.events],
                    [
                      "Sandbox account blocks",
                      run.result.summary.blocked_accounts,
                    ],
                    [
                      "Sandbox IP restrictions",
                      run.result.summary.restricted_ips,
                    ],
                    ["Sandbox alerts", run.result.summary.alerts],
                  ].map(([label, value]) => (
                    <article className="metric" key={label}>
                      <div>{label}</div>
                      <strong>{value}</strong>
                      <small>Isolated run only</small>
                    </article>
                  ))}
                </div>
                <section className="panel">
                  <SectionHeader title="Simulated account outcomes">
                    <Badge
                      value={
                        run.result.summary.model_status === "ready"
                          ? "low"
                          : "monitoring"
                      }
                    >
                      ML: {run.result.summary.model_status.replaceAll("_", " ")}
                    </Badge>
                  </SectionHeader>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Demo actor</th>
                          <th>Simulated source IP</th>
                          <th>Account risk / peak</th>
                          <th>Account restriction</th>
                          <th>IP restriction</th>
                          <th>HTTP outcomes</th>
                        </tr>
                      </thead>
                      <tbody>
                        {run.result.actors.map((actor) => (
                          <tr key={actor.account}>
                            <td>
                              {actor.account}
                              <small className="prediction-context">
                                {actor.status}
                              </small>
                            </td>
                            <td className="mono">{actor.simulated_ip}</td>
                            <td>
                              {actor.account_risk.toFixed(1)} /{" "}
                              {actor.peak_risk.toFixed(1)}
                            </td>
                            <td>
                              <Badge
                                value={actor.account_blocked ? "high" : "low"}
                              >
                                {actor.account_blocked
                                  ? "Blocked"
                                  : "Not blocked"}
                              </Badge>
                            </td>
                            <td>
                              <Badge
                                value={actor.ip_restricted ? "high" : "neutral"}
                              >
                                {actor.ip_restricted
                                  ? "Restricted"
                                  : "Not restricted"}
                              </Badge>
                            </td>
                            <td>
                              {Object.entries(actor.outcomes).map(
                                ([status, count]) => (
                                  <span className="outcome-count" key={status}>
                                    {status} × {count}
                                  </span>
                                ),
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="metric-note">
                    {(run.result.summary.duration_ms / 1000).toFixed(2)} seconds
                    elapsed. No live account, balance, session, IP restriction
                    or security event was changed.
                  </p>
                </section>
                <section className="panel">
                  <SectionHeader title="Sandbox alert evidence" />
                  {run.result.alerts.length ? (
                    run.result.alerts.map((alert, index) => (
                      <article className="simulation-alert" key={index}>
                        <Badge value="high">
                          Simulated {alert.entity} alert
                        </Badge>
                        <h3>{alert.account || alert.ip_address}</h3>
                        <p className="muted">{alert.reason}</p>
                        <Evidence value={alert.evidence} />
                      </article>
                    ))
                  ) : (
                    <Empty text="No alerts were generated by this isolated run." />
                  )}
                </section>
                <section className="panel">
                  <SectionHeader title="Simulated security event timeline">
                    <span className="muted">
                      {run.result.events.length} recorded events
                    </span>
                  </SectionHeader>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Time</th>
                          <th>Demo actor</th>
                          <th>Event</th>
                          <th>FSM transition</th>
                          <th>Risk</th>
                          <th>Outcome</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...run.result.events]
                          .reverse()
                          .slice(0, visible)
                          .map((event) => (
                            <tr key={event.id}>
                              <td className="muted nowrap">
                                {dateTime(event.created_at)}
                              </td>
                              <td>
                                {event.username || "Unattributed"}
                                <small className="simulated">Simulated</small>
                              </td>
                              <td className="event-name">{event.event_type}</td>
                              <td className="mono">
                                {event.state_before} → {event.state_after}
                                {event.fsm && !event.fsm.valid && (
                                  <small className="simulated">
                                    Protocol violation
                                  </small>
                                )}
                              </td>
                              <td>
                                {event.risk_score == null
                                  ? "—"
                                  : event.risk_score.toFixed(1)}
                              </td>
                              <td>
                                <Badge
                                  value={
                                    event.outcome === "success"
                                      ? "low"
                                      : "denied"
                                  }
                                >
                                  {event.outcome}
                                </Badge>
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                  {visible < run.result.events.length && (
                    <div className="pagination">
                      <span>Showing {visible} events</span>
                      <button
                        className="button small secondary"
                        onClick={() => setVisible((value) => value + 100)}
                      >
                        Show more events
                      </button>
                    </div>
                  )}
                </section>
                <section className="panel">
                  <SectionHeader title="Request traces & run configuration" />
                  <div className="evaluation-body">
                    {run.result.actors.map((actor) => (
                      <details
                        className="simulation-requests"
                        key={actor.account}
                      >
                        <summary>
                          {actor.account} · {actor.requests.length} completed
                          requests
                        </summary>
                        {actor.error && (
                          <p className="error">Scenario error: {actor.error}</p>
                        )}
                        <div className="table-scroll">
                          <table>
                            <thead>
                              <tr>
                                <th>Step</th>
                                <th>Method</th>
                                <th>Local path</th>
                                <th>Status</th>
                              </tr>
                            </thead>
                            <tbody>
                              {actor.requests.map((request) => (
                                <tr key={request.step}>
                                  <td>{request.step}</td>
                                  <td>{request.method}</td>
                                  <td className="mono">{request.path}</td>
                                  <td>{request.status}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </details>
                    ))}
                    <Evidence value={run.configuration} />
                    <p className="evaluation-note">
                      Seeded plans are reproducible; actual timing and model
                      decisions depend on runtime conditions. Sandbox IDs are
                      not links to live records. Missing model evidence is shown
                      explicitly and can reduce detection.
                    </p>
                  </div>
                </section>
              </>
            )
          )}
        </section>
      )}
    </ResourceState>
  );
}
export default function Simulation() {
  const catalog = useResource("/simulation/scenarios", 0, 0),
    [params, setParams] = useSearchParams(),
    selected = params.get("run");
  const [scenario, setScenario] = useState("normal"),
    [accounts, setAccounts] = useState(null),
    [seed, setSeed] = useState("42"),
    [shared, setShared] = useState(false),
    [note, setNote] = useState("Controlled demonstration"),
    [confirmed, setConfirmed] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [revision, setRevision] = useState(0);
  const mounted = useRef(true),
    history = useResource(
      "/simulation/runs?limit=25",
      revision,
      busy ? 2000 : 10000,
    );
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (accounts === null && catalog.data)
      setAccounts(catalog.data.accounts.slice(0, 2));
  }, [catalog.data, accounts]);
  async function run(event) {
    event.preventDefault();
    if (busy || !confirmed || !accounts?.length) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api("/simulation/run", {
        method: "POST",
        body: {
          scenario,
          accounts,
          seed: Number(seed),
          shared_ip: shared,
          confirmed,
          note: note.trim(),
        },
      });
      if (mounted.current) {
        setParams({ run: result.id });
        setRevision((value) => value + 1);
        setNotice(
          result.status === "completed"
            ? "Simulation completed and audited."
            : "Simulation ended with errors. Inspect the saved run.",
        );
      }
    } catch (err) {
      if (mounted.current) setError(err.message);
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="LABORATORY / CONTROLLED SCENARIOS"
        title="Explore threats in isolation"
        text="Run real security workflows on disposable demo copies. Live banking accounts and restrictions stay unchanged."
      />
      <div className="simulation-isolation">
        <FlaskConical size={19} />
        <div>
          <strong>Isolated demo sessions only</strong>
          <p>
            Fixed local scenarios · No external URLs · Current detector and
            enforcement policy · Saved, clearly labeled results
          </p>
        </div>
      </div>
      <ResourceState resource={catalog}>
        {(data) => (
          <form className="panel simulation-form" onSubmit={run}>
            <SectionHeader title="Configure a controlled run">
              <Badge value={data.enabled ? "low" : "monitoring"}>
                {data.enabled ? "Development lab enabled" : "Lab disabled"}
              </Badge>
            </SectionHeader>
            {!data.enabled && (
              <p className="warning">
                The simulation lab must be explicitly enabled in a development
                environment.
              </p>
            )}
            <div
              className="scenario-grid"
              role="radiogroup"
              aria-label="Simulation scenario"
            >
              {data.scenarios.map((item) => (
                <label
                  className={`scenario-card ${scenario === item.id ? "selected" : ""}`}
                  key={item.id}
                >
                  <input
                    type="radio"
                    name="scenario"
                    value={item.id}
                    checked={scenario === item.id}
                    onChange={() => setScenario(item.id)}
                    disabled={busy}
                  />
                  <span>
                    <strong>{item.name}</strong>
                    <small>{item.description}</small>
                  </span>
                </label>
              ))}
            </div>
            <div className="simulation-config">
              <fieldset>
                <legend>Demo actors · select up to ten</legend>
                <div className="account-checkboxes">
                  {data.accounts.map((account) => (
                    <label className="checkbox inline" key={account}>
                      <input
                        type="checkbox"
                        checked={accounts?.includes(account) || false}
                        disabled={busy}
                        onChange={(event) =>
                          setAccounts((previous) =>
                            event.target.checked
                              ? [...previous, account]
                              : previous.filter((name) => name !== account),
                          )
                        }
                      />
                      {account}
                    </label>
                  ))}
                </div>
                {!data.accounts.length && (
                  <p className="muted">
                    Provision the demo accounts before running a scenario.
                  </p>
                )}
              </fieldset>
              <div className="simulation-inputs">
                <label htmlFor="simulation-seed">
                  Plan seed
                  <input
                    id="simulation-seed"
                    type="number"
                    min="0"
                    max="2147483647"
                    step="1"
                    required
                    value={seed}
                    onChange={(event) => setSeed(event.target.value)}
                    disabled={busy}
                  />
                </label>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={shared}
                    onChange={(event) => setShared(event.target.checked)}
                    disabled={busy}
                  />
                  Use one shared simulated IP
                </label>
              </div>
              <label htmlFor="simulation-note">
                Review note
                <textarea
                  id="simulation-note"
                  minLength={3}
                  maxLength={500}
                  required
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  disabled={busy}
                />
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                  disabled={busy}
                />
                I confirm this run uses isolated demo copies
              </label>
              {error && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}
              {notice && (
                <p className="notice" role="status">
                  {notice}
                </p>
              )}
              <div className="simulation-submit">
                <button
                  className="button primary"
                  disabled={
                    busy ||
                    !data.enabled ||
                    !accounts?.length ||
                    !confirmed ||
                    note.trim().length < 3
                  }
                >
                  <Play size={15} />
                  {busy ? "Running isolated sessions…" : "Run simulation"}
                </button>
                <p className="muted">
                  Up to two runs per server process. Runs continue if you leave
                  this page; review saved history afterward.
                </p>
              </div>
            </div>
          </form>
        )}
      </ResourceState>
      <section className="panel">
        <SectionHeader title="Saved simulation runs">
          <button className="button small secondary" onClick={history.refresh}>
            Refresh history
          </button>
        </SectionHeader>
        <ResourceState resource={history}>
          {(rows) =>
            rows.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Run</th>
                      <th>Started</th>
                      <th>Scenario</th>
                      <th>Actors</th>
                      <th>Status</th>
                      <th>Simulated outcomes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr
                        key={row.id}
                        className={
                          selected === row.id ? "selected-checkpoint" : ""
                        }
                      >
                        <td>
                          <button
                            className="button small secondary"
                            onClick={() => setParams({ run: row.id })}
                          >
                            {row.id.slice(0, 8)}
                          </button>
                        </td>
                        <td className="muted nowrap">
                          {dateTime(row.started_at)}
                        </td>
                        <td>{row.scenario.replaceAll("_", " ")}</td>
                        <td>{row.configuration.accounts.length}</td>
                        <td>
                          <Badge
                            value={
                              row.status === "completed"
                                ? "low"
                                : row.status === "running"
                                  ? "monitoring"
                                  : "high"
                            }
                          >
                            {row.status.replaceAll("_", " ")}
                          </Badge>
                        </td>
                        <td>
                          {row.summary
                            ? `${row.summary.events} events · ${row.summary.alerts} alerts`
                            : "Results pending"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty text="No simulation runs recorded yet." />
            )
          }
        </ResourceState>
      </section>
      {selected && <RunResult key={selected} id={selected} />}
    </>
  );
}
