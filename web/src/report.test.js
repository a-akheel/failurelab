import { test } from "node:test";
import assert from "node:assert/strict";
import { validateReport } from "./report.js";
test("malformed report cannot crash the dashboard", () => {
  for (const report of [null, {}, { schema_version: 1, groups: [{}] }])
    assert.throws(() => validateReport(report));
});
test("a finite versioned report loads", () => {
  const value = {
    schema_version: 1,
    groups: [
      {
        config: { name: "test" },
        metrics: {
          task_completion: 1,
          p95_latency_ms: 3,
          estimated_cost_usd: 0,
        },
        gates: { pass: true },
        results: [],
      },
    ],
  };
  assert.equal(validateReport(value), value);
  value.groups[0].metrics.p95_latency_ms = "bad";
  assert.throws(() => validateReport(value));
});
test("unknown cost is displayed without pretending it is zero", () => {
  const report = {schema_version: 1, groups: [{config: {name: "partial usage"},
    metrics: {task_completion: 0, p95_latency_ms: 12, estimated_cost_usd: null},
    gates: {cost: false}, results: []}]};
  assert.equal(validateReport(report), report);
  report.groups[0].metrics.estimated_cost_usd = "unknown";
  assert.throws(() => validateReport(report));
});
