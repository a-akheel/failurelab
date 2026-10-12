import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import "./style.css";
import { validateReport } from "./report.js";
function App() {
  const [index, setIndex] = useState(0),
    [selected, setSelected] = useState(null),
    [uploaded, setUploaded] = useState(null),
    [error, setError] = useState(""),
    [source, setSource] = useState("demo");
  const query = useQuery({
    queryKey: ["report", source],
    queryFn: async () => {
      const r = await fetch(
        source === "demo" ? "/api/report" : "/api/integration-report",
      );
      if (!r.ok) throw Error("Start the evaluation API to load the demo.");
      return validateReport(await r.json());
    },
    retry: false,
  });
  const report = uploaded || query.data,
    group = report?.groups[index],
    metrics = group?.metrics;
  async function upload(e) {
    try {
      if (!e.target.files[0]) return;
      if (e.target.files[0].size > 5_000_000)
        throw Error("Report must be smaller than 5 MB");
      const parsed = validateReport(JSON.parse(await e.target.files[0].text()));
      if (
        parsed.schema_version !== 1 ||
        !Array.isArray(parsed.groups) ||
        !parsed.groups.length
      )
        throw Error("Expected a version 1 evaluation report");
      setUploaded(parsed);
      setIndex(0);
      setSelected(null);
      setError("");
    } catch (ex) {
      setError(ex.message);
    }
  }
  return (
    <>
      <header>
        <b>◈ FAILURELAB</b>
        <span>Replay · Compare · Diagnose</span>
      </header>
      <main>
        <div className="eyebrow">Agent evaluation & failure analysis</div>
        <h1>See where agents break.</h1>
        <p className="muted">
          Replay enterprise support scenarios, inspect tool traces, and enforce
          measurable release gates.
        </p>
        <div className="stats">
          <button
            className={source === "demo" ? "" : "secondary"}
            onClick={() => {
              setSource("demo");
              setUploaded(null);
              setIndex(0);
              setSelected(null);
            }}
          >
            Agent policies
          </button>
          <button
            className={source === "integration" ? "" : "secondary"}
            onClick={() => {
              setSource("integration");
              setUploaded(null);
              setIndex(0);
              setSelected(null);
            }}
          >
            DeskPilot integration
          </button>
        </div>
        {query.isPending && !uploaded && (
          <p role="status">Loading evaluation results…</p>
        )}
        <label>
          Load a report from the CLI
          <input type="file" accept=".json" onChange={upload} />
        </label>
        {(error || (!uploaded && query.error)) && (
          <p className="error">{error || query.error.message}</p>
        )}
        {report && (
          <>
            <p className="muted">
              {report.run_type === "deskpilot_integration_demo"
                ? "Recorded HTTP integration run · simulated IT services · no model calls"
                : report.run_type === "model_evaluation"
                  ? "Live-model evaluation report"
                  : "Deterministic agent policies · no model calls"}
            </p>
            {report.recovery_test && (
              <p className="note">
                Worker process restart:{" "}
                {report.recovery_test.passed
                  ? "PASS — original plan restored and executed once"
                  : "FAIL — inspect the saved report"}
              </p>
            )}
            <div className="stats">
              {report.groups.map((g, i) => (
                <button
                  className={i === index ? "" : "secondary"}
                  key={g.config.name}
                  onClick={() => {
                    setIndex(i);
                    setSelected(null);
                  }}
                >
                  {g.config.name} · {g.release_passed ? "PASS" : "FAIL"}
                </button>
              ))}
            </div>
            <div className="stats">
              <div className="stat">
                Task completion
                <strong>{(metrics.task_completion * 100).toFixed(0)}%</strong>
              </div>
              <div className="stat">
                {metrics.approval_scope === undefined
                  ? "Policy compliance"
                  : "Approval scope"}
                <strong>
                  {(
                    (metrics.approval_scope ?? metrics.policy_compliance ?? 0) *
                    100
                  ).toFixed(0)}
                  %
                </strong>
              </div>
              <div className="stat">
                p95 latency
                <strong>{metrics.p95_latency_ms.toFixed(2)} ms</strong>
              </div>
              <div className="stat">
                Estimated inference cost
                <strong>${metrics.estimated_cost_usd.toFixed(4)}</strong>
              </div>
            </div>
            <div className="grid">
              <section className="card">
                <h2>Release gates</h2>
                {Object.entries(group.gates).map(([k, v]) => (
                  <p key={k}>
                    <span className={v ? "badge" : "badge fail"}>
                      {v ? "PASS" : "FAIL"}
                    </span>{" "}
                    {k.replaceAll("_", " ")}
                  </p>
                ))}
                <p className="note">
                  {report.run_type === "deskpilot_integration_demo"
                    ? "These traces came from the Kotlin API, Temporal workflow, and SQLite action ledger. Rerun scripts/integration.py to collect fresh results."
                    : "Demo policies test the evaluator. Live-model reports require explicit CLI runs. Cost depends on the configured token prices."}
                </p>
                <button
                  className="secondary"
                  onClick={() => {
                    setUploaded(null);
                    setSelected(null);
                    setIndex(0);
                    query.refetch();
                  }}
                >
                  {source === "integration"
                    ? "Reload saved run"
                    : "Replay demo"}
                </button>
              </section>
              <section className="card">
                <h2>Scenario results</h2>
                <div className="results-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Scenario</th>
                        <th>Result</th>
                        <th>Trace events</th>
                        <th>Latency</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.results.map((row) => (
                        <tr
                          key={row.scenario}
                          tabIndex={0}
                          onClick={() => setSelected(row)}
                          onKeyDown={(e) =>
                            e.key === "Enter" && setSelected(row)
                          }
                        >
                          <td>{row.scenario}</td>
                          <td className={row.passed ? "" : "error"}>
                            {row.passed ? "PASS" : "FAIL"}
                          </td>
                          <td>{row.trace.length}</td>
                          <td>{row.latency_ms.toFixed(2)} ms</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <h2>
                  {selected
                    ? selected.scenario
                    : "Select a scenario to inspect its trace"}
                </h2>
                {selected && (
                  <>
                    <p>{selected.output.response}</p>
                    <pre>
                      {JSON.stringify(
                        {
                          checks: selected.checks,
                          output: selected.output,
                          trace: selected.trace,
                        },
                        null,
                        2,
                      )}
                    </pre>
                  </>
                )}
              </section>
            </div>
          </>
        )}
      </main>
    </>
  );
}
createRoot(document.getElementById("root")).render(
  <QueryClientProvider client={new QueryClient()}>
    <App />
  </QueryClientProvider>,
);
