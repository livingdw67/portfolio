"""The home page's "Ask about my work" panel: the /ask page's answers, at the top of the site.

Same logic, approved sources and word-for-word quotes as app_pages/ask.py (both use ask_my_work.py).
The panel offers a handful of the questions and the first quotes; the page has every question and source.
No model is involved, so a click costs nothing.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import streamlit as st

from ask_my_work import TOPICS, Index, Quote, answer

BY_QUESTION = {topic.question: topic for topic in TOPICS}
# The questions offered on the home page, in order, with the short label each chip shows.
CHIPS = {
    "How does he test AI systems?": "Testing AI",
    "Has he built a RAG system?": "RAG",
    "Has he built LLM agents?": "LLM agents",
    "How does he keep an AI from making up numbers?": "No made-up numbers",
    "What has he done with Snowflake?": "Snowflake",
    "What has he done with Databricks?": "Databricks",
    "What forecasting has he built?": "Forecasting",
    "What business impact has he had?": "Business impact",
}
SHOWN = 2  # quotes per answer here; the full page shows them all

CSS = """
<style>
.st-key-hero-ask { background: var(--surface); border: 1px solid var(--border); border-top: 3px solid var(--teal);
  border-radius: 10px; padding: 1rem 1.15rem .6rem 1.15rem; gap: .6rem; margin: 0 0 1.5rem 0; }
.ha-where { font-size: .8rem; color: var(--muted); font-weight: 500; margin: 0; }
.ha-title { font-family: var(--display); font-weight: 600; font-size: 1.3rem; line-height: 1.2; color: var(--ink);
  margin: .1rem 0 0 0; }
.st-key-hero-ask [data-testid="stButtonGroup"] button p { font-size: .84rem; }
.ha-q { display: flex; justify-content: flex-end; margin: 0 0 .55rem 0; }
.ha-q span { background: #1d3a4a; border: 1px solid #2f5a66; color: var(--ink); border-radius: 12px 12px 3px 12px;
  padding: .4rem .8rem; font-size: .92rem; max-width: 85%; }
.ha-quote { margin: 0 0 .7rem 0; padding: .1rem 0 .1rem .9rem; border-left: 2px solid var(--teal); }
.ha-quote p { color: var(--ink); font-size: .93rem; line-height: 1.55; margin: 0 0 .2rem 0; }
.ha-quote a { font-size: .8rem; color: var(--muted); text-decoration: none; }
.ha-quote a:hover { color: var(--teal); text-decoration: underline; }
.st-key-hero-ask .stButton button { background: transparent; border: none; min-height: 2rem; padding-left: 0; }
.st-key-hero-ask .stButton button p { font-size: .88rem; color: var(--teal); }
.st-key-hero-ask .stButton button:hover p { color: var(--teal-hover); text-decoration: underline; }
</style>
"""


@st.cache_resource(max_entries=1)
def load_index() -> Index:
    path = Path(__file__).parent / "ask_corpus.json"
    return Index(json.loads(path.read_text(encoding="utf-8"))["passages"])


def _text(s: str) -> str:
    # Escaped for HTML; "$" too, so two dollar figures in one answer don't render as maths.
    return html.escape(s).replace("$", "&#36;")


def _quote(q: Quote) -> str:
    return (f'<blockquote class="ha-quote"><p>{_text(q.text)}</p>'
            f'<a href="{html.escape(q.url, quote=True)}" target="_blank" rel="noopener">'
            f'{_text(q.source)} · {_text(q.section)} ↗</a></blockquote>')


@st.fragment  # a click reruns only this panel, not the page
def ask_panel(full_page) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    with st.container(key="hero-ask"):
        st.markdown('<p class="ha-where">Runs here · answers quoted word for word from my write-ups, no AI model</p>'
                    '<p class="ha-title">Ask about my work</p>', unsafe_allow_html=True)
        first = next(iter(CHIPS))
        picked = st.pills("Pick a question", list(CHIPS), format_func=CHIPS.get, default=first,
                          key="hero-ask-topic", label_visibility="collapsed")
        topic = BY_QUESTION[picked or first]
        quotes = answer(topic, load_index())
        st.markdown(f'<div class="ha-q"><span>{_text(topic.question)}</span></div>'
                    + "".join(_quote(q) for q in quotes[:SHOWN]), unsafe_allow_html=True)
        more = len(quotes) - SHOWN
        label = (f"{more} more source{'s' if more > 1 else ''}, and all {len(TOPICS)} questions" if more > 0
                 else f"All {len(TOPICS)} questions")
        if st.button(label, key="hero-ask-more", type="tertiary", icon=":material/arrow_forward:"):
            st.session_state["ask_topic"] = topic.question  # the full page opens on the same question
            st.switch_page(full_page)
