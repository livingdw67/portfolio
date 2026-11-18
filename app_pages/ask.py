"""Ask about my work: answers quoted word for word from public write-ups, with no model involved.

A page of the portfolio app (url /ask), opened from the panel at the top of the home page
(ask_panel.py), which shows a few of these questions. The logic is in ask_my_work.py, and the only
text it can quote is ask_corpus.json, written by scripts/export_ask_corpus.py.
"""
import streamlit as st

from ask_my_work import TOPICS, answer
from ask_panel import BY_QUESTION, load_index

RESULTS = "https://github.com/livingdw67/portfolio/blob/main/evals/ask_results.md"
# The home page's panel sets this to the question it was showing; otherwise start on the first.
st.session_state.setdefault("ask_topic", TOPICS[0].question)

st.title("Ask about my work")
st.markdown(
    "Pick a question. Answers are **quoted word for word** from this site and my public project write-ups, each with "
    "its source. No AI model writes anything here, so it can't make up a fact about me."
)

picked = st.pills("Questions", list(BY_QUESTION), key="ask_topic")

if picked:
    for quote in answer(BY_QUESTION[picked], load_index()):
        with st.container(border=True):
            st.markdown(f"**{quote.source}** · {quote.section}")
            st.text(quote.text)
            # Each link opens the heading the quote sits under, not the top of the page.
            label = "Read it in the README" if "github.com" in quote.url else "See it on the home page"
            st.link_button(label, quote.url, icon=":material/open_in_new:")

st.divider()
st.caption(
    f"I read the sources behind every answer here. It's a list rather than a search box because [free typing failed "
    f"its test]({RESULTS}), and a wrong answer about my own work is worse than a shorter list."
)
