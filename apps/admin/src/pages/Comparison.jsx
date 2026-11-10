import { useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";
import { useResource } from "../hooks/useResource";
import {
  Badge,
  PageTitle,
  ResourceState,
  SectionHeader,
} from "../components/UI";
import {
  ConfusionMatrix,
  EvaluationControls,
  Unavailable,
} from "../components/Evaluation";
import { decimal, modelNames, percent } from "../services/analytics";
export default function Comparison({ live }) {
  const resource = useResource("/admin/detectors/comparison", live.revision, 0),
    [partition, setPartition] = useState("test"),
    [scope, setScope] = useState("complete");
  return (
    <>
      <PageTitle
        eyebrow="ANALYSIS / DETECTOR COMPARISON"
        title="One dataset. Four detectors."
        text="Compare protocol rules, trained models, and the documented hybrid policy on identical observations."
      />
      <section className="panel">
        <SectionHeader title="Frozen detector evaluation">
          <button className="button small secondary" onClick={resource.refresh}>
            Reload comparison
          </button>
        </SectionHeader>
        <ResourceState resource={resource}>
          {(data) => {
            if (data.status !== "available")
              return <Unavailable reason={data.reason} />;
            const report = data.report,
              rows = Object.entries(report.models).map(([key, model]) => ({
                key,
                name: modelNames[key],
                metric: model.metrics[partition][scope],
                latency: model.latency,
              }));
            return (
              <>
                <div className="evaluation-body">
                  <div className="evaluation-provenance">
                    <Badge value="neutral">
                      Synthetic · {report.dataset.sessions.toLocaleString()}{" "}
                      source sessions
                    </Badge>
                    <span className="muted">
                      Seed {report.dataset.seed} · Model{" "}
                      {report.model_sha256.slice(0, 12)}
                    </span>
                  </div>
                  {!data.runtime_policy_match && (
                    <p className="warning">
                      The live risk policy differs from this saved comparison
                      snapshot. Results below use the recorded policy, not the
                      changed live settings.
                    </p>
                  )}
                  <EvaluationControls
                    partition={partition}
                    setPartition={setPartition}
                    scope={scope}
                    setScope={setScope}
                  />
                  <p className="metric-note">
                    Identical cohort:{" "}
                    <strong data-testid="comparison-samples">
                      {rows[0].metric.samples.toLocaleString()}
                    </strong>{" "}
                    observations per detector. No test/held-out threshold
                    tuning.
                  </p>
                  <div className="comparison-chart">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={rows.map((row) => ({
                          name: row.name,
                          "F1 score": row.metric.f1 * 100,
                          "False-positive rate":
                            row.metric.false_positive_rate * 100,
                        }))}
                        margin={{ left: 0, right: 25 }}
                      >
                        <XAxis
                          dataKey="name"
                          tick={{ fill: "#aaaabb", fontSize: 10 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          domain={[0, 100]}
                          width={40}
                          tick={{ fill: "#838394", fontSize: 9 }}
                          tickFormatter={(value) => `${value}%`}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          contentStyle={{
                            background: "#18181b",
                            border: "1px solid #3f3f46",
                          }}
                          formatter={(value) => `${value.toFixed(2)}%`}
                        />
                        <Legend
                          wrapperStyle={{ fontSize: 10, paddingTop: 15 }}
                        />
                        <Bar
                          dataKey="F1 score"
                          fill="#6692d4"
                          radius={[3, 3, 0, 0]}
                          isAnimationActive={false}
                        />
                        <Bar
                          dataKey="False-positive rate"
                          fill="#bc7585"
                          radius={[3, 3, 0, 0]}
                          isAnimationActive={false}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Detector</th>
                        <th>Accuracy</th>
                        <th>Precision</th>
                        <th>Recall</th>
                        <th>F1</th>
                        <th>False-positive rate</th>
                        <th>Test-session benchmark median</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <tr key={row.key}>
                          <td>{row.name}</td>
                          <td>{percent(row.metric.accuracy)}</td>
                          <td>{percent(row.metric.precision)}</td>
                          <td>{percent(row.metric.recall)}</td>
                          <td>{percent(row.metric.f1)}</td>
                          <td>{percent(row.metric.false_positive_rate)}</td>
                          <td>{decimal(row.latency.median_ms)} ms</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="evaluation-body">
                  <p className="evaluation-note">
                    Timing always uses the same first {rows[0].latency.samples}{" "}
                    complete test sessions for all detectors, including
                    feature/context extraction. It excludes database and network
                    overhead and is independent of the selected results cohort.
                  </p>
                  <div className="comparison-matrices">
                    {rows.map((row) => (
                      <ConfusionMatrix
                        key={row.key}
                        name={row.name}
                        metric={row.metric}
                      />
                    ))}
                  </div>
                  <h3 className="policy-heading">Recorded hybrid policy</h3>
                  <div className="policy-chips">
                    {[
                      ["FSM", report.policy.fsm_weight],
                      ["Random Forest", report.policy.rf_weight],
                      ["Isolation Forest", report.policy.if_weight],
                      ["Behavior", report.policy.behavior_weight],
                    ].map(([name, value]) => (
                      <Badge key={name} value="neutral">
                        {name} {percent(value)}
                      </Badge>
                    ))}
                    <Badge value="monitoring">
                      Suspicious above {report.hybrid_threshold}
                    </Badge>
                  </div>
                  <p className="evaluation-note">{report.hybrid_scope}</p>
                  <p className="evaluation-note">
                    These are synthetic single-session measurements. The live
                    account pipeline adds cross-session evidence and decay. A
                    conservative hybrid policy can reduce false positives while
                    missing more attacks than RF alone; no detector is declared
                    universally best.
                  </p>
                </div>
              </>
            );
          }}
        </ResourceState>
      </section>
    </>
  );
}
