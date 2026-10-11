"""Compare eval variants run with different model policies: pass rate, safety, and cost per ticket.

    python -m evals.models_report gw-opus gw-haiku gw-routed gw-routed-wide

Writes evals/results/models-report.md. Cost is the help desk's own spend per ticket (the
eval judge excluded), priced per call by the model that served it.
"""

import json
import sys
from collections import Counter, defaultdict

from evals.run import RESULTS, load_rows, wilson

KEY_METRICS = [("correct", "All checks"), ("safe", "No unsafe act"), ("reply_ok", "Reply (judge)")]


def report(variants: list[str]) -> str:
    data = {v: load_rows(RESULTS / v / "results.jsonl") for v in variants}
    errors = {v: load_rows(RESULTS / v / "errors.jsonl") for v in variants}
    base = variants[0]
    base_cost = sum(r.get("app_cost_usd", r["cost_usd"]) for r in data[base]) / max(1, len(data[base]))

    lines = ["# Model policies compared", "",
             "| Variant | Runs | Errors | All checks (95% CI) | No unsafe act | Reply | App cost / ticket | vs first |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for v in variants:
        rows = data[v]
        cells = []
        for metric, _ in KEY_METRICS:
            values = [r["grade"][metric] for r in rows if r["grade"].get(metric) is not None]
            if metric == "correct":
                low, high = wilson(sum(values), len(values))
                cells.append(f"{sum(values) / len(values):.1%} ({low:.0%}-{high:.0%})")
            else:
                cells.append(f"{sum(values) / len(values):.1%}" if values else "-")
        cost = sum(r.get("app_cost_usd", r["cost_usd"]) for r in rows) / max(1, len(rows))
        error_kinds = Counter(e["class"] for e in errors[v])
        error_text = ", ".join(f"{n} {k}" for k, n in error_kinds.items()) or "0"
        lines.append(f"| {v} | {len(rows)} | {error_text} | {' | '.join(cells)} | ${cost:.4f} | "
                     f"{cost / base_cost - 1:+.0%} |")

    lines += ["", "## Agent model mix", ""]
    for v in variants:
        mix = Counter(r.get("model") or "blocked before agent" for r in data[v])
        lines.append(f"- **{v}**: " + ", ".join(f"{m} {n}" for m, n in mix.most_common()))

    lines += ["", "## All checks by group", "", "| Group | " + " | ".join(variants) + " |",
              "| --- |" + " --- |" * len(variants)]
    groups = sorted({r["tags"][0] for v in variants for r in data[v]})
    for g in groups:
        cells = []
        for v in variants:
            values = [r["grade"]["correct"] for r in data[v] if r["tags"][0] == g]
            cells.append(f"{sum(values) / len(values):.0%}" if values else "-")
        lines.append(f"| {g} | " + " | ".join(cells) + " |")

    lines += ["", "## Cases that pass on the first variant but fail on another", ""]
    passed_first = {(r["prompt_id"], r["rep"]) for r in data[base] if r["grade"]["correct"] == 1}
    for v in variants[1:]:
        lost = defaultdict(list)
        for r in data[v]:
            if (r["prompt_id"], r["rep"]) in passed_first and r["grade"]["correct"] == 0:
                failed = [k for k, val in r["grade"].items() if val == 0.0 and k not in ("correct", "reply_ok")]
                lost[r["prompt_id"]].append(f"rep{r['rep']} ({r.get('model') or 'blocked'}: {', '.join(failed)})")
        lines.append(f"- **{v}** ({sum(len(x) for x in lost.values())} runs): "
                     + ("; ".join(f"{c} {' '.join(x)}" for c, x in sorted(lost.items())) or "none"))

    text = "\n".join(lines) + "\n"
    (RESULTS / "models-report.md").write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(report(sys.argv[1:]))
