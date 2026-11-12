import { useState } from "react";
import { Pause, Play } from "lucide-react";
import { Badge, EventsTable, PageTitle, SearchBox } from "../components/UI";
export default function Monitoring({ live }) {
  const [search, setSearch] = useState(""),
    [frozen, setFrozen] = useState(null);
  const events = (frozen || live.events).filter((row) =>
    `${row.username || ""} ${row.event_type} ${row.ip}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageTitle
        eyebrow="OPERATIONS / LIVE MONITORING"
        title="Every event. In context."
        text="Committed security activity, updated automatically from the backend."
      >
        <Badge
          value={
            ["Live", "Polling"].includes(live.status) ? "low" : "monitoring"
          }
        >
          {live.status}
        </Badge>
      </PageTitle>
      <section className="panel">
        <div className="toolbar">
          <SearchBox
            value={search}
            onChange={setSearch}
            placeholder="Filter account, IP or event…"
          />
          <div className="toolbar-end">
            <span className="muted">{events.length} recent events</span>
            <button
              className="button secondary"
              onClick={() => setFrozen(frozen ? null : [...live.events])}
            >
              {frozen ? <Play size={14} /> : <Pause size={14} />}{" "}
              {frozen ? "Resume" : "Pause"}
            </button>
          </div>
        </div>
        <EventsTable events={events} />
      </section>
      <p className="page-footnote">
        Showing up to 200 recent events. Pausing freezes this view while the
        backend continues monitoring.
      </p>
    </>
  );
}
