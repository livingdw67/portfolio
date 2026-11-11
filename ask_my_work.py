"""Answer a fixed list of questions about Daniel's work by quoting his public write-ups.

No model writes anything here. Each question searches the site and public project READMEs
with BM25, and the answer is the best sentences, word for word, from sources picked by
hand for that question. So it can't invent a career fact and a click costs nothing.

It is a list rather than a search box on purpose. Free typing failed its held-out test:
see evals/ask_results.md. ask_corpus.json is written by scripts/export_ask_corpus.py.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

TOKEN = re.compile(r"[a-z0-9]+")
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])")
STOPWORDS = frozenset("""
a about after all also am an and any are as at be been but by can could did do does done doing for from get got had
has have he her him his how i if in into is it its just kind know knows like made make me more most much my of on one
or our out over please say see she show so some tell than that the their them then there these they this those to
tried try up us use used uses using very want was way we were what when where which who why will with work worked
working works would you your daniel livingston dan experience experienced project projects ever built build building
done anything something give example examples thing things him familiar good
""".split())
CANONICAL = {
    "llms": "llm", "genai": "llm", "generative": "llm", "gpt": "llm",
    "optimization": "optimiz", "optimizer": "optimiz", "optimize": "optimiz", "milp": "optimiz",
    "forecasting": "forecast", "forecasts": "forecast",
    "retrieval": "rag", "citations": "citation", "cited": "citation",
    "tested": "test", "testing": "test", "tests": "test",
    "agents": "agent", "turbofan": "engine", "engines": "engine",
}


@dataclass(frozen=True)
class Topic:
    question: str
    search: str = ""                # the words to look for
    sources: tuple[str, ...] = ()   # the sources read and approved for this question
    listing: str = ""               # or show every passage of this kind instead


TOPICS = [
    Topic("Has he built a RAG system?", "RAG retrieval citations verified grounded page",
          ("michelin-rag", "site-toolkit")),
    Topic("How does he test AI systems?", "held-out questions blind grading tests power vendor baseline",
          ("site-principles", "snowpark-customer-segmentation", "michelin-rag")),
    Topic("How does he keep an AI from making up numbers?",
          "model chooses calculation code computes every number checked source",
          ("site-principles", "snowpark-customer-segmentation", "michelin-rag")),
    Topic("Has he built LLM agents?", "LLM agent tools guardrails orchestration specialists",
          ("park-crowd-forecast", "site-toolkit")),
    Topic("What has he done with semantic layers?", "semantic layer metrics Cortex Analyst MCP governed",
          ("cmapss-predictive-maintenance", "exp-attain-financial")),
    Topic("What has he done with Snowflake?", "Snowflake Snowpark Model Registry feature store",
          ("site-toolkit", "cmapss-predictive-maintenance", "exp-attain-financial")),
    Topic("What has he done with Databricks?", "Databricks Unity Catalog MLflow Delta",
          ("cmapss-predictive-maintenance", "site-toolkit", "loan-default-prediction")),
    Topic("What forecasting has he built?", "forecasts daily crowds Universal Orlando parks 90 days out Databricks errors simple baseline",
          ("park-crowd-forecast",)),
    Topic("Has he used optimization?", "mixed-integer program optimizer staffing shifts",
          ("park-crowd-forecast", "site-toolkit")),
    Topic("Does he run experiments and causal studies?", "A/B tests control groups synthetic control causal",
          ("site-toolkit", "park-crowd-forecast")),
    Topic("What's his predictive maintenance work?", "predictive maintenance turbofan engines failure",
          ("cmapss-predictive-maintenance",)),
    Topic("What business impact has he had?", "incremental revenue accuracy runtime cutting time",
          ("exp-tiaa", "exp-diesel-laptops", "exp-duke-energy")),
    Topic("Where has he worked?", listing="experience"),
    Topic("What are his credentials?", listing="credentials"),
]


def stem(word: str) -> str:
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokenize(text: str) -> list[str]:
    return [stem(CANONICAL.get(word, word)) for word in TOKEN.findall(text.lower()) if word not in STOPWORDS]


@dataclass
class Quote:
    text: str
    source: str
    section: str
    url: str
    key: str


class Index:
    """BM25 over passages. The corpus is a few hundred passages, so plain Python is fast enough."""

    def __init__(self, passages: list[dict], k1: float = 1.4, b: float = 0.6):
        self.passages, self.k1, self.b = passages, k1, b
        # A project's title and section heading count as part of every passage under them.
        self.counts = [Counter(tokenize(f"{p['source']} {p['section']} {p['text']}")) for p in passages]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths) / max(len(self.lengths), 1)
        self.postings: dict[str, list[int]] = {}
        for index, counter in enumerate(self.counts):
            for term in counter:
                self.postings.setdefault(term, []).append(index)
        total = len(passages)
        self.idf = {term: math.log(1 + (total - len(ids) + 0.5) / (len(ids) + 0.5)) for term, ids in self.postings.items()}

    def rank(self, terms: list[str]) -> list[int]:
        scores: Counter = Counter()
        for term in set(terms):
            for index in self.postings.get(term, []):
                tf = self.counts[index][term]
                norm = 1 - self.b + self.b * self.lengths[index] / self.average
                scores[index] += self.idf[term] * tf * (self.k1 + 1) / (tf + self.k1 * norm)
        return [index for index, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))]


def best_sentences(index: Index, passage: dict, terms: list[str], limit: int = 2) -> str:
    """The sentences that carry the most of the search words, kept in reading order."""
    sentences = [s.strip() for s in SENTENCE.split(passage["text"]) if s.strip()]
    wanted = set(terms)

    def weight(sentence: str) -> float:
        return sum(index.idf.get(term, 0.0) for term in set(tokenize(sentence)) & wanted)

    ordered = sorted(range(len(sentences)), key=lambda i: (-weight(sentences[i]), i))
    keep = sorted(i for i in ordered[:limit] if weight(sentences[i]) > 0) or [0]
    return " ".join(sentences[i] for i in keep)


def answer(topic: Topic, index: Index) -> list[Quote]:
    if topic.listing:
        return [Quote(p["text"], p["source"], p["section"], p["url"], p["key"])
                for p in index.passages if p.get("kind") == topic.listing]
    terms = tokenize(topic.search)
    quotes: list[Quote] = []
    used: set[str] = set()
    for passage_index in index.rank(terms):
        passage = index.passages[passage_index]
        if passage["key"] in topic.sources and passage["key"] not in used:
            used.add(passage["key"])
            quotes.append(Quote(best_sentences(index, passage, terms), passage["source"], passage["section"],
                                passage["url"], passage["key"]))
    # The Toolkit line is a list of names, so the write-ups that show the work come first.
    return sorted(quotes, key=lambda quote: quote.key == "site-toolkit")
