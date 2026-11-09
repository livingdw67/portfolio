"""Ask about my work: answers quoted word for word from public write-ups, with no model involved.

A page of the portfolio app, opened from the demos strip (url /ask). The logic is in
ask_my_work.py, and the only text it can quote is ask_corpus.json, written by
scripts/export_ask_corpus.py.
"""
import json
from pathlib import Path

import streamlit as st

from ask_my_work import Index, answer

SUGGESTIONS = [
    "Has Daniel built a RAG system?",
    "How does he test LLM answers?",
    "What has he done with Snowflake?",
    "Has he used mixed-integer programming?",
    "Where has Daniel worked?",
]
RESULTS = "https://github.com/livingdw67/portfolio/blob/main/evals/ask_results.md"


@st.cache_resource(max_entries=1)
def load_index() -> Index:
    path = Path(__file__).parent.parent / "ask_corpus.json"
    return Index(json.loads(path.read_text(encoding="utf-8"))["passages"])


def use_suggestion() -> None:
    picked = st.session_state.get("ask_suggestion")
    if picked:
        st.session_state["ask_question"] = picked


st.title("Ask about my work")
st.markdown(
    "Answers are **quoted word for word** from this site and my public project write-ups, each with its source. "
    "No AI model writes anything here, so it can't make up a fact about me, and asking costs nothing."
)

st.pills("Try one", SUGGESTIONS, key="ask_suggestion", on_change=use_suggestion)
question = st.text_input(
    "Your question", key="ask_question", max_chars=300, placeholder="Try a tool, a method or a topic",
)

if question.strip():
    reply = answer(question, load_index())
    if reply.kind == "listing":
        st.caption(reply.message)
    elif reply.message:
        st.info(reply.message, icon=":material/info:")
    for quote in reply.quotes:
        with st.container(border=True):
            st.markdown(f"**{quote.source}** · {quote.section}")
            st.text(quote.text)
            st.link_button("Read the source", quote.url, icon=":material/open_in_new:")

st.divider()
st.caption(
    f"How well it works: [results on held-out questions]({RESULTS}), including what it missed. "
    "It matches words rather than meaning, so naming a specific tool or topic works best."
)
