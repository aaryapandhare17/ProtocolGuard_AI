import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RotateCcw,
  RefreshCw,
} from "lucide-react";
import { api, dateTime } from "../services/admin";
import { checkpoint } from "../services/replay";
import { useResource } from "../hooks/useResource";
import {
  Badge,
  Empty,
  PageTitle,
  ResourceState,
  SectionHeader,
} from "../components/UI";
import FSMGraph from "../components/FSMGraph";

function ReplayWorkspace({ definition, live }) {
  const sessions = useResource("/admin/fsm/sessions", live.revision);
  const [params, setParams] = useSearchParams(),
    sessionId = params.get("session") || "";
  const [report, setReport] = useState(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [nonce, setNonce] = useState(0);
  const [position, setPosition] = useState(0),
    [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(800),
    [enforcement, setEnforcement] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setReport(null);
    setError("");
    setPosition(0);
    setPlaying(false);
    setLoading(Boolean(sessionId));
    if (sessionId)
      api(`/admin/fsm/sessions/${encodeURIComponent(sessionId)}`, {
        signal: controller.signal,
      })
        .then((data) => {
          setReport(data);
          setLoading(false);
        })
        .catch((err) => {
          if (err.name !== "AbortError") {
            setError(err.message);
            setLoading(false);
          }
        });
    return () => controller.abort();
  }, [sessionId, nonce]);
  useEffect(() => {
    if (!playing || !report) return;
    if (position >= report.transitions.length) {
      setPlaying(false);
      return;
    }
    const timer = setTimeout(() => setPosition((value) => value + 1), speed);
    return () => clearTimeout(timer);
  }, [playing, position, report, speed]);
  const snapshot = report
    ? checkpoint(report, position, definition.accepting_states)
    : null;
  function move(value) {
    setPlaying(false);
    setPosition(value);
  }
  function play() {
    if (position >= report.transitions.length) setPosition(0);
    setPlaying((value) => !value);
  }
  return (
    <>
      <section className="panel">
        <div className="fsm-selector">
          <div>
            <label htmlFor="session-picker">Recorded banking session</label>
            <ResourceState resource={sessions}>
              {(rows) => (
                <select
                  id="session-picker"
                  value={sessionId}
                  onChange={(event) =>
                    setParams(
                      event.target.value ? { session: event.target.value } : {},
                    )
                  }
                >
                  <option value="">Explore the state machine</option>
                  {sessionId &&
                    !rows.some((row) => row.session_id === sessionId) && (
                      <option value={sessionId}>
                        Selected session · {sessionId.slice(0, 10)}
                      </option>
                    )}
                  {rows.map((row) => (
                    <option value={row.session_id} key={row.session_id}>
                      {row.username ||
                        (row.user_id
                          ? `User #${row.user_id}`
                          : "Unattributed")}{" "}
                      · {row.session_id.slice(0, 10)} · {row.state} ·{" "}
                      {dateTime(row.last_event_at)}
                    </option>
                  ))}
                </select>
              )}
            </ResourceState>
          </div>
          <button
            className="button secondary"
            aria-label="Refresh recorded trace"
            disabled={!sessionId || loading}
            onClick={() => setNonce((value) => value + 1)}
          >
            <RefreshCw size={14} />
            Refresh trace
          </button>
        </div>
        {loading && (
          <p className="fsm-message" role="status">
            Loading recorded evidence…
          </p>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {report && !report.complete_trace && (
          <p className="fsm-message warning">
            Partial historical trace. Acceptance applies only to the available
            evidence; the missing prefix has not been reconstructed.
          </p>
        )}
        <div className="fsm-graph-heading">
          <div>
            <strong>
              {snapshot
                ? `Current state: ${snapshot.state}`
                : "Banking session DFA"}
            </strong>
            <span className="muted">
              {snapshot
                ? `Checkpoint ${position} of ${report.transitions.length}`
                : `${definition.states.length} states · Initial state ${definition.initial_state} · Accepting state ${definition.accepting_states.join(", ")}`}
            </span>
          </div>
          <label className="checkbox inline">
            <input
              type="checkbox"
              checked={enforcement}
              onChange={(event) => setEnforcement(event.target.checked)}
            />
            Show enforcement edges
          </label>
        </div>
        <FSMGraph
          definition={definition}
          currentState={snapshot?.state || definition.initial_state}
          transition={snapshot?.transition}
          showEnforcement={enforcement}
        />
        <div className="fsm-legend">
          <span>
            <i className="current" />
            Current state/transition
          </span>
          <span>
            <i className="accepted" />
            Accepting state
          </span>
          <span>
            <i className="invalid" />
            Invalid transition
          </span>
        </div>
        <p className="fsm-message">
          Undefined state/event pairs lead to REJECTED. The selected rejecting
          transition is shown in red. Pan or zoom to inspect the graph.
        </p>
        {report && (
          <div className="replay-controls">
            <div className="replay-buttons">
              <button
                className="button secondary"
                aria-label="Reset replay"
                onClick={() => move(0)}
              >
                <RotateCcw size={15} />
              </button>
              <button
                className="button secondary"
                aria-label="Previous transition"
                disabled={position === 0}
                onClick={() => move(position - 1)}
              >
                <SkipBack size={15} />
              </button>
              <button className="button primary" onClick={play}>
                {playing ? <Pause size={15} /> : <Play size={15} />}{" "}
                {playing ? "Pause replay" : "Play replay"}
              </button>
              <button
                className="button secondary"
                aria-label="Next transition"
                disabled={position === report.transitions.length}
                onClick={() => move(position + 1)}
              >
                <SkipForward size={15} />
              </button>
              <label className="speed-label">
                Speed
                <select
                  aria-label="Replay speed"
                  value={speed}
                  onChange={(event) => setSpeed(Number(event.target.value))}
                >
                  <option value={1500}>1.5 s/event</option>
                  <option value={800}>0.8 s/event</option>
                  <option value={400}>0.4 s/event</option>
                </select>
              </label>
            </div>
            <label className="replay-range">
              <span>
                Replay checkpoint: {position} / {report.transitions.length}
              </span>
              <input
                aria-label="Replay checkpoint"
                type="range"
                min="0"
                max={report.transitions.length}
                value={position}
                onChange={(event) => move(Number(event.target.value))}
              />
            </label>
          </div>
        )}
      </section>
      {report ? (
        <>
          <div className="detail-stats">
            <article className="panel">
              <span className="muted">Current replay prefix</span>
              <strong className="fsm-classification">
                {snapshot.classification}
              </strong>
              <Badge
                value={
                  snapshot.classification === "suspicious"
                    ? "high"
                    : snapshot.classification === "accepted"
                      ? "low"
                      : "neutral"
                }
              >
                {snapshot.violations} invalid transitions so far
              </Badge>
            </article>
            <article className="panel">
              <span className="muted">Recorded final result</span>
              <strong className="fsm-classification">
                {report.classification.replaceAll("_", " ")}
              </strong>
              <span className="mono">{report.final_state}</span>
            </article>
            <article className="panel">
              <span className="muted">Triggering event at checkpoint</span>
              <strong className="fsm-event-title">
                {snapshot.transition?.event || "Before first event"}
              </strong>
              <span className="muted">
                {snapshot.transition?.violation ||
                  "No violation at this checkpoint"}
              </span>
            </article>
          </div>
          <section className="panel">
            <SectionHeader title="Recorded transition history">
              {report.user_id && (
                <Link className="text-link" to={`/users/${report.user_id}`}>
                  Review account #{report.user_id}
                </Link>
              )}
            </SectionHeader>
            <div className="table-scroll">
              <table className="replay-table">
                <thead>
                  <tr>
                    <th>Step</th>
                    <th>Recorded time</th>
                    <th>From → To</th>
                    <th>Event</th>
                    <th>Validity / explanation</th>
                  </tr>
                </thead>
                <tbody>
                  {report.transitions.map((row, index) => (
                    <tr
                      key={report.persisted_events[index].id}
                      className={
                        position === index + 1 ? "selected-checkpoint" : ""
                      }
                    >
                      <td>
                        <button
                          className="button small secondary"
                          aria-label={`Replay through transition ${index + 1}`}
                          onClick={() => move(index + 1)}
                        >
                          {index + 1}
                        </button>
                      </td>
                      <td className="muted nowrap">
                        {dateTime(report.persisted_events[index].timestamp)}
                      </td>
                      <td className="mono">
                        {row.state_before} → {row.state_after}
                      </td>
                      <td className="event-name">{row.event}</td>
                      <td>
                        <Badge value={row.valid ? "low" : "high"}>
                          {row.valid ? "Valid" : "Invalid"}
                        </Badge>
                        {row.violation && (
                          <p className="violation-explanation">
                            {row.violation}
                          </p>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : (
        !loading &&
        !error && (
          <section className="panel">
            <Empty text="Select a recorded session to replay its persisted events. Replay does not send banking actions or change security records." />
          </section>
        )
      )}
      <section className="panel">
        <SectionHeader title="Formal definition & transition reference" />
        <div className="fsm-reference">
          <p>
            <strong>M = (Q, Σ, δ, q₀, F)</strong>
            <span className="muted"> · {definition.version}</span>
          </p>
          <p className="muted">
            Q: {definition.states.join(", ")}
            <br />
            Σ: {definition.alphabet.join(", ")}
            <br />
            q₀: {definition.initial_state} · F: {"{"}
            {definition.accepting_states.join(", ")}
            {"}"}
          </p>
          <details>
            <summary>View explicit transition rules</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>State</th>
                    <th>Event</th>
                    <th>Next state</th>
                  </tr>
                </thead>
                <tbody>
                  {definition.transitions
                    .filter((row) => row.explicit)
                    .map((row) => (
                      <tr key={`${row.from}-${row.event}`}>
                        <td className="mono">{row.from}</td>
                        <td className="event-name">{row.event}</td>
                        <td className="mono">{row.to}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </details>
          <p className="muted">
            All omitted pairs reject. A valid prefix is not a complete accepted
            session. BLOCKED is suspicious even when enforcement transitions are
            defined. This analysis does not grant authorization.
          </p>
        </div>
      </section>
    </>
  );
}
export default function FSM({ live }) {
  const definition = useResource("/admin/fsm", 0, 0);
  return (
    <>
      <PageTitle
        eyebrow="ANALYSIS / FINITE-STATE MACHINE"
        title="Follow every state transition"
        text="Inspect the banking protocol and replay persisted session evidence without changing live activity."
      />
      <ResourceState resource={definition}>
        {(data) => <ReplayWorkspace definition={data} live={live} />}
      </ResourceState>
    </>
  );
}
