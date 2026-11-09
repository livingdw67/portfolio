"""Answer questions about Daniel's work by quoting his public write-ups.

No model writes anything here. A question is matched to passages from the site and from
public project READMEs with BM25, and the answer is the best sentences, word for word,
each with its source. That means it can't invent a career fact and a click costs nothing.
When nothing matches well, it says so rather than stretching. Absence from the write-ups
is reported as exactly that, never as "Daniel hasn't done this".

ask_corpus.json is written by scripts/export_ask_corpus.py.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

TOKEN = re.compile(r"[a-z0-9]+")
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])")
INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts)|disregard (the|your) (rules|instructions)"
    r"|(reveal|print|show) (me )?(your|the) (system )?prompt|you are now|developer mode|jailbreak",
    re.I,
)
PERSONAL = re.compile(
    r"\b(salary|compensation|pay|paid|rate|age|old|married|wife|husband|kids?|children|family|religion|politic\w*|"
    r"health|disab\w*|visa|citizen\w*|address|phone|ssn|gender|race)\b",
    re.I,
)
MAX_QUESTION_CHARS = 300

# Filler that says nothing about what is being asked.
STOPWORDS = frozenset("""
a about after all also am an and any are as at be been but by can could did do does done doing for from get got had
has have he her him his how i if in into is it its just kind know knows like made make me more most much my of on one
or our out over please say see she show so some tell than that the their them then there these they this those to
tried try up us use used uses using very want was way we were what when where which who why will with work worked
working works would you your daniel livingston dan experience experienced project projects ever built build building
done anything something give example examples thing things him familiar good
""".split())

# Different words for one idea, resolved the same way in questions and in passages.
CANONICAL = {
    "llms": "llm", "genai": "llm", "generative": "llm", "gpt": "llm", "chatbot": "llm", "chatbots": "llm",
    "optimization": "optimiz", "optimizer": "optimiz", "optimize": "optimiz", "optimizing": "optimiz",
    "optimized": "optimiz", "milp": "optimiz",
    "experimentation": "experiment", "experiments": "experiment", "experimental": "experiment",
    "forecasting": "forecast", "forecasts": "forecast", "forecasted": "forecast", "forecaster": "forecast",
    "retrieval": "rag", "citations": "citation", "cited": "citation", "cite": "citation",
    "evaluate": "eval", "evaluation": "eval", "evaluations": "eval", "evaluating": "eval", "evals": "eval",
    "tested": "test", "testing": "test", "tests": "test",
    "agents": "agent", "agentic": "agent",
    "segments": "segment", "segmentation": "segment", "segmenting": "segment",
    "explainability": "shap", "explainable": "shap",
    "turbofan": "engine", "engines": "engine",
    "kubernetes": "k8s",
}


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


def tokenize(text: str, normalize: bool = True) -> list[str]:
    tokens = []
    for word in TOKEN.findall(text.lower()):
        if word in STOPWORDS:
            continue
        tokens.append(stem(CANONICAL.get(word, word)) if normalize else word)
    return tokens


@dataclass
class Quote:
    text: str
    source: str
    section: str
    url: str
    key: str


@dataclass
class Answer:
    kind: str  # "quotes", "listing", "decline", "personal", "empty" or "blocked"
    quotes: list[Quote] = field(default_factory=list)
    message: str = ""
    keys: list[str] = field(default_factory=list)  # sources in rank order, for the evaluation


# Questions about the person rather than a topic, answered from one part of the site.
LISTINGS = [
    (re.compile(r"\b(where|who) (has|did|does)?\s*(he|daniel)?\s*(work|worked|employ\w*)\b|employers?\b|companies|"
                r"work history|job history|career|resume|background\b", re.I), "experience",
     "Daniel's work history, from the Experience section of this site."),
    (re.compile(r"\b(education|degrees?|masters?|school|university|certifi\w+|credentials?|qualifications?)\b", re.I),
     "credentials", "From the Toolkit section of this site."),
    (re.compile(r"\b(skills|toolkit|tech stack|technologies|what tools)\b", re.I), "toolkit",
     "The Toolkit section of this site."),
]


class Meaning:
    """Match on meaning with a static word-piece embedding (Model2Vec potion-base-8M).

    The model is a table of vectors, so a text's embedding is the average of its pieces'
    vectors. It needs only numpy, runs in milliseconds and writes nothing. It only decides
    which passages to quote. Build the file with scripts/build_ask_model.py.
    """

    SKIP = {"[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"}

    def __init__(self, path: Path, passages: list[dict]):
        with np.load(path, allow_pickle=False) as data:
            tokens = [str(token) for token in data["tokens"]]
            self.table = data["vectors"].astype(np.float32) * float(data["scale"])
        self.vocabulary = {token: i for i, token in enumerate(tokens) if token not in self.SKIP}
        self.matrix = np.vstack([self.embed(f"{p['source']} {p['section']} {p['text']}") for p in passages])

    def pieces(self, text: str) -> list[int]:
        """Lowercase, split on spaces and punctuation, then take the longest known pieces."""
        ids: list[int] = []
        folded = "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")
        for word in re.findall(r"[^\W_]+|[^\w\s]|_", folded):   # the model's tokenizer splits on "_"
            found: list[int] = []
            start = 0
            while start < len(word):
                for end in range(len(word), start, -1):
                    piece = word[start:end] if start == 0 else f"##{word[start:end]}"
                    if piece in self.vocabulary:
                        found.append(self.vocabulary[piece])
                        start = end
                        break
                else:
                    found = []
                    break
            ids.extend(found)
        return ids

    def embed(self, text: str) -> np.ndarray:
        ids = self.pieces(text)
        if not ids:
            return np.zeros(self.table.shape[1], dtype=np.float32)
        vector = self.table[ids].mean(axis=0)
        return vector / max(float(np.linalg.norm(vector)), 1e-9)

    def cosines(self, question: str) -> np.ndarray:
        return self.matrix @ self.embed(question)


class Index:
    """BM25 over passages. The corpus is a few hundred passages, so plain Python is fast enough."""

    def __init__(self, passages: list[dict], normalize: bool = True, k1: float = 1.4, b: float = 0.6,
                 unseen_weight: float = 0.25):
        self.passages, self.normalize, self.k1, self.b = passages, normalize, k1, b
        self.unseen_weight = unseen_weight
        # A project's title and section heading count as part of every passage under them.
        self.counts = [
            Counter(tokenize(f"{p['source']} {p['section']} {p['text']}", normalize)) for p in passages
        ]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths) / max(len(self.lengths), 1)
        self.postings: dict[str, list[int]] = {}
        for index, counter in enumerate(self.counts):
            for term in counter:
                self.postings.setdefault(term, []).append(index)
        total = len(passages)
        self.idf = {
            term: math.log(1 + (total - len(ids) + 0.5) / (len(ids) + 0.5)) for term, ids in self.postings.items()
        }
        # A word the write-ups never use ("comfortable") counts against a match, but only a
        # little, because it says more about how someone talks than about what they're asking.
        self.unseen_idf = math.log(1 + (total + 0.5) / 0.5) * unseen_weight

    def rank(self, terms: list[str]) -> list[tuple[int, float]]:
        scores: Counter = Counter()
        for term in set(terms):
            for index in self.postings.get(term, []):
                tf = self.counts[index][term]
                norm = 1 - self.b + self.b * self.lengths[index] / self.average
                scores[index] += self.idf[term] * tf * (self.k1 + 1) / (tf + self.k1 * norm)
        return sorted(scores.items(), key=lambda item: (-item[1], item[0]))

    def coverage(self, terms: list[str], index: int) -> float:
        """Share of the question's meaning, weighted by word rarity, found in this passage."""
        unique = set(terms)
        total = sum(self.idf.get(term, self.unseen_idf) for term in unique)
        found = sum(self.idf[term] for term in unique if term in self.counts[index])
        return found / total if total else 0.0

    def anchored(self, terms: list[str], index: int, min_idf: float) -> bool:
        """At least one reasonably distinctive word of the question appears in this passage."""
        return any(term in self.counts[index] and self.idf[term] >= min_idf for term in set(terms))


def best_sentences(index: Index, passage: dict, terms: list[str], limit: int = 2,
                   meaning: Meaning | None = None, question: str = "") -> str:
    """The sentences closest to the question, by its words and its meaning, in reading order."""
    sentences = [s.strip() for s in SENTENCE.split(passage["text"]) if s.strip()]
    wanted = set(terms)
    target = meaning.embed(question) if meaning is not None else None

    def weight(sentence: str) -> float:
        words = sum(index.idf.get(term, 0.0) for term in set(tokenize(sentence, index.normalize)) & wanted)
        if target is None:
            return words
        return words + 5.0 * max(float(meaning.embed(sentence) @ target), 0.0)

    scored = sorted(range(len(sentences)), key=lambda i: (-weight(sentences[i]), i))
    keep = sorted(i for i in scored[:limit] if weight(sentences[i]) > 0) or [0]
    return " ".join(sentences[i] for i in keep)


# Tuned on the tuning questions only; results are in evals/ask_results.md. The stricter of two
# equally accurate settings, because quoting something irrelevant looks worse than one refusal.
MIN_COVERAGE = 0.70
MIN_ANCHOR_IDF = 1.0
MIN_COSINE = 0.425
MAX_SOURCES = 3
NO_MATCH = ("That isn't covered in Daniel's public write-ups, which doesn't mean he hasn't done it. "
            "The fastest way to find out is to ask him on LinkedIn.")
NOT_ANSWERED = ("This page only covers Daniel's published work. For anything personal or about terms, "
                "please contact him directly on LinkedIn.")


def answer(question: str, index: Index, min_coverage: float = MIN_COVERAGE,
           min_anchor: float = MIN_ANCHOR_IDF, meaning: Meaning | None = None,
           min_cosine: float = MIN_COSINE) -> Answer:
    question = (question or "").strip()[:MAX_QUESTION_CHARS]
    if not question:
        return Answer("empty", message="Type a question, or pick one of the suggestions.")
    if INJECTION.search(question):
        return Answer("blocked", message="There's no AI model behind this page to give instructions to. "
                                         "It only quotes Daniel's write-ups.")
    if PERSONAL.search(question):
        return Answer("personal", message=NOT_ANSWERED)

    terms = tokenize(question, index.normalize)
    for pattern, kind, intro in LISTINGS:
        match = pattern.search(question)
        if not match:
            continue
        # "Where has he worked?" is about the person; "any background in forecasting?" is a topic.
        trigger = set(tokenize(match.group(0), index.normalize))
        if not [term for term in terms if term not in trigger and term in index.postings]:
            rows = [p for p in index.passages if p.get("kind") == kind]
            quotes = [Quote(p["text"], p["source"], p["section"], p["url"], p["key"]) for p in rows]
            return Answer("listing", quotes=quotes, message=intro, keys=[p["key"] for p in rows])

    if not terms:
        return Answer("empty", message="Try naming a tool, a method or a topic, such as Snowflake or forecasting.")
    ranked = [passage_index for passage_index, _ in index.rank(terms)]
    cosines = meaning.cosines(question) if meaning is not None else None
    if cosines is not None:
        # Reciprocal rank fusion: a passage that either method ranks highly moves up.
        by_meaning = [int(i) for i in np.argsort(-cosines, kind="stable")]
        fused: Counter = Counter()
        for order in (ranked, by_meaning):
            for position, passage_index in enumerate(order, 1):
                fused[passage_index] += 1.0 / (60 + position)
        ranked = [passage_index for passage_index, _ in sorted(fused.items(), key=lambda item: (-item[1], item[0]))]

    def good_enough(passage_index: int) -> bool:
        if cosines is not None and cosines[passage_index] >= min_cosine:
            return True
        return index.coverage(terms, passage_index) >= min_coverage and index.anchored(terms, passage_index, min_anchor)

    if not ranked or not any(good_enough(passage_index) for passage_index in ranked[:10]):
        return Answer("decline", message=NO_MATCH)

    quotes: list[Quote] = []
    used: set[str] = set()
    keys: list[str] = []
    for passage_index in ranked:
        if len(quotes) >= MAX_SOURCES:
            break
        passage = index.passages[passage_index]
        if passage["key"] in used or not good_enough(passage_index):
            continue
        used.add(passage["key"])
        keys.append(passage["key"])
        quotes.append(Quote(best_sentences(index, passage, terms, meaning=meaning, question=question),
                            passage["source"], passage["section"], passage["url"], passage["key"]))
    return Answer("quotes", quotes=quotes, keys=keys)
