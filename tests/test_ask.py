"""The page must quote exactly, use only approved sources, and never reach a private repo."""
import json
import re
from pathlib import Path

import pytest

from ask_my_work import TOPICS, Index, answer, tokenize

ROOT = Path(__file__).resolve().parent.parent
PASSAGES = json.loads((ROOT / "ask_corpus.json").read_text(encoding="utf-8"))["passages"]
INDEX = Index(PASSAGES)
ALL_TEXT = " ".join(passage["text"] for passage in PASSAGES)
BY_ID = [topic.question for topic in TOPICS]


def test_word_forms_and_synonyms_resolve_the_same_way():
    assert tokenize("forecasting") == tokenize("forecasts") == ["forecast"]
    assert tokenize("GenAI") == tokenize("LLMs")


@pytest.mark.parametrize("topic", TOPICS, ids=BY_ID)
def test_every_question_has_an_answer(topic):
    assert answer(topic, INDEX)


@pytest.mark.parametrize("topic", [t for t in TOPICS if t.sources], ids=[t.question for t in TOPICS if t.sources])
def test_each_question_shows_exactly_its_approved_sources(topic):
    assert {quote.key for quote in answer(topic, INDEX)} == set(topic.sources)


@pytest.mark.parametrize("topic", TOPICS, ids=BY_ID)
def test_every_answer_is_a_verbatim_quote_of_the_sources(topic):
    for quote in answer(topic, INDEX):
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])", quote.text):
            assert sentence in ALL_TEXT


def test_work_history_matches_the_site():
    history = next(topic for topic in TOPICS if topic.listing == "experience")
    assert [quote.key for quote in answer(history, INDEX)] == [
        "exp-diesel-laptops", "exp-attain-financial", "exp-duke-energy", "exp-tiaa",
    ]


def test_private_repos_never_enter_the_corpus():
    private = {"cfb-betting-sim", "data-canon-core", "music-similarity", "architecture-comparison", "headhunter"}
    assert not private & {passage["key"] for passage in PASSAGES}
    assert not any(name in passage["url"] for name in private for passage in PASSAGES)
