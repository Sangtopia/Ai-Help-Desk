"""Run the help desk eval: every case through the real pipeline (handle_ticket), each in a fresh database.

    python -m evals.run --cases acct-01,sec-01 --reps 1      # a pilot
    python -m evals.run --reps 2                              # the full set
    python -m evals.run --summary                              # re-print the summary from saved results

Writes evals/results/<variant>/results.jsonl (one row per case x rep), traces/<id>_rep<k>.json
(the full conversation), errors.jsonl (attempts that never produced a gradable result), and summary.md.

The first run, and any run after the runner, grader, or cases change, stops until you re-run it with
--approve-harness. That approval records a fingerprint of those files; it is yours to give.
"""

import argparse
import hashlib
import json
import math
import random
import shutil
import sys
import tempfile
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import anthropic

from evals.check_cases import load_cases, problems
from evals.grade import JUDGE_CRITERIA, JUDGE_MODEL, METRICS, Observation, check, judge_reply, unsafe_attempts
from helpdesk.agent import SYSTEM_PROMPT, BlockedReply, handle_ticket
from helpdesk.db import session, use_database
from helpdesk.llm import MODEL, get_client
from helpdesk.models import Ticket, Triage
from helpdesk.seed import build_database

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
STATE = RESULTS / "_state.json"
HARNESS_FILES = [HERE / "run.py", HERE / "grade.py", HERE / "cases.json"]
RETRYABLE = (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError)

# $ per million tokens (input, output). Cache writes cost 1.25x input, cache reads 0.1x input.
PRICES = {"claude-opus-5-5": (4.00, 20.00), "claude-sonnet-5-5": (2.00, 10.00)}
USAGE_KEYS = ["input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"]


# ---------- harness approval ----------

def harness_sha() -> str:
    digest = hashlib.sha256()
    for path in HARNESS_FILES:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save_state(state: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------- calling the app ----------

class RecordingClient:
    """Wraps the real Anthropic client so every call the app makes is recorded (usage, model, latency)."""

    def __init__(self, client: anthropic.Anthropic):
        self._client = client
        self.calls: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs):
        started = time.monotonic()
        response = self._client.beta.messages.parse(**kwargs)
        kinds = {Triage: "triage", BlockedReply: "blocked_reply"}
        self.calls.append({
            "kind": kinds.get(kwargs.get("output_format"), "agent"),
            "kwargs": kwargs, "response": response, "latency_s": time.monotonic() - started,
        })
        return response


def add_usage(total: dict, usage) -> None:
    for key in USAGE_KEYS:
        total[key] = total.get(key, 0) + (getattr(usage, key, 0) or 0)


def cost(model: str, usage: dict) -> float:
    price_in, price_out = PRICES.get(model, (0.0, 0.0))
    return (usage.get("input_tokens", 0) * price_in + usage.get("output_tokens", 0) * price_out
            + usage.get("cache_read_input_tokens", 0) * price_in * 0.1
            + usage.get("cache_creation_input_tokens", 0) * price_in * 1.25) / 1e6


def observe(ticket_id: str) -> Observation:
    """Read what the pipeline left behind in this case's database."""
    with session() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        audit = conn.execute("SELECT * FROM audit_log WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
        escalated = conn.execute("SELECT 1 FROM escalations WHERE ticket_id = ?", (ticket_id,)).fetchone() is not None
    resolution = json.loads(row["resolution"]) if row["resolution"] else {}
    calls = [{"tool": e["action"], "args": json.loads(e["arguments"] or "{}"), "outcome": e["outcome"]}
             for e in audit if e["actor"] == "agent" and e["action"] != "submit_resolution"]
    return Observation(sender=row["sender"], status=row["status"],
                       triage=json.loads(row["triage"]) if row["triage"] else None,
                       reply=resolution.get("reply_to_user", ""), escalated=escalated, calls=calls)


def block_to_turns(block) -> list[dict]:
    if block.type == "tool_use":
        return [{"role": "tool_call", "name": block.name, "content": json.dumps(block.input, indent=2)}]
    if block.type == "text" and block.text.strip():
        return [{"role": "assistant", "content": block.text}]
    return []


def build_trace(case: dict, recorder: RecordingClient, obs: Observation, judge_why: dict | None) -> list[dict]:
    trace = [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": f"From: {case['sender']}\nSubject: {case['subject']}\n\n{case['body']}"}]
    if obs.triage:
        trace.append({"role": "assistant", "name": "triage", "content": json.dumps(obs.triage, indent=2)})
    agent_calls = [c for c in recorder.calls if c["kind"] == "agent"]
    if not agent_calls:
        trace.append({"role": "assistant", "content": f"[Blocked before the agent ran. Status: {obs.status}]"})
    else:
        messages = agent_calls[-1]["kwargs"]["messages"]
        trace.append({"role": "user", "content": messages[0]["content"]})
        for message in messages[1:]:
            if message["role"] == "assistant":
                for block in message["content"]:
                    trace += block_to_turns(block)
            else:
                trace += [{"role": "tool_result", "content": r["content"]} for r in message["content"]]
        final = agent_calls[-1]["response"]
        if final.parsed_output is not None:
            trace.append({"role": "assistant", "content": final.parsed_output.model_dump_json(indent=2)})
    trace.append({"role": "assistant", "name": "final_reply", "content": obs.reply})
    if judge_why:
        trace.append({"role": "assistant", "name": "judge", "content": json.dumps(judge_why, indent=2)})
    return trace


def with_retries(fn, attempts: int = 4):
    """Call fn, backing off with jitter on rate limits and transient errors. Returns (result, retries)."""
    for attempt in range(attempts):
        try:
            return fn(), attempt
        except RETRYABLE:
            if attempt == attempts - 1:
                raise
            time.sleep(min(60, 2 ** attempt * 5) * (0.5 + random.random()))


def run_case(case: dict, rep: int, use_judge: bool) -> dict:
    """Run one (case, rep) end to end in its own database. Raises on harness failures."""
    workdir = Path(tempfile.mkdtemp(prefix="helpdesk-eval-"))
    try:
        return _run_case_in(workdir / "helpdesk.db", case, rep, use_judge)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _run_case_in(db: Path, case: dict, rep: int, use_judge: bool) -> dict:
    with use_database(db):
        ticket = Ticket(id=f"EVAL-{case['id']}", sender=case["sender"], subject=case["subject"], body=case["body"])
        started = time.monotonic()

        def attempt_once() -> RecordingClient:
            build_database(db)  # every attempt, including a retry, starts from a clean environment
            recorder = RecordingClient(get_client())
            handle_ticket(ticket, recorder)
            return recorder

        recorder, retries = with_retries(attempt_once)
        obs = observe(ticket.id)

        models = {c["response"].model for c in recorder.calls}
        if models - {MODEL}:
            raise RuntimeError(f"served_model_mismatch: asked for {MODEL}, got {sorted(models)}")

        grade, why = check(case, obs)
        judge_usage, judge_model, judge_why = {}, None, None
        if use_judge:
            (judge_grade, judge_why, judge_response), _ = with_retries(
                lambda: judge_reply(get_client(), case, obs))
            grade.update(judge_grade)
            why.update(judge_why)
            judge_model = judge_response.model
            add_usage(judge_usage, judge_response.usage)

        usage = {}
        for call in recorder.calls:
            add_usage(usage, call["response"].usage)
        truncated = any(c["response"].stop_reason == "max_tokens" for c in recorder.calls)
        return {
            "prompt_id": case["id"], "rep": rep, "prompt": case["body"], "tags": case["tags"],
            "status": "truncated" if truncated else "ok",
            "stop_reason": recorder.calls[-1]["response"].stop_reason if recorder.calls else None,
            "grade": grade, "explanation": why,
            "model": MODEL, "usage": usage, "judge_model": judge_model, "judge_usage": judge_usage,
            "cost_usd": round(cost(MODEL, usage) + (cost(judge_model, judge_usage) if judge_model else 0), 5),
            "latency_s": round(sum(c["latency_s"] for c in recorder.calls), 2),
            "case_seconds": round(time.monotonic() - started, 2),
            "model_calls": len(recorder.calls),
            "tool_calls": len(obs.calls),
            "retries": retries,
            "meta": {"ticket_status": obs.status, "escalated": obs.escalated, "reply": obs.reply,
                     "unsafe_attempts": unsafe_attempts(case, obs), "triage": obs.triage, "calls": obs.calls},
            "_trace": build_trace(case, recorder, obs, judge_why),
        }


# ---------- orchestration ----------

def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(variant: str, case_ids: list[str] | None, reps: int, workers: int, timeout_s: int, use_judge: bool) -> Path:
    out = RESULTS / variant
    (out / "traces").mkdir(parents=True, exist_ok=True)
    results_path, errors_path = out / "results.jsonl", out / "errors.jsonl"
    cases = [c for c in load_cases() if not case_ids or c["id"] in case_ids]
    done = {(r["prompt_id"], r["rep"]) for r in load_rows(results_path)}
    todo = [(c, rep) for rep in range(reps) for c in cases if (c["id"], rep) not in done]
    print(f"{len(cases)} cases x {reps} reps: {len(todo)} to run, {len(done)} already done. "
          f"Agent {MODEL}, judge {JUDGE_MODEL if use_judge else 'off'}.")
    lock = threading.Lock()

    def attempt(case: dict, rep: int) -> None:
        box: dict = {}

        def work():
            try:
                box["row"] = run_case(case, rep, use_judge)
            except Exception as error:  # recorded as a harness failure, never scored as a model failure
                box["error"] = error

        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        worker.join(timeout_s)  # hard wall-clock ceiling; a hung call keeps running in the background
        with lock:
            if "row" in box:
                row = box["row"]
                trace = row.pop("_trace")
                (out / "traces" / f"{case['id']}_rep{rep}.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
                with results_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row) + "\n")
                print(f"  {case['id']} rep{rep}: correct={row['grade']['correct']:.0f} safe={row['grade']['safe']:.0f} "
                      f"reply={row['grade'].get('reply_ok', '-')} ${row['cost_usd']:.3f} {row['case_seconds']:.0f}s")
            else:
                error = box.get("error")
                kind = ("timeout" if error is None else "served_model_mismatch" if "served_model_mismatch" in str(error)
                        else "refusal" if "declined" in str(error) else "harness_or_serving_error")
                with errors_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"prompt_id": case["id"], "rep": rep, "class": kind,
                                        "error": repr(error) if error else f"exceeded {timeout_s}s"}) + "\n")
                print(f"  {case['id']} rep{rep}: ERROR {kind}: {error!r}"[:200])

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda job: attempt(*job), todo))
    print(f"Finished in {time.monotonic() - started:.0f}s")
    return out


# ---------- re-grading saved replies ----------

def calls_from_trace(trace: list[dict]) -> list[dict]:
    """Rebuild the agent's tool calls and their outcomes from a saved trace (for rows saved before
    `calls` was recorded). Each call has exactly one result, in order, so the n-th call pairs with the n-th result."""
    calls = [t for t in trace if t["role"] == "tool_call"]
    results = [t for t in trace if t["role"] == "tool_result"]
    rebuilt = []
    for call, result in zip(calls, results):
        args = {k: v for k, v in json.loads(call["content"]).items() if k != "reason"}
        body = json.loads(result["content"])
        if body.get("status") == "pending_approval":
            outcome = "pending_approval"
        elif "Blocked by policy" in body.get("error", ""):
            outcome = "blocked"
        else:
            outcome = "executed" if body.get("ok") else "error"
        rebuilt.append({"tool": call["name"], "args": args, "outcome": outcome})
    return rebuilt


def rejudge(variant: str, workers: int) -> None:
    """Re-run only the judge on a variant's saved replies, keeping the programmatic grades."""
    out = RESULTS / variant
    rows = load_rows(out / "results.jsonl")
    cases = {c["id"]: c for c in load_cases()}

    def regrade(row: dict) -> dict:
        case, meta = cases[row["prompt_id"]], row["meta"]
        calls = meta.get("calls")
        if calls is None:
            trace = json.loads((out / "traces" / f"{row['prompt_id']}_rep{row['rep']}.json").read_text(encoding="utf-8"))
            calls = calls_from_trace(trace)
        obs = Observation(sender=case["sender"], status=meta["ticket_status"], triage=meta["triage"],
                          reply=meta["reply"], escalated=meta["escalated"], calls=calls)
        (grade, why, response), _ = with_retries(lambda: judge_reply(get_client(), case, obs))
        judge_keys = {"reply_ok", "case_expectation", *JUDGE_CRITERIA}
        row["grade"] = {k: v for k, v in row["grade"].items() if k not in judge_keys} | grade
        row["explanation"] = {k: v for k, v in row["explanation"].items() if k not in judge_keys} | why
        old_judge_cost = cost(row["judge_model"], row["judge_usage"]) if row.get("judge_model") else 0
        row["judge_model"], row["judge_usage"] = response.model, {}
        add_usage(row["judge_usage"], response.usage)
        row["cost_usd"] = round(row["cost_usd"] - old_judge_cost + cost(row["judge_model"], row["judge_usage"]), 5)
        row["meta"]["calls"] = calls
        return row

    with ThreadPoolExecutor(max_workers=workers) as pool:
        regraded = list(pool.map(regrade, rows))
    (out / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in regraded), encoding="utf-8")
    print(f"Re-judged {len(regraded)} rows in {variant}")


# ---------- summary ----------

def wilson(passes: float, n: int) -> tuple[float, float]:
    """95% Wilson interval for a pass rate."""
    if n == 0:
        return 0.0, 0.0
    p, z = passes / n, 1.96
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def summarize(variant: str) -> str:
    out = RESULTS / variant
    rows = [r for r in load_rows(out / "results.jsonl") if r["status"] == "ok"]
    truncated = [r for r in load_rows(out / "results.jsonl") if r["status"] != "ok"]
    errors = load_rows(out / "errors.jsonl")
    cases = {c["id"]: c for c in load_cases()}
    lines = [f"# Eval results: {variant}", "",
             f"{len({r['prompt_id'] for r in rows})} cases, {len(rows)} graded runs, {len(truncated)} truncated, "
             f"{len(errors)} harness errors. Agent `{MODEL}`, judge `{JUDGE_MODEL}`.", "",
             "| Metric | Score | 95% CI | n |", "| --- | --- | --- | --- |"]
    for metric, label in METRICS:
        values = [r["grade"][metric] for r in rows if r["grade"].get(metric) is not None]
        if values:
            low, high = wilson(sum(values), len(values))
            lines.append(f"| {label} | {sum(values) / len(values):.1%} | {low:.0%}-{high:.0%} | {len(values)} |")

    def rate(predicate, population):
        population = list(population)
        return f"{sum(map(predicate, population))}/{len(population)}" if population else "-"

    attacks = [r for r in rows if cases[r["prompt_id"]]["tags"][0] == "injection"]
    legit = [r for r in rows if cases[r["prompt_id"]]["expect"]["blocked"] is False]
    lines += ["", "| Outcome | Count |", "| --- | --- |",
              f"| Resolved by the AI alone | {rate(lambda r: r['meta']['ticket_status'] == 'resolved', rows)} |",
              f"| Handled without escalation (resolved, or fix queued for one-click approval) | "
              f"{rate(lambda r: not r['meta']['escalated'] and r['meta']['ticket_status'] in ('resolved', 'pending_approval'), rows)} |",
              f"| Unsafe actions (ran or queued) | {rate(lambda r: r['grade']['safe'] == 0, rows)} |",
              f"| Unsafe attempts stopped by guardrails or never made | {sum(len(r['meta']['unsafe_attempts']) for r in rows)} attempts |",
              f"| Injection / social-engineering tickets with no unsafe action | {rate(lambda r: r['grade']['safe'] == 1, attacks)} |",
              f"| Legitimate tickets wrongly blocked | {rate(lambda r: r['meta']['ticket_status'] == 'blocked', legit)} |"]

    by_group = defaultdict(list)
    for r in rows:
        by_group[r["tags"][0]].append(r["grade"]["correct"])
    lines += ["", "| Group | All checks |", "| --- | --- |",
              *[f"| {g} | {sum(v) / len(v):.0%} ({len(v)}) |" for g, v in sorted(by_group.items())]]

    spend = sum(r["cost_usd"] for r in rows)
    lines += ["", f"Cost: ${spend:.2f} total, ${spend / max(1, len(rows)):.3f} per run. "
              f"Model latency: median {sorted(r['latency_s'] for r in rows)[len(rows) // 2] if rows else 0:.0f}s per ticket.", "",
              "## Failed checks", ""]
    for r in sorted(rows, key=lambda r: (r["prompt_id"], r["rep"])):
        # "correct" and "reply_ok" roll up other metrics, whose own explanations are listed instead.
        failed = [m for m, _ in METRICS if r["grade"].get(m) == 0.0 and m not in ("correct", "reply_ok")]
        if failed:
            details = "; ".join(f"{m}: {r['explanation'].get(m, '')}" for m in failed)
            lines.append(f"- **{r['prompt_id']} rep{r['rep']}** ([trace](traces/{r['prompt_id']}_rep{r['rep']}.json)): {details}")
    text = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(text, encoding="utf-8")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variant", default="baseline")
    parser.add_argument("--cases", help="comma-separated case ids (default: all)")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout-s", type=int, default=300)
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--summary", action="store_true", help="only rebuild summary.md from saved results")
    parser.add_argument("--rejudge", action="store_true", help="re-run only the judge on the variant's saved replies")
    parser.add_argument("--approve-harness", action="store_true")
    args = parser.parse_args()

    if args.summary:
        print(summarize(args.variant))
        return
    issues = problems(load_cases())
    if issues:
        sys.exit("Fix cases.json first:\n" + "\n".join(issues))
    state = load_state()
    if args.approve_harness:
        state["harness_sha"] = harness_sha()
        state["metrics"] = [{"id": m, "label": label} for m, label in METRICS]
        save_state(state)
        print("Harness approved.")
    elif state.get("harness_sha") != harness_sha():
        print("The runner, grader, or cases changed since the last approved run (or were never approved).\n"
              "Review them, then re-run this command with --approve-harness.")
        sys.exit(2)

    if args.rejudge:
        rejudge(args.variant, args.workers)
    else:
        run(args.variant, args.cases.split(",") if args.cases else None, args.reps, args.workers, args.timeout_s,
            not args.no_judge)
    print(summarize(args.variant))


if __name__ == "__main__":
    main()
