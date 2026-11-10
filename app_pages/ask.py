"""Ask about my work: answers quoted word for word from public write-ups, with no model involved.

A page of the portfolio app, opened from the demos strip (url /ask). The logic is in
ask_my_work.py, and the only text it can quote is ask_corpus.json, written by
scripts/export_ask_corpus.py.
"""
import json
from pathlib import Path

import streamlit as st

from ask_my_work import TOPICS, Index, answer

BY_QUESTION = {topic.question: topic for topic in TOPICS}
RESULTS = "https://github.com/livingdw67/portfolio/blob/main/evals/ask_results.md"


@st.cache_resource(max_entries=1)
def load_index() -> Index:
    path = Path(__file__).parent.parent / "ask_corpus.json"
    return Index(json.loads(path.read_text(encoding="utf-8"))["passages"])


st.title("Ask about my work")
st.markdown(
    "Pick a question. Answers are **quoted word for word** from this site and my public project write-ups, each with "
    "its source. No AI model writes anything here, so it can't make up a fact about me."
)

picked = st.pills("Questions", list(BY_QUESTION), key="ask_topic", default=TOPICS[0].question)

if picked:
    for quote in answer(BY_QUESTION[picked], load_index()):
        with st.container(border=True):
            st.markdown(f"**{quote.source}** · {quote.section}")
            st.text(quote.text)
            st.link_button("Read the source", quote.url, icon=":material/open_in_new:")

st.divider()
st.caption(
    f"I read the sources behind every answer here. It's a list rather than a search box because [free typing failed "
    f"its test]({RESULTS}), and a wrong answer about my own work is worse than a shorter list."
)
