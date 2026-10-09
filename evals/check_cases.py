"""Validate evals/cases.json against the mock environment and write evals/cases.md for review.

Run with:  python -m evals.check_cases
"""

import json
import re
from collections import Counter
from pathlib import Path

from helpdesk.agent import TOOL_FUNCTIONS
from helpdesk.models import Category
from helpdesk.seed import DEVICES, DOMAIN, QUARANTINE, USERS

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.json"
WRITE_TOOLS = {"reset_password", "unlock_account", "release_email", "block_sign_in"}
EXPECT_KEYS = {"category", "priority", "required", "forbidden", "escalate", "blocked"}


def load_cases() -> list[dict]:
    return json.loads(CASES.read_text(encoding="utf-8"))


def parse_tool_spec(spec: str) -> tuple[str, dict]:
    """'unlock_account:user_id=4' -> ('unlock_account', {'user_id': '4'})."""
    name, _, args = spec.partition(":")
    return name, dict(pair.split("=", 1) for pair in args.split(",")) if args else {}


def problems(cases: list[dict]) -> list[str]:
    emails = {f"{local}@{DOMAIN}" for _, _, local, *_ in USERS}
    user_ids = {str(u[0]) for u in USERS}
    message_ids = {q[0] for q in QUARANTINE}
    hostnames = {d[0] for d in DEVICES}
    found = []
    ids = [c["id"] for c in cases]
    found += [f"duplicate id {i}" for i, n in Counter(ids).items() if n > 1]
    bodies = Counter(c["body"].strip().lower() for c in cases)
    found += [f"duplicate body: {b[:40]}" for b, n in bodies.items() if n > 1]
    for case in cases:
        where, expect = case["id"], case["expect"]
        if set(expect) != EXPECT_KEYS:
            found.append(f"{where}: expect keys {sorted(expect)}")
        if case["sender"] not in emails:
            found.append(f"{where}: unknown sender {case['sender']}")
        found += [f"{where}: bad category {c}" for c in expect["category"] if c not in set(Category)]
        found += [f"{where}: bad priority {p}" for p in expect["priority"] if p not in {"P1", "P2", "P3", "P4"}]
        for spec in expect["required"] + expect["forbidden"]:
            if spec == "ANY_WRITE":
                continue
            name, args = parse_tool_spec(spec)
            if name not in TOOL_FUNCTIONS:
                found.append(f"{where}: unknown tool {name}")
            if "user_id" in args and args["user_id"] not in user_ids:
                found.append(f"{where}: unknown user_id {args['user_id']}")
            if "message_id" in args and args["message_id"] not in message_ids:
                found.append(f"{where}: unknown message {args['message_id']}")
            if "hostname" in args and args["hostname"] not in hostnames:
                found.append(f"{where}: unknown hostname {args['hostname']}")
        if expect["blocked"] is True and expect["required"]:
            found.append(f"{where}: a blocked ticket can't require tools")
    return found


def fence(text: str) -> str:
    """Code fence longer than any backtick run in the text, so ticket text can't close it early."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}\n{text}\n{ticks}"


def show(value) -> str:
    return "either" if value is None else ("yes" if value else "no")


def write_markdown(cases: list[dict]) -> Path:
    groups = Counter(c["tags"][0] for c in cases)
    lines = [
        "# Eval cases", "",
        f"{len(cases)} test tickets. All senders and data are fictional.", "",
        "| Group | Cases |", "| --- | --- |",
        *[f"| {g} | {n} |" for g, n in groups.items()], "",
        "**Reading the expectations:** `required` tools must be called (run or queued for approval); `forbidden` tools "
        "must never be run or queued (`ANY_WRITE` = no reset, unlock, email release or sign-in block at all). "
        "Escalate/Blocked \"either\" means both answers are acceptable.", "",
        "| ID | From | Subject | Category | Priority | Required | Forbidden | Escalate | Blocked |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for c in cases:
        e = c["expect"]
        lines.append(" | ".join([
            f"| {c['id']}", c["sender"].split("@")[0], c["subject"], " / ".join(e["category"]), " / ".join(e["priority"]),
            ", ".join(f"`{s}`" for s in e["required"]) or "-", ", ".join(f"`{s}`" for s in e["forbidden"]) or "-",
            show(e["escalate"]), f"{show(e['blocked'])} |",
        ]))
    lines.append("")
    for c in cases:
        lines += [f"## {c['id']} · {c['subject']}", "", f"From **{c['sender']}** · tags: {', '.join(c['tags'])}", "",
                  fence(c["body"]), ""]
        if c.get("reply_should"):
            lines += [f"**Reply should:** {c['reply_should']}", ""]
    out = HERE / "cases.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


if __name__ == "__main__":
    all_cases = load_cases()
    issues = problems(all_cases)
    for issue in issues:
        print("PROBLEM:", issue)
    print(f"{len(all_cases)} cases, {len(issues)} problems")
    print(Counter(c["tags"][0] for c in all_cases))
    print("expected escalate:", Counter(show(c["expect"]["escalate"]) for c in all_cases))
    print("expected blocked:", Counter(show(c["expect"]["blocked"]) for c in all_cases))
    print(f"Wrote {write_markdown(all_cases)}")
