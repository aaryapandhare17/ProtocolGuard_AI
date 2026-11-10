import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { useResource } from "../hooks/useResource";
import {
  Badge,
  Empty,
  PageTitle,
  ResourceState,
  SectionHeader,
} from "../components/UI";
import {
  ConfusionMatrix,
  EvaluationControls,
  MetricValues,
  Unavailable,
} from "../components/Evaluation";
import { decimal, histogram, modelNames, percent } from "../services/analytics";
import { dateTime } from "../services/admin";
export default function Analytics({ live }) {
  const evaluation = useResource("/admin/ml/metrics", live.revision, 0),
    history = useResource("/admin/ml/predictions?limit=100", live.revision);
  const [partition, setPartition] = useState("test"),
    [scope, setScope] = useState("complete");
  const distribution = useMemo(
    () =>
      histogram(
        (history.data?.predictions || []).map(
          (row) => row.isolation_forest.raw_anomaly_score,
        ),
      ),
    [history.data],
  );
  return (
    <>
      <PageTitle
        eyebrow="ANALYSIS / MACHINE LEARNING"
        title="Models, measured and observed"
        text="Saved synthetic evaluation and recent operational predictions, shown as separate evidence sources."
      />
      <section className="panel">
        <SectionHeader title="Saved synthetic evaluation">
          <button
            className="button small secondary"
            onClick={evaluation.refresh}
          >
            Reload report
          </button>
        </SectionHeader>
        <ResourceState resource={evaluation}>
          {(data) =>
            data.status !== "available" ? (
              <Unavailable reason={data.reason} />
            ) : (
              <div className="evaluation-body">
                <div className="evaluation-provenance">
                  <Badge value="neutral">
                    Synthetic dataset ·{" "}
                    {data.report.dataset.sessions.toLocaleString()} sessions
                  </Badge>
                  <Badge
                    value={data.model_status === "ready" ? "low" : "monitoring"}
                  >
                    Runtime: {data.model_status.replaceAll("_", " ")}
                  </Badge>
                  <span className="muted">
                    Training seed {data.report.training_seed} ·{" "}
                    {data.report.versions.scikit_learn} scikit-learn
                  </span>
                </div>
                <EvaluationControls
                  partition={partition}
                  setPartition={setPartition}
                  scope={scope}
                  setScope={setScope}
                />
                <div className="model-grid">
                  {["random_forest", "isolation_forest"].map((name) => {
                    const model = data.report.models[name],
                      metric = model.metrics[partition][scope];
                    return (
                      <article className="model-card" key={name}>
                        <div className="section-header">
                          <h2>{modelNames[name]}</h2>
                          <Badge value="neutral">
                            {metric.samples.toLocaleString()} observations
                          </Badge>
                        </div>
                        <MetricValues metric={metric} />
                        <p className="metric-note">
                          Frozen threshold: {decimal(model.threshold, 6)} ·
                          Original model-only median:{" "}
                          {decimal(model.latency.median_ms)} ms
                        </p>
                        <ConfusionMatrix
                          name={modelNames[name]}
                          metric={metric}
                        />
                      </article>
                    );
                  })}
                </div>
                <p className="evaluation-note">
                  Synthetic scores do not establish real-world performance.
                  Prefix observations are correlated. Accuracy and confusion
                  matrices describe this selected cohort; runtime predictions
                  below have no ground-truth labels.
                </p>
                <section className="importance-section">
                  <h3>Random Forest feature importance</h3>
                  <p className="muted">
                    Top ten impurity-based importances from the trained forest;
                    importance does not establish causality.
                  </p>
                  <div className="importance-chart">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        layout="vertical"
                        data={Object.entries(
                          data.report.random_forest_feature_importance,
                        )
                          .sort((a, b) => b[1] - a[1])
                          .slice(0, 10)
                          .map(([feature, value]) => ({
                            feature,
                            label:
                              feature.length > 29
                                ? `${feature.slice(0, 27)}…`
                                : feature,
                            value: value * 100,
                          }))}
                        margin={{ left: 0, right: 25 }}
                      >
                        <XAxis
                          type="number"
                          tick={{ fill: "#777787", fontSize: 9 }}
                          tickFormatter={(value) => `${value}%`}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          dataKey="label"
                          type="category"
                          width={180}
                          tick={{ fill: "#aaaabb", fontSize: 9 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          contentStyle={{
                            background: "#18181b",
                            border: "1px solid #3f3f46",
                          }}
                          labelFormatter={(_, payload) =>
                            payload[0]?.payload.feature
                          }
                          formatter={(value) => `${value.toFixed(2)}%`}
                        />
                        <Bar
                          dataKey="value"
                          name="Importance"
                          fill="#6088c4"
                          barSize={12}
                          radius={[0, 3, 3, 0]}
                          isAnimationActive={false}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </section>
              </div>
            )
          }
        </ResourceState>
      </section>
      <section className="panel">
        <SectionHeader title="Operational prediction history">
          <Badge value="neutral">Recent persisted assessments</Badge>
        </SectionHeader>
        <ResourceState resource={history}>
          {(data) => (
            <>
              <p className="metric-note">
                Scanning the latest {data.assessments_scanned} assessments.
                Multiple contexts may describe the same session; these are not
                independent labeled test cases.
              </p>
              {data.predictions.length ? (
                <>
                  <div className="operational-chart">
                    <h3>Isolation Forest raw anomaly-score distribution</h3>
                    <div className="anomaly-chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={distribution}
                          margin={{ left: 0, right: 25, bottom: 20 }}
                        >
                          <XAxis
                            dataKey="range"
                            tick={{ fill: "#838394", fontSize: 8 }}
                            interval="preserveStartEnd"
                            axisLine={false}
                            tickLine={false}
                          />
                          <YAxis
                            allowDecimals={false}
                            width={35}
                            tick={{ fill: "#838394", fontSize: 9 }}
                            axisLine={false}
                            tickLine={false}
                          />
                          <Tooltip
                            contentStyle={{
                              background: "#18181b",
                              border: "1px solid #3f3f46",
                            }}
                          />
                          <Bar
                            dataKey="count"
                            name="Predictions"
                            fill="#738aaf"
                            isAnimationActive={false}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <p className="muted">
                      Higher raw scores indicate more anomalous observations.
                      Raw scores and reference percentiles are not probabilities
                      of malicious behavior.
                    </p>
                  </div>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Recorded time</th>
                          <th>Account / context</th>
                          <th>RF score</th>
                          <th>IF raw score</th>
                          <th>Normal-reference percentile</th>
                          <th>Hybrid risk</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.predictions.map((row) => (
                          <tr key={`${row.detection_id}-${row.context}`}>
                            <td className="muted nowrap">
                              {dateTime(row.created_at)}
                            </td>
                            <td>
                              {row.user_id ? (
                                <Link to={`/users/${row.user_id}`}>
                                  {row.username}
                                </Link>
                              ) : (
                                "Unattributed"
                              )}
                              <small className="prediction-context">
                                {row.context.replaceAll("_", " ")} ·{" "}
                                {row.provisional ? "provisional" : "complete"}
                              </small>
                            </td>
                            <td>{decimal(row.random_forest.score)}</td>
                            <td>
                              {decimal(row.isolation_forest.raw_anomaly_score)}
                            </td>
                            <td>
                              {percent(
                                row.isolation_forest
                                  .normal_reference_percentile,
                              )}
                            </td>
                            <td>{decimal(row.risk_score, 1)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <Empty text="No saved live predictions in the recent assessment window. Banking actions with loaded models will create this history." />
              )}
            </>
          )}
        </ResourceState>
      </section>
    </>
  );
}
