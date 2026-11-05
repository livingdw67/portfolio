"""Copy a few recorded, graded Segment Assistant answers into segment_demo.json for the hero demo.

usage: python scripts/export_segment_demo.py PATH_TO_snowpark-customer-segmentation

Reads practice_eval/results/ from a checkout of https://github.com/livingdw67/snowpark-customer-segmentation:
the held-out retest (questions frozen before the fixes, graded blind) and the power run, both answered by the
same Assistant code, with Cortex Analyst's answers to the same questions and the grades for both.
"""
import csv
import json
import sys
from pathlib import Path

# (question id, round) in the order shown. A follow-up is listed under its parent by the app, not here.
PICKS = [("HCP02", "v2"), ("HLK04", "v2"), ("HRK01", "v2"), ("HDC08", "v2"), ("HUN05", "v2"), ("HOT03", "v2"),
         ("XUN013", "v3")]
FOLLOW_UPS = {"HCP02": ("HFU09", "v2")}
ROUNDS = {
    "v2": dict(name="Held-out retest, graded blind", assistant="v2_assistant_after.jsonl",
               assistant_grades="grades_v2_after.csv", analyst="v2_analyst_r8_answers.jsonl",
               analyst_grades="grades_v2_analyst_r8.csv"),
    "v3": dict(name="Power run, 1,400 paired questions", assistant="v3_assistant_answers.jsonl",
               assistant_grades="grades_v3_assistant.csv", analyst="v3_analyst_answers.jsonl",
               analyst_grades="grades_v3_analyst.csv"),
}
res = Path(sys.argv[1]) / "practice_eval" / "results"


def jsonl(name):
    return {r["id"]: r for r in map(json.loads, (res / name).read_text(encoding="utf-8").splitlines())}


def grades(name):
    with open(res / name, encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


loaded = {k: {f: (jsonl(v[f]) if f in ("assistant", "analyst") else grades(v[f])) for f in v if f != "name"}
          for k, v in ROUNDS.items()}


def record(qid, rnd):
    d = loaded[rnd]
    a, g = d["assistant"][qid], d["assistant_grades"][qid]
    out = {
        "id": qid, "round": ROUNDS[rnd]["name"], "type": a["type"], "question": a["q"],
        "assistant": {"answer": a["answer"], "route": a["intent"], "declined": a["declined"], "plan": a["plan"],
                      "adjust": a["adjust"], "rows": a["rows"], "check": a["check"], "seconds": a["secs"],
                      "llm_calls": a["llm_calls"], "model": a["model"], "commit": a["commit"],
                      "verdict": g["verdict"], "note": g.get("note", "")},
        "analyst": None,
    }
    if qid in d["analyst"] and qid in d["analyst_grades"]:
        n, ng = d["analyst"][qid], d["analyst_grades"][qid]
        out["analyst"] = {"text": n.get("text") or "", "sql": n.get("sql") or "", "columns": n.get("columns") or [],
                          "rows": n.get("rows") or [], "seconds": n.get("secs"), "models": n.get("models") or [],
                          "verdict": ng["verdict"], "note": ng.get("note", "")}
    return out


demo = []
for qid, rnd in PICKS:
    item = record(qid, rnd)
    if qid in FOLLOW_UPS:
        item["follow_up"] = record(*FOLLOW_UPS[qid])
    demo.append(item)

dest = Path(__file__).resolve().parent.parent / "segment_demo.json"
dest.write_bytes((json.dumps(demo, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
print(f"wrote {dest}: {len(demo)} questions, {sum('follow_up' in d for d in demo)} with a follow-up")
