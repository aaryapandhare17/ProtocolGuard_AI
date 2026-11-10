// Replay uses server transitions; it does not duplicate the DFA transition function.
export function checkpoint(report, position, acceptingStates = []) {
  const count = Math.max(0, Math.min(position, report.transitions.length));
  const transition = count ? report.transitions[count - 1] : null;
  const state = transition ? transition.state_after : report.initial_state;
  const violations = report.transitions
    .slice(0, count)
    .filter((row) => !row.valid).length;
  const suspicious = violations > 0 || ["REJECTED", "BLOCKED"].includes(state);
  return {
    position: count,
    state,
    transition,
    violations,
    classification: suspicious
      ? "suspicious"
      : acceptingStates.includes(state)
        ? "accepted"
        : "valid prefix",
  };
}
export function transitionGroups(definition, current, showEnforcement = false) {
  const grouped = new Map();
  for (const row of definition.transitions) {
    if (!row.explicit || (!showEnforcement && row.to === "BLOCKED")) continue;
    const key = `${row.from}:${row.to}`;
    if (!grouped.has(key))
      grouped.set(key, { source: row.from, target: row.to, events: [] });
    grouped.get(key).events.push(row.event);
  }
  if (current) {
    const key = `${current.state_before}:${current.state_after}`;
    if (!grouped.has(key))
      grouped.set(key, {
        source: current.state_before,
        target: current.state_after,
        events: [],
      });
    const group = grouped.get(key);
    if (!group.events.includes(current.event)) group.events.push(current.event);
    group.active = true;
    group.invalid = !current.valid;
  }
  return [...grouped.values()];
}
