"""The hero demo: Segment Assistant answers replayed from its graded test runs.

segment_demo.json is written by scripts/export_segment_demo.py from the snowpark-customer-segmentation repo's
practice_eval/results. Every answer, plan, row, figure check and grade below was recorded when the Assistant
(and Cortex Analyst, on the same question) was tested. Nothing here calls a model, so a click costs nothing.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
import streamlit as st

DEMO = json.loads((Path(__file__).parent / "segment_demo.json").read_text(encoding="utf-8"))
BY_ID = {d["id"]: d for d in DEMO}
CODE = "https://github.com/livingdw67/snowpark-customer-segmentation"

# Short labels for the question picker; the chat shows each question exactly as it was asked.
LABELS = {
    "HCP02": "C2-B2 vs C3-B2 revenue",
    "HLK04": "occasinal holiday p buys again",
    "HRK01": "Best revenue per customer",
    "HDC08": "Can I promise these to finance?",
    "HUN05": "Customers in France?",
    "HOT03": "Write me a SQL query",
    "XUN013": "C2-B1 in Lithuania (a miss)",
}
ROUTES = {"analytical": "Calculation agent", "methodology": "Documentation agent", "generative": "Writing agent",
          "out_of_scope": "Out of scope"}
VERDICTS = {"answered-instead-of-declining": "answered instead of declining", "wrong number": "wrong number",
            "unhelpful": "unhelpful", "wrong claim": "wrong claim", "misrouted": "misrouted", "error": "error"}

CSS = """
<style>
.st-key-hero-demo { padding-top: 1.6rem; gap: .55rem; }
.sa-where { font-size: .8rem; color: var(--muted); font-weight: 500; margin: 0; }
.sa-title { font-family: var(--display); font-weight: 600; font-size: 1.35rem; line-height: 1.2; color: var(--ink);
  margin: .1rem 0 .2rem 0; }
.sa-sub { color: var(--muted); font-size: .9rem; margin: 0 0 .35rem 0; line-height: 1.5; }
.st-key-hero-demo [data-testid="stButtonGroup"] button p { font-size: .82rem; }
.sa-q { display: flex; justify-content: flex-end; margin: .2rem 0 0 0; }
.sa-q span { background: #1d3a4a; border: 1px solid #2f5a66; color: var(--ink); border-radius: 12px 12px 3px 12px;
  padding: .45rem .8rem; font-size: .93rem; max-width: 85%; }
[class*="st-key-sa-answer-"] { background: var(--surface); border: 1px solid var(--border); border-radius: 3px 12px 12px 12px;
  padding: .65rem .85rem .2rem .85rem; gap: .2rem; }
[class*="st-key-sa-answer-"] p, [class*="st-key-sa-answer-"] li, [class*="st-key-sa-answer-"] td,
[class*="st-key-sa-answer-"] th { font-size: .9rem; }
[class*="st-key-sa-answer-"] table { margin-bottom: .5rem; }
.sa-who { font-size: .72rem; color: var(--muted); font-weight: 600; letter-spacing: .04em; margin: 0 0 .3rem 0; }
.sa-meta { display: flex; flex-wrap: wrap; gap: 5px; margin: .1rem 0 .1rem 0; }
.sa-meta span { font-size: .76rem; padding: .12rem .55rem; border-radius: 999px; border: 1px solid var(--line);
  color: var(--muted); background: var(--paper); }
.sa-meta span.good { border-color: #2f6b68; color: var(--teal); }
.sa-meta span.bad { border-color: #7a3f3b; color: #e5736b; }
.sa-note { color: var(--muted); font-size: .84rem; margin: .1rem 0 0 0; }
.st-key-hero-demo [data-testid="stExpander"] summary p { font-size: .88rem; }
.st-key-hero-demo [data-testid="stPageLink"] p { font-size: .9rem; }
</style>
"""


def _check_text(check: dict | None) -> tuple[str, str]:
    if not check:
        return "No figures to check", ""
    return ("✓ " if check["ok"] else "✗ ") + check["summary"], "good" if check["ok"] else "bad"


def _verdict(verdict: str) -> tuple[str, str]:
    if verdict == "correct":
        return "Graded correct", "good"
    return f"Graded wrong: {VERDICTS.get(verdict, verdict)}", "bad"


def _plan_text(plan: dict | None) -> str:
    if not plan:
        return ""
    args = ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in plan.items() if k != "tool")
    return f"{plan.get('tool', 'plan')}({args})"


def _chips(items: list[tuple[str, str]]) -> str:
    return '<div class="sa-meta">' + "".join(f'<span class="{c}">{html.escape(t)}</span>' for t, c in items if t) + "</div>"


def _turn(rec: dict) -> None:
    """One question and the Assistant's recorded answer, with how it was produced."""
    a = rec["assistant"]
    st.markdown(f'<div class="sa-q"><span>{html.escape(rec["question"])}</span></div>', unsafe_allow_html=True)
    with st.container(key=f"sa-answer-{rec['id']}"):  # the answers are this app's own recorded data
        st.markdown('<div class="sa-who">SEGMENT ASSISTANT</div>\n\n' + a["answer"], unsafe_allow_html=True)
    route = ROUTES.get(a["route"], a["route"]) + (" · declined" if a["declined"] else "")
    plan = f"Plan: {a['plan']['tool']}" if a.get("plan") else ""
    fixes = f"{len(a['adjust'])} fix{'es' if len(a['adjust']) > 1 else ''} by code" if a["adjust"] else ""
    st.markdown(_chips([(route, ""), (plan, ""), (fixes, ""), _check_text(a["check"]), _verdict(a["verdict"])]),
                unsafe_allow_html=True)
    if a["verdict"] != "correct" and a["note"]:
        st.markdown(f'<div class="sa-note">Grader\'s note: {html.escape(a["note"])}.</div>', unsafe_allow_html=True)


def _how(rec: dict) -> None:
    a = rec["assistant"]
    st.markdown(f"**Route:** {ROUTES.get(a['route'], a['route'])}" + (", which declined the request" if a["declined"] else ""))
    if a.get("plan"):
        st.markdown("**The model's plan** (it picks a calculation and its inputs, nothing else):")
        st.code(_plan_text(a["plan"]), language="python", wrap_lines=True)
    if a["adjust"]:
        st.markdown("**What code changed in the plan:**\n" + "\n".join(f"- {x}" for x in a["adjust"]))
    if a.get("rows"):
        st.markdown("**Rows computed by code:**")
        st.dataframe(pd.DataFrame(a["rows"]), hide_index=True, width="stretch")
    st.markdown(f"**Figure check:** {_check_text(a['check'])[0]}")
    st.caption(f"{a['model']}, {a['llm_calls']} model calls, {a['seconds']:.1f} s. {rec['round']}; code at commit "
               f"`{a['commit']}`.")


def _analyst(rec: dict) -> None:
    n = rec["analyst"]
    label, cls = _verdict(n["verdict"])
    st.markdown(_chips([("Snowflake Cortex Analyst", ""), (label, cls)]), unsafe_allow_html=True)
    if n["text"]:
        st.markdown(n["text"].replace("This is our interpretation of your question:\n\n", "*Its reading of the question:* "))
    if n["rows"]:
        st.dataframe(pd.DataFrame(n["rows"], columns=n["columns"] or None), hide_index=True, width="stretch")
    if n["sql"]:
        sql = "\n".join(line for line in n["sql"].splitlines() if "Generated by Cortex Analyst" not in line).strip()
        st.code(sql, language="sql", wrap_lines=True)


@st.fragment  # a click reruns only this widget, not the page
def segment_demo(tested_page=None) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="sa-where">Replays of graded test runs · nothing here calls a model</div>'
        '<div class="sa-title">Ask the Segment Assistant</div>'
        '<div class="sa-sub">An LLM agent over a semantic layer for 4,261 customer segments. The model only picks '
        "a calculation; tested code computes and checks every figure. Snowflake's Cortex Analyst got the same "
        "questions.</div>",
        unsafe_allow_html=True,
    )
    pick = st.pills("Pick a question", [d["id"] for d in DEMO], format_func=lambda i: LABELS.get(i, BY_ID[i]["question"]),
                    default=DEMO[0]["id"], key="sa-pick", label_visibility="collapsed")
    rec = BY_ID[pick or DEMO[0]["id"]]
    _turn(rec)
    follow = rec.get("follow_up")
    if follow:
        asked = st.session_state.setdefault("sa-follow", set())
        if rec["id"] in asked:
            _turn(follow)
        elif st.button(f"Follow up: “{follow['question']}”", key=f"sa-ask-{rec['id']}", icon=":material/reply:"):
            asked.add(rec["id"])
            st.rerun(scope="fragment")
    shown = follow if follow and rec["id"] in st.session_state.get("sa-follow", set()) else rec
    with st.expander("How it got there", icon=":material/account_tree:"):
        _how(shown)
    if shown.get("analyst"):
        with st.expander("Same question to Cortex Analyst", icon=":material/compare_arrows:"):
            _analyst(shown)
    with st.container(horizontal=True, gap="medium"):
        if tested_page is not None:
            st.page_link(tested_page, label="How the 1,400-question test was run", icon=":material/arrow_forward:")
        st.page_link(CODE, label="Code", icon=":material/code:")
