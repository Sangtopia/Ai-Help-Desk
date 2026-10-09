"""Compare two eval variants case by case and write evals/results/comparison.md.

Run with:  python -m evals.compare baseline v1
"""

import sys
from collections import defaultdict

from evals.grade import METRICS
from evals.run import RESULTS, load_rows, wilson


def by_case(variant: str) -> dict[str, list[dict]]:
    rows = defaultdict(list)
    for row in load_rows(RESULTS / variant / "results.jsonl"):
        if row["status"] == "ok":
            rows[row["prompt_id"]].append(row)
    return rows


def mean(rows: list[dict], metric: str) -> float | None:
    values = [r["grade"][metric] for r in rows if r["grade"].get(metric) is not None]
    return sum(values) / len(values) if values else None


def compare(before: str, after: str) -> str:
    a, b = by_case(before), by_case(after)
    all_a = [r for rows in a.values() for r in rows]
    all_b = [r for rows in b.values() for r in rows]
    lines = [f"# {before} vs {after}", "", f"| Metric | {before} | {after} | Change |", "| --- | --- | --- | --- |"]
    for metric, label in METRICS:
        values_a = [r["grade"][metric] for r in all_a if r["grade"].get(metric) is not None]
        values_b = [r["grade"][metric] for r in all_b if r["grade"].get(metric) is not None]
        if not values_a or not values_b:
            continue
        ma, mb = sum(values_a) / len(values_a), sum(values_b) / len(values_b)
        la, ha = wilson(sum(values_a), len(values_a))
        lb, hb = wilson(sum(values_b), len(values_b))
        lines.append(f"| {label} | {ma:.1%} ({la:.0%}-{ha:.0%}) | {mb:.1%} ({lb:.0%}-{hb:.0%}) | {mb - ma:+.1%} |")

    def count(rows, predicate):
        return sum(1 for r in rows if predicate(r))

    lines += ["", f"| Outcome | {before} | {after} |", "| --- | --- | --- |"]
    for label, predicate in [
        ("Unsafe actions (ran or queued)", lambda r: r["grade"]["safe"] == 0),
        ("Legitimate tickets wrongly blocked", lambda r: r["meta"]["ticket_status"] == "blocked"
         and r["grade"].get("blocking") == 0),
        ("Resolved by the AI alone", lambda r: r["meta"]["ticket_status"] == "resolved"),
    ]:
        lines.append(f"| {label} | {count(all_a, predicate)}/{len(all_a)} | {count(all_b, predicate)}/{len(all_b)} |")
    cost_a, cost_b = sum(r["cost_usd"] for r in all_a), sum(r["cost_usd"] for r in all_b)
    lines.append(f"| Cost per run | ${cost_a / len(all_a):.3f} | ${cost_b / len(all_b):.3f} |")

    fixed, broke = [], []
    for case_id in sorted(set(a) & set(b)):
        ca, cb = mean(a[case_id], "correct"), mean(b[case_id], "correct")
        ra, rb = mean(a[case_id], "reply_ok"), mean(b[case_id], "reply_ok")
        if cb > ca or (rb or 0) > (ra or 0):
            fixed.append(f"- {case_id}: all checks {ca:.0%} -> {cb:.0%}, reply {ra:.0%} -> {rb:.0%}")
        if cb < ca or (rb or 0) < (ra or 0):
            broke.append(f"- {case_id}: all checks {ca:.0%} -> {cb:.0%}, reply {ra:.0%} -> {rb:.0%}")
    lines += ["", f"## Improved ({len(fixed)} cases)", "", *fixed, "", f"## Got worse ({len(broke)} cases)", "", *broke]
    text = "\n".join(lines) + "\n"
    (RESULTS / "comparison.md").write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(compare(*(sys.argv[1:3] if len(sys.argv) >= 3 else ("baseline", "v1"))))
