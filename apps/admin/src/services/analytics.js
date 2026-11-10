export const modelNames = {
  fsm_only: "FSM only",
  random_forest: "Random Forest",
  isolation_forest: "Isolation Forest",
  hybrid: "Hybrid",
};
export function percent(value) {
  return Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : "—";
}
export function decimal(value, places = 3) {
  return Number.isFinite(value) ? value.toFixed(places) : "—";
}
export function histogram(values, count = 8) {
  const finite = values.filter(Number.isFinite);
  if (!finite.length) return [];
  const low = Math.floor(Math.min(...finite) * 100) / 100;
  let high = Math.ceil(Math.max(...finite) * 100) / 100;
  if (high === low) high = low + 0.01;
  const width = (high - low) / count;
  const bins = Array.from({ length: count }, (_, index) => ({
    range: `${(low + index * width).toFixed(3)}–${(low + (index + 1) * width).toFixed(3)}`,
    count: 0,
  }));
  for (const value of finite)
    bins[Math.min(count - 1, Math.max(0, Math.floor((value - low) / width)))]
      .count++;
  return bins;
}
