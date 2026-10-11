import math

def summarize(results: list[dict], thresholds: dict) -> dict:
    if not results: raise ValueError("cannot gate an empty evaluation")
    keys = set().union(*(row["checks"] for row in results))
    metrics = {key: sum(row["checks"].get(key, False) for row in results) / len(results) for key in keys}
    metrics["task_completion"]=sum(row["passed"] for row in results)/len(results)
    metrics["p95_latency_ms"]=sorted(row["latency_ms"] for row in results)[max(0,math.ceil(.95*len(results))-1)]
    metrics["estimated_cost_usd"]=sum(row["estimated_cost_usd"] for row in results)
    if not thresholds: raise ValueError("at least one release threshold required")
    for name,value in thresholds.items():
        if name not in metrics or not isinstance(value,(int,float)) or not math.isfinite(value) or value < 0: raise ValueError("invalid threshold: "+name)
    gates={name:metrics[name]<=value if name in {"p95_latency_ms","estimated_cost_usd"} else metrics[name]>=value for name,value in thresholds.items()}
    return {"metrics":metrics,"gates":gates,"release_passed":all(gates.values())}

