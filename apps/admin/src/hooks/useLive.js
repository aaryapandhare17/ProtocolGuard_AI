import { useEffect, useState } from "react";
import { api } from "../services/admin";
export function useLive() {
  const [events, setEvents] = useState([]),
    [status, setStatus] = useState("Connecting"),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    let stopped = false,
      socket,
      retry,
      heartbeat,
      changeTimer;
    let eventCursor = 0,
      alertCursor = 0,
      ipCursor = 0,
      attempts = 0;
    const changed = () => {
      clearTimeout(changeTimer);
      changeTimer = setTimeout(() => {
        if (!stopped) setRevision((value) => value + 1);
      }, 300);
    };
    if (import.meta.env.VITE_LIVE_TRANSPORT === "poll") {
      let timer,
        initialized = false;
      async function poll() {
        try {
          const rows = await api(
            initialized
              ? `/admin/events?limit=200&after_id=${eventCursor}&order=asc`
              : "/admin/events?limit=200",
          );
          if (stopped) return;
          initialized = true;
          eventCursor = Math.max(eventCursor, ...rows.map((row) => row.id));
          setEvents((previous) =>
            [
              ...new Map(
                [...rows, ...previous].map((row) => [row.id, row]),
              ).values(),
            ]
              .sort((a, b) => b.id - a.id)
              .slice(0, 200),
          );
          setStatus("Polling");
          changed();
        } catch (error) {
          if (stopped) return;
          setStatus(error.status === 403 ? "Restricted" : "Unavailable");
          if (error.status === 401 || error.status === 403) return;
        }
        if (!stopped) timer = setTimeout(poll, 3000);
      }
      poll();
      return () => {
        stopped = true;
        clearTimeout(timer);
        clearTimeout(changeTimer);
      };
    }
    function connect() {
      if (stopped) return;
      const protocol = location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(
        `${protocol}//${location.host}/ws/admin/events?after_id=${alertCursor}&after_ip_id=${ipCursor}&after_event_id=${eventCursor}`,
      );
      socket.onopen = () => {
        attempts = 0;
        setStatus("Live");
        heartbeat = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) socket.send("ping");
        }, 15000);
      };
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "events") {
          eventCursor = message.event_cursor;
          setEvents((previous) =>
            [
              ...new Map(
                [...message.events.reverse(), ...previous].map((row) => [
                  row.id,
                  row,
                ]),
              ).values(),
            ]
              .sort((a, b) => b.id - a.id)
              .slice(0, 200),
          );
          changed();
        } else if (message.type === "security_alerts") {
          alertCursor = message.cursor;
          changed();
        } else if (message.type === "ip_security_alerts") {
          ipCursor = message.ip_cursor;
          changed();
        }
      };
      socket.onclose = (event) => {
        clearInterval(heartbeat);
        if (stopped) return;
        setStatus(event.code === 4403 ? "Restricted" : "Reconnecting");
        if (event.code === 4401) {
          window.dispatchEvent(new Event("admin:unauthorized"));
          return;
        }
        if (event.code !== 4403)
          retry = setTimeout(connect, Math.min(1000 * 2 ** attempts++, 15000));
      };
      socket.onerror = () => socket.close();
    }
    api("/admin/events?limit=100")
      .then((rows) => {
        if (stopped) return;
        setEvents(rows);
        eventCursor = Math.max(0, ...rows.map((row) => row.id));
        connect();
      })
      .catch(() => {
        if (!stopped) {
          setStatus("Unavailable");
          retry = setTimeout(connect, 2000);
        }
      });
    const fallback = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) return;
      api(`/admin/events?limit=200&after_id=${eventCursor}`)
        .then((rows) => {
          if (stopped || !rows.length) return;
          eventCursor = Math.max(eventCursor, ...rows.map((row) => row.id));
          setEvents((previous) =>
            [
              ...new Map(
                [...rows, ...previous].map((row) => [row.id, row]),
              ).values(),
            ]
              .sort((a, b) => b.id - a.id)
              .slice(0, 200),
          );
          changed();
        })
        .catch(() => {});
    }, 10000);
    return () => {
      clearInterval(fallback);
      stopped = true;
      clearTimeout(retry);
      clearTimeout(changeTimer);
      clearInterval(heartbeat);
      socket?.close();
    };
  }, []);
  return {
    events,
    status,
    revision,
    refresh: () => setRevision((value) => value + 1),
  };
}
