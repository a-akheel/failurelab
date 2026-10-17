export function validateReport(value) {
  const object = (x) => x && typeof x === "object" && !Array.isArray(x);
  if (
    !object(value) ||
    value.schema_version !== 1 ||
    !Array.isArray(value.groups) ||
    !value.groups.length
  )
    throw Error("Expected a version 1 evaluation report");
  for (const group of value.groups) {
    if (
      !object(group.config) ||
      typeof group.config.name !== "string" ||
      !object(group.metrics) ||
      !object(group.gates) ||
      !Array.isArray(group.results)
    )
      throw Error("Report group is incomplete");
    for (const key of [
      "task_completion",
      "p95_latency_ms",

    ])
      if (!Number.isFinite(group.metrics[key]))
        throw Error("Invalid report metric: " + key);
    if (group.metrics.estimated_cost_usd !== null && !Number.isFinite(group.metrics.estimated_cost_usd))
      throw Error("Invalid cost metric");
    if (!Object.values(group.gates).every((x) => typeof x === "boolean"))
      throw Error("Invalid release gates");
    for (const row of group.results)
      if (
        !object(row) ||
        typeof row.scenario !== "string" ||
        typeof row.passed !== "boolean" ||
        !Number.isFinite(row.latency_ms) ||
        !Array.isArray(row.trace) ||
        !object(row.output) ||
        typeof row.output.response !== "string"
      )
        throw Error("Malformed scenario result");
  }
  return value;
}
