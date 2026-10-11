import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import "./style.css";
function App() {
  const [index, setIndex] = useState(0),
    [selected, setSelected] = useState(null),
    [uploaded, setUploaded] = useState(null),
    [error, setError] = useState("");
  const query = useQuery({
    queryKey: ["report"],
    queryFn: async () => {
      const r = await fetch("/api/report");
      if (!r.ok) throw Error("Start the evaluation API to load the demo.");
      return r.json();
    },
    retry: false,
  });
  const report = uploaded || query.data,
    group = report?.groups[index],
    metrics = group?.metrics;
  async function upload(e) {
    try {
      const parsed = JSON.parse(await e.target.files[0].text());
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
        <label>
          Load a report from the CLI
          <input type="file" accept=".json" onChange={upload} />
        </label>
        {(error || (!uploaded && query.error)) && (
          <p className="error">{error || query.error.message}</p>
        )}
        {report && (
          <>
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
                Policy compliance
                <strong>{(metrics.policy_compliance * 100).toFixed(0)}%</strong>
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
                    <span className={v ? "badge" : "badge fail"}>{v ? "PASS" : "FAIL"}</span>{" "}
                    {k.replaceAll("_", " ")}
                  </p>
                ))}
                <p className="note">
                  Demo results come from deterministic policies. Latency is
                  measured locally; demo inference cost is zero. Upload a
                  gateway run to inspect model results.
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
                  Replay demo
                </button>
              </section>
              <section className="card">
                <h2>Scenario results</h2>
                <table>
                  <thead>
                    <tr>
                      <th>Fault</th>
                      <th>Result</th>
                      <th>Tools</th>
                      <th>Latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.results.map((row) => (
                      <tr
                        key={row.scenario}
                        tabIndex={0}
                        onClick={() => setSelected(row)}
                        onKeyDown={(e) => e.key === "Enter" && setSelected(row)}
                      >
                        <td>{row.fault}</td>
                        <td className={row.passed ? "" : "error"}>
                          {row.passed ? "PASS" : "FAIL"}
                        </td>
                        <td>{row.trace.length}</td>
                        <td>{row.latency_ms.toFixed(2)} ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
