"""
Aggregation and reporting for cost benchmark results.

Stdlib only (csv, statistics) — no pandas required.
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from benchmarks.cost.run_benchmark import RunResult


def _fmt(value: object, decimals: int = 4) -> str:
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    if value is None:
        return "N/A"
    return str(value)


def write_csv(results: List[RunResult], path: Path) -> None:
    """Write one row per RunResult to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    result_fields = [f.name for f in fields(RunResult)]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=result_fields)
        writer.writeheader()
        for r in results:
            writer.writerow(r.as_dict())


def _group_results(results: List[RunResult]) -> Dict[Tuple, List[RunResult]]:
    groups: Dict[Tuple, List[RunResult]] = {}
    for r in results:
        key = (r.mode, r.engine, r.model or "unknown", r.graphify)
        groups.setdefault(key, []).append(r)
    return groups


def _mean_std(vals: List[float]) -> Tuple[float, Optional[float]]:
    if not vals:
        return 0.0, None
    mean = statistics.mean(vals)
    std = statistics.stdev(vals) if len(vals) > 1 else None
    return mean, std


def write_markdown(results: List[RunResult], path: Path) -> None:
    """Write an aggregated Markdown report."""
    path.parent.mkdir(parents=True, exist_ok=True)

    total_cost = sum(r.cost_usd for r in results)
    groups = _group_results(results)

    lines: List[str] = [
        "# Cost Benchmark Report",
        "",
        f"Generated: {datetime.now().isoformat()}",
        f"Runs: {len(results)}  |  Total cost: ${total_cost:.6f}",
        "",
        "---",
        "",
    ]

    metrics: List[Tuple[str, str]] = [
        ("cost_usd", "cost_usd"),
        ("input_tokens", "input_tokens"),
        ("cached_tokens", "cached_tokens"),
        ("output_tokens", "output_tokens"),
        ("wall_seconds", "wall_seconds"),
        ("llm_calls", "llm_calls"),
    ]

    for key, rows in sorted(groups.items()):
        mode, engine, model, graphify = key
        graphify_str = "on" if graphify else "off"
        lines.append(f"## {mode} / engine={engine} / model={model} / graphify={graphify_str}")
        lines.append("")
        lines.append(f"Repetitions: {len(rows)}")
        lines.append("")

        # Per-metric table
        lines.append("| Metric | Mean | Std |")
        lines.append("|--------|-----:|----:|")

        numeric_vals: Dict[str, List[float]] = {attr: [] for _, attr in metrics}
        for r in rows:
            for _, attr in metrics:
                val = getattr(r, attr)
                numeric_vals[attr].append(float(val))

        for label, attr in metrics:
            mean, std = _mean_std(numeric_vals[attr])
            std_str = _fmt(std, 4) if std is not None else "—"
            lines.append(f"| {label} | {_fmt(mean, 4)} | {std_str} |")

        successes = [r.success for r in rows if r.success is not None]
        n_success = sum(1 for s in successes if s)
        success_rate = n_success / len(successes) if successes else None
        lines.append(f"| success_rate | {_fmt(success_rate, 4) if success_rate is not None else 'N/A'} | — |")
        lines.append("")

        # Summary stats
        costs = numeric_vals["cost_usd"]
        if any(c > 0 for c in costs):
            cost_per_req = sum(costs) / len(rows)
            lines.append(f"- **Cost per request**: ${cost_per_req:.6f}")
            if n_success > 0:
                cost_per_success = sum(costs) / n_success
                lines.append(f"- **Cost per successful run**: ${cost_per_success:.6f}")
        else:
            lines.append("- **Cost per request**: $0.000000 (mock/free run)")

        lines.append("")

        # Graphify delta note (for when both on/off exist for same mode/engine/model)
        off_key = (mode, engine, model, False)
        on_key = (mode, engine, model, True)
        if off_key in groups and on_key in groups and key == on_key:
            off_cost = statistics.mean(r.cost_usd for r in groups[off_key])
            on_cost = statistics.mean(r.cost_usd for r in groups[on_key])
            delta = on_cost - off_cost
            sign = "+" if delta >= 0 else ""
            lines.append(f"**Graphify cost delta**: {sign}${delta:.6f} vs. graphify=off")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
