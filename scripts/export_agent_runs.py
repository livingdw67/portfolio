"""Copy the park agent's graded eval runs into app_pages/agent_runs.json for the agent-runs page.

usage: python scripts/export_agent_runs.py PATH_TO_park-crowd-forecast

Reads agent/evals/questions.jsonl and agent/evals/results/*.json from a checkout of
https://github.com/livingdw67/park-crowd-forecast. The newest full run (every question) is the one shown;
earlier full runs are kept as history.
"""
import json
import sys
from pathlib import Path

CATEGORIES = {"f": "Forecast", "s": "Staffing", "b": "Both specialists", "e": "Edge cases",
              "o": "Out of scope", "x": "Prompt injection"}

repo = Path(sys.argv[1]) / "agent" / "evals"
questions = {q["id"]: q for q in map(json.loads, (repo / "questions.jsonl").read_text(encoding="utf-8").splitlines())}
runs = [(p.stem, json.loads(p.read_text(encoding="utf-8"))) for p in sorted((repo / "results").glob("*.json"))]
full = [(stamp, run) for stamp, run in runs if run["summary"]["questions"] == len(questions)]
stamp, latest = full[-1]

out = {
    "run": stamp,
    "history": [dict(run=s, **r["summary"]) for s, r in full],
    "results": [],
}
for r in latest["results"]:
    q = questions[r["id"]]
    out["results"].append({
        "id": r["id"], "category": CATEGORIES[r["id"][0]], "question": r["question"],
        "expected_route": q["route"], "expected_tools": q["tools"], "expect": q.get("expect", "answer"),
        "route": r["route"], "checks": r["checks"], "passed": r["passed"],
        "tools": [{"specialist": s, "tool": t, "error": e} for s, t, e in r["tools_called"]],
        "answer": r["answer"], "seconds": r["seconds"], "cost_usd": r["cost_usd"], "models": r["models"],
    })

dest = Path(__file__).resolve().parent.parent / "app_pages" / "agent_runs.json"
dest.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {dest} from run {stamp}: {len(out['results'])} questions, {len(out['history'])} full runs")
