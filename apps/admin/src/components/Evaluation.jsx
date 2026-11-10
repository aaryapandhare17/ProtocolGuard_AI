import { percent } from "../services/analytics";
export function EvaluationControls({
  partition,
  setPartition,
  scope,
  setScope,
}) {
  return (
    <div className="evaluation-controls">
      <label>
        Evaluation partition
        <select
          aria-label="Evaluation partition"
          value={partition}
          onChange={(e) => setPartition(e.target.value)}
        >
          <option value="test">Test · known families</option>
          <option value="held_out">Held-out · unseen families</option>
          <option value="validation">Validation · threshold selection</option>
        </select>
      </label>
      <label>
        Observation scope
        <select
          aria-label="Observation scope"
          value={scope}
          onChange={(e) => setScope(e.target.value)}
        >
          <option value="complete">Complete sessions</option>
          <option value="prefix">Session prefixes</option>
          <option value="all_observations">Combined observations</option>
        </select>
      </label>
    </div>
  );
}
export function ConfusionMatrix({ name, metric }) {
  return (
    <div className="confusion">
      <h3>{name}</h3>
      <p className="muted">
        True rows / predicted columns · {metric.samples.toLocaleString()}{" "}
        observations
      </p>
      <table aria-label={`${name} confusion matrix`}>
        <thead>
          <tr>
            <th>True / Predicted</th>
            <th>Normal</th>
            <th>Suspicious</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th>Normal</th>
            <td className="correct">{metric.confusion_matrix[0][0]}</td>
            <td className="mistake">{metric.confusion_matrix[0][1]}</td>
          </tr>
          <tr>
            <th>Suspicious</th>
            <td className="mistake">{metric.confusion_matrix[1][0]}</td>
            <td className="correct">{metric.confusion_matrix[1][1]}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
export function MetricValues({ metric }) {
  return (
    <div className="model-metrics">
      {[
        ["Accuracy", metric.accuracy],
        ["Precision", metric.precision],
        ["Recall", metric.recall],
        ["F1 score", metric.f1],
        ["False-positive rate", metric.false_positive_rate],
      ].map(([label, value]) => (
        <div key={label}>
          <span>{label}</span>
          <strong>{percent(value)}</strong>
        </div>
      ))}
    </div>
  );
}
export function Unavailable({ reason }) {
  return (
    <div className="empty evaluation-empty">
      <strong>Evaluation unavailable</strong>
      <p>{reason}</p>
      <p>
        Generate the saved evaluation using the project setup instructions.
        Operational history remains separate.
      </p>
    </div>
  );
}
