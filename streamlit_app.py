"""Daniel Livingston: data science portfolio.

A storefront for every repo Daniel owns and has starred on GitHub.
Repos are pulled from the GitHub API (refreshed once a day), then
dressed up with the curated titles and results in projects.json.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import json
import posixpath
import re
import time
from pathlib import Path

import requests
import streamlit as st

from segment_demo import segment_demo

# ---------------------------------------------------------------------------
# Personal settings: edit these
# ---------------------------------------------------------------------------
GITHUB_USER = "livingdw67"
NAME = "Daniel Livingston"
ROLE = "Principal Data Scientist"
CREDENTIALS = ["M.S. Applied Statistics", "AWS Certified ML"]  # pills beside your name
LOCATION = "Greer, SC"
LINKEDIN = "https://www.linkedin.com/in/daniel-w-livingston"
EMAIL = ""  # optional, e.g. "you@example.com"; shown in the footer when set
REFRESH = dt.timedelta(hours=24)  # how often to re-check GitHub for repos and READMEs
RETRY_AFTER_FAILURE = dt.timedelta(minutes=15)  # pause before asking GitHub again after it fails

HEADLINE = "AI that shows its work."

INTRO = (
    "Twelve years building, deploying and monitoring production models, most recently as Principal Data Scientist "
    "at Diesel Laptops. I design AI architecture and build it hands-on: semantic layers that reports, agents and MCP "
    "servers all consume, retrieval grounded in governed data, and agent orchestration with tools, state, failure "
    "handling and guardrails, tested the way you'd test any other claim."
)

PRINCIPLES = [
    ("Governance enforced by code", "One definition of each metric, shared by a report, an AI assistant and an MCP "
                                    "server under a read-only role, with all 80 metrics reconciled against hand-written SQL."),
    ("The model chooses, code computes", "LLMs pick which calculation to run; tested code computes the figures, and "
                                         "every number in an answer is checked against its source."),
    ("Tested like an experiment", "Held-out questions, blind grading and tests sized for power against a vendor "
                                  "baseline, and control groups for models in production."),
]

# (when, organisation, role, what) from the current resume
EXPERIENCE = [
    ("2026", "Diesel Laptops", "Principal Data Scientist (contract)",
     "Deployed a classifier that separates sensor errors from physical coolant leaks, improving the diagnostic "
     "product's accuracy by 16%, peer-reviewed graph neural network models, and cut pipeline runtime by 30% under Dagster."),
    ("2026", "Attain Financial", "Contract data scientist",
     "Designed a five-schema Snowflake architecture with isolated environments and audit logging, served a collections "
     "forecast from the Model Registry, and built a Cortex Analyst semantic layer for finance users."),
    ("2024 to 2025", "Duke Energy", "Contract data scientist",
     "Built a centralized feature store across smart meter, program and demographic data, cutting data preparation "
     "and model building time by 50%, and introduced control groups for enterprise models."),
    ("2014 to 2023", "TIAA", "Senior Data Scientist, Enterprise Analytics, 2016 to 2023 · Contractor, 2014 to 2016",
     "Built the propensity models behind a recommendation system that drove $36M in incremental revenue in six months, "
     "an XGBoost churn model with SHAP explanations, and the model monitoring process that became the firm's standard."),
]

TOOLKIT = [
    ("Snowflake", "Snowpark, stored procedures, Model Registry, feature stores, Cortex Analyst semantic views, MCP server"),
    ("Databricks", "PySpark, Delta Lake, Unity Catalog, MLflow, Jobs, Asset Bundles, Apps, Genie"),
    ("Modeling", "LightGBM, XGBoost, scikit-learn, PyTorch, Optuna, time-series backtests, survival analysis, SHAP"),
    ("Optimization and causal inference", "Mixed-integer programming (OR-Tools, HiGHS), A/B tests, difference-in-differences, "
                                          "synthetic control, power analysis"),
    ("Applied AI", "LLM agents and tool orchestration, RAG with citations, MCP, text-to-SQL over semantic layers, "
                   "guardrails, LLM evaluation"),
    ("Engineering", "Python, SQL, Git, pytest, GitHub Actions, Docker, FastAPI, Dagster, Kedro, Azure ML, AWS, SAS, R"),
    ("Credentials", "M.S. Applied Statistics. AWS Certified Machine Learning, Associate (2024)"),
]

# Domain -> (css slug, colour). The colour runs down the left edge of each card.
# Brand support colours, so teal (action) and amber (highlight) keep their jobs.
DOMAINS = {
    "Applied AI": ("ai", "#a99bd6"),
    "Energy & industry": ("energy", "#e5736b"),
    "Finance": ("finance", "#7fa6d1"),
    "Customer analytics": ("customer", "#f0c96a"),
    "Analytics engineering": ("analytics", "#9fb1c7"),
    "Data science": ("general", "#6f86a3"),  # catch-all for repos with no curated domain
}
DOMAIN_KEYWORDS = [
    ("Applied AI", {"rag", "llm", "llms", "agent", "agents", "langgraph", "langchain", "gpt", "chatbot", "nlp", "genai", "openai"}),
    ("Energy & industry", {"grid", "energy", "load", "solar", "ev", "maintenance", "turbofan", "cmapss", "power", "utility", "rul"}),
    ("Finance", {"loan", "credit", "default", "fraud", "bank", "finance", "financial", "risk", "churn", "lending"}),
    ("Customer analytics", {"segment", "segmentation", "customer", "customers", "uplift", "marketing", "criteo", "recommendation", "rfm"}),
    ("Analytics engineering", {"dbt", "metricflow", "dagster", "warehouse", "elt"}),
]

ACRONYMS = {"rag": "RAG", "llm": "LLM", "ml": "ML", "ai": "AI", "ev": "EV", "api": "API", "sql": "SQL",
            "nlp": "NLP", "aws": "AWS", "rfm": "RFM", "cmapss": "C-MAPSS", "automl": "AutoML", "shap": "SHAP"}

HERE = Path(__file__).parent

# ---------------------------------------------------------------------------
# Page setup and styling
# ---------------------------------------------------------------------------
st.set_page_config(  # each page's browser-tab title comes from its st.Page at the bottom
    page_icon=str(HERE / "assets" / "favicon.png"),  # teal D on navy with the amber dot
    layout="wide",
    initial_sidebar_state="collapsed",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;500;600;700&display=swap');

:root {
  /* Brand colours (Branding/brand-guide.md): navy ground, teal for the main line and the
     primary action, amber for the one thing to look at */
  --ink: #f2f5f9;
  --muted: #9fb1c7;
  --faint: #6f86a3;
  --paper: #0e1a2b;
  --surface: #16283f;
  --line: #2b3f58;
  --border: #3a5373;
  --muted-line: #3c5a7d;
  --teal: #5fc4c0;
  --teal-hover: #79d7d3;
  --on-teal: #0e1a2b;
  --amber: #f0a742;
  /* Brand type (Branding/brand-guide.md): Segoe UI, Open Sans where it isn't installed; headings at 600 */
  --body: 'Segoe UI', 'Open Sans', system-ui, -apple-system, sans-serif;
  --display: var(--body);
}

/* Streamlit chrome off */
header[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stHeaderActionElements"] { display: none !important; }

.stApp { background: var(--paper); color: var(--ink); }
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp button,
.stMarkdown, [data-testid="stMarkdownContainer"] { font-family: var(--body); }
.stApp p { line-height: 1.6; }

[data-testid="stMainBlockContainer"], .block-container {
  max-width: 1120px; padding-top: 3rem; padding-bottom: 4rem;
  padding-left: 1.5rem; padding-right: 1.5rem;
}

a { color: var(--teal); }
a:focus-visible, button:focus-visible, input:focus-visible {
  outline: 3px solid var(--teal) !important; outline-offset: 2px;
}

/* ---------- Hero ---------- */
.hero-id { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px; margin-bottom: 1.6rem; }
.hero-id img { width: 56px; height: 56px; border-radius: 50%; border: 2px solid var(--surface);
  box-shadow: 0 0 0 1px var(--border); }
.hero-id .who { font-size: .95rem; color: var(--muted); line-height: 1.35; }
.hero-id .who strong { color: var(--ink); font-weight: 600; display: block; }
.creds { display: flex; flex-wrap: wrap; gap: 6px; }
.creds span { font-size: .8rem; padding: .16rem .65rem; border-radius: 999px;
  border: 1px solid var(--border); color: var(--muted); }
.hero h1 {
  font-family: var(--display); font-weight: 600; color: var(--ink);
  font-size: clamp(2.25rem, 4.8vw, 3.5rem); line-height: 1.1; letter-spacing: -0.02em;
  margin: 0; padding: 0; max-width: 14ch;
}
.hero .rule { width: 64px; height: 3px; background: var(--amber); border-radius: 2px; margin: 1.3rem 0 1.2rem 0; }
.hero .intro { font-size: 1.15rem; color: var(--ink); max-width: 36rem; margin: 0 0 1.75rem 0; }
.principles { display: grid; gap: .9rem; margin: 0 0 2rem 0; max-width: 36rem; }
.principles div { border-left: 2px solid var(--line); padding-left: 14px; }
.principles dt { font-weight: 600; color: var(--ink); }
.principles dd { margin: 0; color: var(--muted); font-size: .97rem; }
.cta { display: flex; flex-wrap: wrap; gap: 10px; }
.cta a { text-decoration: none; font-weight: 500; font-size: .97rem; padding: .62rem 1.05rem;
  border-radius: 6px; border: 1px solid var(--border); color: var(--ink); background: var(--surface); }
.cta a.primary { background: var(--teal); border-color: var(--teal); color: var(--on-teal); font-weight: 600; }
.cta a:hover { border-color: var(--teal); color: var(--ink); }
.cta a.primary:hover { background: var(--teal-hover); color: var(--on-teal); }

/* ---------- Section headings ---------- */
.section-head { margin: 5rem 0 1.25rem 0; }
.section-head h2 { font-family: var(--display); font-weight: 600; font-size: clamp(1.7rem, 3vw, 2.2rem);
  letter-spacing: -0.01em; color: var(--ink); margin: 0 0 .35rem 0; padding: 0; }
.section-head p { color: var(--muted); margin: 0; max-width: 40rem; }

/* ---------- Demos ---------- */
[class*="st-key-demo-"] {
  background: var(--surface); border: 1px solid var(--border); border-top: 3px solid var(--teal);
  border-radius: 10px; padding: 1.1rem 1.15rem 1rem 1.15rem; gap: .55rem; height: 100%;
}
.demo-where { font-size: .8rem; color: var(--muted); font-weight: 500; margin: 0; }
.demo-title { font-family: var(--display); font-weight: 600; font-size: 1.2rem; line-height: 1.25; color: var(--ink);
  margin: .1rem 0 .35rem 0; padding: 0; }
.demo-what { color: var(--ink); font-size: .93rem; margin: 0; }
.demo-for { color: var(--muted); font-size: .84rem; margin: .45rem 0 0 0; }
.demo { padding-bottom: 1.1rem; }  /* room for the button Streamlit pulls up under markdown */

/* ---------- Filters ---------- */
[data-testid="stWidgetLabel"] p { font-size: .88rem; color: var(--muted); font-weight: 500; }
[data-testid="stButtonGroup"] div:has(> button) { flex-wrap: wrap; }  /* domain pills wrap rather than clip */

/* ---------- Project cards ---------- */
[class*="st-key-card-"] {
  background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--faint);
  border-radius: 10px; padding: 1.35rem 1.4rem 1.1rem 1.4rem; gap: .5rem;
}
.pc-domain { font-size: .86rem; font-weight: 600; display: flex; align-items: center; gap: 7px; margin-bottom: .3rem; }
.pc-domain i { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.pc-also { color: var(--muted); font-weight: 500; }
.pc-title { font-family: var(--display); font-weight: 600; color: var(--ink); letter-spacing: -0.01em;
  font-size: 1.45rem; line-height: 1.2; margin: 0 0 .55rem 0; padding: 0; }
.pc-result { color: var(--ink); font-size: 1rem; margin: 0 0 .5rem 0; }
.pc-desc { color: var(--muted); font-size: .93rem; margin: 0 0 .7rem 0; }
.pc-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: .2rem 0 .75rem 0; }
.pc-chips span { font-size: .8rem; padding: .18rem .6rem; border-radius: 999px;
  background: var(--paper); border: 1px solid var(--line); color: var(--ink); }
.pc { padding-bottom: 1.25rem; }  /* Streamlit pulls the next element 1rem up under markdown */
.pc-meta { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: .84rem; color: var(--muted); }
.lead .pc-title { font-size: clamp(1.7rem, 3.2vw, 2.3rem); }
.lead .pc-result { font-size: 1.12rem; max-width: 46rem; }
.lead .pc-desc { max-width: 46rem; }

/* Buttons */
.stButton button, .stLinkButton a {
  border-radius: 6px; font-weight: 500; border: 1px solid var(--border); min-height: 2.5rem;
  background: var(--surface); color: var(--ink);
}
.stButton button:hover, .stLinkButton a:hover { border-color: var(--teal); color: var(--ink); }
.stButton button[kind="primary"], .stButton button[data-testid="stBaseButton-primary"],
.stLinkButton a[data-testid="stBaseLinkButton-primary"] {
  background: var(--teal); border-color: var(--teal); color: var(--on-teal); font-weight: 600;
}
.stButton button[data-testid="stBaseButton-primary"] p,
.stLinkButton a[data-testid="stBaseLinkButton-primary"] p { color: var(--on-teal); }
.stButton button[data-testid="stBaseButton-primary"]:hover,
.stLinkButton a[data-testid="stBaseLinkButton-primary"]:hover {
  background: var(--teal-hover); border-color: var(--teal-hover); color: var(--on-teal);
}

.empty { background: var(--surface); border: 1px dashed var(--border); border-radius: 10px;
  padding: 2rem; color: var(--muted); }
.note { color: var(--muted); font-size: .88rem; margin: .25rem 0 1rem 0; }

/* ---------- Experience timeline ---------- */
.timeline { border-left: 2px solid var(--line); margin-left: 6px; padding-left: 26px; }
.tl-item { position: relative; padding-bottom: 1.9rem; max-width: 46rem; }
.tl-item::before { content: ""; position: absolute; left: -33px; top: .45rem; width: 12px; height: 12px;
  border-radius: 50%; background: var(--paper); border: 2px solid var(--muted); }
.tl-when { color: var(--muted); font-size: .9rem; }
.tl-org { font-family: var(--display); font-weight: 600; font-size: 1.3rem; color: var(--ink); margin: .1rem 0 .1rem 0; }
.tl-role { font-weight: 500; color: var(--ink); }
.tl-item p { color: var(--ink); margin: .35rem 0 0 0; }

/* ---------- Toolkit ---------- */
.toolkit { display: grid; grid-template-columns: 13rem 1fr; gap: 0; max-width: 54rem; }
.toolkit dt, .toolkit dd { padding: .85rem 0; border-top: 1px solid var(--line); margin: 0; }
.toolkit dt { font-weight: 600; color: var(--ink); }
.toolkit dd { color: var(--ink); }

/* ---------- Footer ---------- */
.foot { margin-top: 5rem; padding-top: 2rem; border-top: 1px solid var(--line);
  display: flex; flex-wrap: wrap; justify-content: space-between; gap: 1.5rem; align-items: flex-end; }
.foot h2 { font-family: var(--display); font-weight: 600; font-size: 1.8rem; letter-spacing: -0.01em;
  margin: 0 0 .4rem 0; padding: 0; color: var(--ink); }
.foot p { color: var(--muted); margin: 0; }
.foot .small { font-size: .84rem; color: var(--faint); }

/* ---------- README dialog ---------- */
div[role="dialog"] { border-radius: 10px; }
div[role="dialog"] img { max-width: 100%; height: auto; }
div[role="dialog"] h1, div[role="dialog"] h2, div[role="dialog"] h3 { font-family: var(--display); letter-spacing: -0.01em; }

@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"], .block-container { padding-left: 1rem; padding-right: 1rem; padding-top: 1.75rem; }
  .st-key-hero-demo { padding-top: .5rem; }
  .toolkit { grid-template-columns: 1fr; }
  .toolkit dt { padding-bottom: .1rem; }
  .toolkit dd { border-top: none; padding-top: 0; }
  .section-head { margin-top: 3.5rem; }
  [class*="st-key-card-"] { padding: 1.1rem 1.1rem .9rem 1.1rem; }
}
</style>
"""
DOMAIN_CSS = "".join(f'[class*="st-key-card-{slug}-"] {{ border-left-color: {colour}; }}'
                     for slug, colour in DOMAINS.values())
st.markdown(CSS + f"<style>{DOMAIN_CSS}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    try:
        token = st.secrets.get("GITHUB_TOKEN", "")
    except Exception:  # no secrets file
        token = ""
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


REPO_FIELDS = ("name", "description", "topics", "language", "stargazers_count",
               "pushed_at", "updated_at", "html_url", "homepage", "default_branch")


@st.cache_data(ttl=REFRESH, show_spinner=False)
def fetch_my_starred(user: str) -> list[dict]:
    """Repos the user owns and has starred, trimmed to the fields the app uses.

    Raises on any failure, so a bad or partial response is never cached.
    """
    repos: list[dict] = []
    for page in range(1, 11):
        r = requests.get(
            f"https://api.github.com/users/{user}/starred",
            params={"per_page": 100, "page": page},
            headers=_headers(),
            timeout=15,
        )
        r.raise_for_status()
        batch = r.json()
        if not isinstance(batch, list):
            raise ValueError("GitHub returned an unexpected response.")
        repos.extend(
            {k: repo.get(k) for k in REPO_FIELDS}
            for repo in batch
            if (repo.get("owner") or {}).get("login", "").lower() == user.lower()
        )
        if len(batch) < 100:
            break
    return repos


@st.cache_resource
def _github_state() -> dict:
    """Shared by all visitors: the last good repo list and when GitHub last failed."""
    return {"repos": None, "failed_at": 0.0}


def load_repos(user: str) -> list[dict] | None:
    """Fresh repos, else the last good list, else None if GitHub has never answered."""
    state = _github_state()
    # After a failure, wait before retrying so every widget click doesn't hit GitHub again.
    if time.time() - state["failed_at"] >= RETRY_AFTER_FAILURE.total_seconds():
        try:
            state["repos"] = fetch_my_starred(user)
        except Exception:  # rate limit, network, etc.
            state["failed_at"] = time.time()
    return state["repos"]


@st.cache_data(ttl=REFRESH, show_spinner=False)
def fetch_readme(repo: str, branch: str) -> tuple[str, str] | None:
    """(markdown, folder the README lives in), or None if the repo has no README.

    Raises if GitHub can't be reached, so a failure is never cached.
    """
    r = requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{repo}/readme",
                     headers=_headers(), timeout=15)
    if r.status_code == 404:
        return None
    if r.ok:
        data = r.json()
        text = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return text, posixpath.dirname(data["path"])
    # The API refused, usually the anonymous rate limit. Raw files don't count against it.
    for name in ("README.md", "readme.md", "Readme.md"):
        raw = requests.get(f"https://raw.githubusercontent.com/{GITHUB_USER}/{repo}/{branch}/{name}", timeout=15)
        if raw.ok and raw.text.strip():
            return raw.text, ""
    r.raise_for_status()


def load_curation() -> dict:
    # Not cached: the file is tiny, and caching would hide pushed edits until the app restarts.
    path = HERE / "projects.json"
    if not path.exists():
        return {"featured_order": [], "projects": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def prettify(name: str) -> str:
    words = re.split(r"[-_\s]+", name)
    return " ".join(ACRONYMS.get(w.lower(), w.capitalize()) for w in words if w)


def classify(*texts: str) -> str:
    tokens = set(re.findall(r"[a-z0-9]+", " ".join(t for t in texts if t).lower()))
    for domain, words in DOMAIN_KEYWORDS:
        if tokens & words:
            return domain
    return "Data science"


def ago(iso: str | None) -> str:
    if not iso:
        return ""
    when = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    days = (dt.datetime.now(dt.timezone.utc) - when).days
    if days < 1:
        return "Updated today"
    if days < 2:
        return "Updated yesterday"
    if days < 30:
        return f"Updated {days} days ago"
    if days < 365:
        months = days // 30
        return f"Updated {months} month{'s' if months > 1 else ''} ago"
    years = days // 365
    return f"Updated {years} year{'s' if years > 1 else ''} ago"


def secondary_domains(c: dict, domain: str) -> list[str]:
    """Extra domains from projects.json ("also"). They count for the filter; the card keeps one colour."""
    return [d for d in c.get("also", []) if d in DOMAINS and d != domain]


def build_projects() -> tuple[list[dict], bool]:
    """Merge live starred repos with curated metadata. Returns (projects, live?)."""
    cur = load_curation()
    curated = cur.get("projects", {})
    order = {name: i for i, name in enumerate(cur.get("featured_order", []))}

    repos = load_repos(GITHUB_USER)
    live = repos is not None

    projects = []
    if live:
        for r in repos:
            c = curated.get(r["name"], {})
            domain = c.get("domain") or classify(r["name"], r.get("description") or "", " ".join(r.get("topics") or []))
            projects.append({
                "name": r["name"],
                "title": c.get("title") or prettify(r["name"]),
                "domain": domain,
                "also": secondary_domains(c, domain),
                "result": c.get("result", ""),
                "description": r.get("description") or "",
                "stack": c.get("stack") or [t.replace("-", " ") for t in (r.get("topics") or [])][:6],
                "language": r.get("language") or "",
                "stars": r.get("stargazers_count", 0),
                "updated": r.get("pushed_at") or r.get("updated_at"),
                "url": r.get("html_url"),
                "homepage": c.get("homepage") or r.get("homepage") or "",
                "page": c.get("page", ""), "page_label": c.get("page_label", ""),
                "branch": r.get("default_branch") or "main",
                "order": order.get(r["name"], 10_000),
            })
    else:
        # GitHub unreachable or rate-limited: fall back to the curated list.
        for name, c in curated.items():
            if name.startswith("_"):
                continue
            domain = c.get("domain") or classify(name)
            projects.append({
                "name": name, "title": c.get("title") or prettify(name),
                "domain": domain, "also": secondary_domains(c, domain), "result": c.get("result", ""),
                "description": "", "stack": c.get("stack", []), "language": "", "stars": 0,
                "updated": None, "url": f"https://github.com/{GITHUB_USER}/{name}",
                "homepage": c.get("homepage", ""), "branch": c.get("branch", "main"),
                "page": c.get("page", ""), "page_label": c.get("page_label", ""),
                "order": order.get(name, 10_000),
            })
    return projects, live


# ---------------------------------------------------------------------------
# README rendering
# ---------------------------------------------------------------------------
def dark_image(m: re.Match) -> str:
    """A <picture> with light and dark versions becomes a plain <img> of the dark one: this site is always dark,
    and a <source srcset> would otherwise point at this site rather than at GitHub."""
    block = m[0]
    img = re.search(r"<img\b[^>]*>", block)
    dark = re.search(r"<source\b[^>]*prefers-color-scheme:\s*dark[^>]*>", block)
    srcset = re.search(r'srcset="([^"\s]+)', dark[0]) if dark else None
    if not img:
        return block
    if not srcset:
        return img[0]
    return re.sub(r'\ssrc="[^"]*"', f' src="{srcset[1]}"', img[0], count=1)


@st.cache_data(ttl=REFRESH, show_spinner=False)
def svg_width(url: str) -> float | None:
    """The drawing's natural width in pixels, from its viewBox. Raises if it can't be fetched, so a failure isn't cached."""
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    box = re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+) [\d.]+"', r.text)
    return float(box[1]) if box else None


def mermaid_image(m: re.Match) -> str:
    """Markdown here can't draw Mermaid diagrams, so render them as an image with mermaid.ink, in the site's colours.
    A wide diagram keeps its natural size and scrolls sideways, as on GitHub, rather than shrinking past reading."""
    code = base64.urlsafe_b64encode(m[1].encode("utf-8")).decode("ascii")
    url = f"https://mermaid.ink/svg/{code}?theme=dark&bgColor=!16283f"
    try:
        width = svg_width(url)
    except requests.RequestException:
        width = None
    if not width:
        return f'<img alt="Diagram" src="{url}">\n'
    return (f'<div style="overflow-x: auto"><img alt="Diagram" src="{url}" '
            f'style="width: {width:.0f}px; max-width: none; height: auto"></div>\n')


def absolutize(md: str, repo: str, branch: str, folder: str = "") -> str:
    """Point relative images and links at GitHub. `folder` is where the README lives."""
    raw = f"https://raw.githubusercontent.com/{GITHUB_USER}/{repo}/{branch}/"
    blob = f"https://github.com/{GITHUB_USER}/{repo}/blob/{branch}/"

    def fix(url: str, base: str) -> str:
        if re.match(r"^(https?:|mailto:|#|data:|//)", url):
            return url
        if url.startswith("/"):  # relative to the repo root
            return base + url.lstrip("/")
        return base + posixpath.normpath(posixpath.join(folder, url))

    md = re.sub(r"(?s)<picture>.*?</picture>", dark_image, md)
    md = re.sub(r"(?s)```mermaid\n(.*?)```", mermaid_image, md)
    md = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)([^)]*)\)", lambda m: f"![{m[1]}]({fix(m[2], raw)}{m[3]})", md)
    md = re.sub(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)([^)]*)\)", lambda m: f"[{m[1]}]({fix(m[2], blob)}{m[3]})", md)
    md = re.sub(r'(<img[^>]*?\ssrc=")([^"]+)"', lambda m: f'{m[1]}{fix(m[2], raw)}"', md)
    return md


def open_writeup(p: dict) -> None:
    def body() -> None:
        meta = [x for x in (p["language"], ago(p["updated"])) if x]
        if meta:
            st.caption("   ".join(meta))
        try:
            readme = fetch_readme(p["name"], p["branch"])
        except Exception:
            st.warning("GitHub isn't responding right now, so the write-up can't load. "
                       "Try again in a few minutes, or read it on GitHub.")
        else:
            if readme:
                md, folder = readme
                st.markdown(absolutize(md, p["name"], p["branch"], folder), unsafe_allow_html=True)
            else:
                st.info("This project doesn't have a README yet. The code is on GitHub.")
        st.link_button("View the code on GitHub", p["url"], width="stretch")

    st.dialog(p["title"], width="large")(body)()


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------
def hero() -> None:
    left, right = st.columns([1.45, 1], gap="large")
    creds = "".join(f"<span>{html.escape(c)}</span>" for c in CREDENTIALS)
    principles = "".join(
        f"<div><dt>{html.escape(t)}</dt><dd>{html.escape(d)}</dd></div>" for t, d in PRINCIPLES
    )
    with left:
        st.markdown(
            f"""
<div class="hero">
  <div class="hero-id">
    <img src="https://github.com/{GITHUB_USER}.png?size=160" alt="Photo of {html.escape(NAME)}">
    <div class="who"><strong>{html.escape(NAME)}</strong>{html.escape(ROLE)}, {html.escape(LOCATION)}</div>
    {f'<div class="creds">{creds}</div>' if creds else ''}
  </div>
  <h1>{html.escape(HEADLINE)}</h1>
  <div class="rule"></div>
  <p class="intro">{html.escape(INTRO)}</p>
  <dl class="principles">{principles}</dl>
  <div class="cta">
    <a class="primary" href="#demos" target="_self">Try a demo</a>
    <a href="#projects" target="_self">See the projects</a>
    <a href="{LINKEDIN}" target="_blank" rel="noopener">LinkedIn</a>
    <a href="https://github.com/{GITHUB_USER}" target="_blank" rel="noopener">GitHub</a>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    with right, st.container(key="hero-demo"):
        segment_demo(PAGES["power-test"])


def card_html(p: dict, lead: bool = False) -> str:
    slug, colour = DOMAINS.get(p["domain"], DOMAINS["Data science"])
    chips = "".join(f"<span>{html.escape(s)}</span>" for s in p["stack"])
    meta = [x for x in (p["language"], f"★ {p['stars']}" if p["stars"] else "", ago(p["updated"])) if x]
    meta_html = "".join(f"<span>{html.escape(m)}</span>" for m in meta)
    desc = p["description"]
    also = "".join(f'<span class="pc-also">· {html.escape(d)}</span>' for d in p["also"])
    show_desc = bool(desc) and not p["result"]  # curated result replaces the repo blurb
    return f"""
<div class="pc{' lead' if lead else ''}">
  <div class="pc-domain" style="color:{colour}"><i style="background:{colour}"></i>{html.escape(p['domain'])}{also}</div>
  <h3 class="pc-title">{html.escape(p['title'])}</h3>
  {f'<p class="pc-result">{html.escape(p["result"])}</p>' if p['result'] else ''}
  {f'<p class="pc-desc">{html.escape(desc)}</p>' if show_desc else ''}
  {f'<div class="pc-chips">{chips}</div>' if chips else ''}
  {f'<div class="pc-meta">{meta_html}</div>' if meta_html else ''}
</div>"""


def project_card(p: dict, lead: bool = False) -> None:
    slug, _ = DOMAINS.get(p["domain"], DOMAINS["Data science"])
    page = PAGES.get(p["page"])  # an in-app page named in projects.json, if any
    with st.container(key=f"card-{slug}-{p['name']}"):
        st.markdown(card_html(p, lead), unsafe_allow_html=True)
        n = 2 + bool(page) + bool(p["homepage"])
        widths = [1] * n + ([1.4] if lead else [])
        cols = iter(st.columns(widths, gap="small"))
        if next(cols).button("Read the write-up", key=f"read-{p['name']}", type="primary", width="stretch"):
            open_writeup(p)
        if page and next(cols).button(p["page_label"] or page.title, key=f"page-{p['name']}", width="stretch"):
            st.switch_page(page)
        if p["homepage"]:
            next(cols).link_button("Open the live app", p["homepage"], width="stretch")
        next(cols).link_button("View code", p["url"], width="stretch")


# (key, where it runs, title, what you can do, what it shows, button label, in-app page key or URL)
DEMOS = [
    ("planner", "Runs here · solves in about a second", "Plan an empty-container network",
     "A demand forecast for 15 depots feeds a mixed-integer program that decides which empties to truck where. Change "
     "the costs or the forecast's accuracy and watch it re-plan.",
     "Forecasting into optimization, and what forecast accuracy is worth in dollars.",
     "Open the planner", "container-planner"),
    ("lab", "Databricks project · frozen snapshot", "Retrain a crowd forecast",
     "Tune the production LightGBM model, backtest it on years it never saw, and test it against the champion with a "
     "block bootstrap, the same gate the weekly Databricks job uses.",
     "Champion/challenger promotion and out-of-time validation.",
     "Open the model lab", "https://park-crowd-forecast.streamlit.app/"),
    ("fleet", "Live on Databricks · 50 questions a day", "Ask 709 jet engines a question",
     "Plain-English questions go to a Databricks Genie space that writes SQL against governed Unity Catalog metric "
     "views of engine reliability. Allow a minute on the first question while the warehouse starts.",
     "Semantic layers, text-to-SQL with guardrails, a public app on a budget.",
     "Open Ask the Fleet", "https://ask-the-fleet.streamlit.app"),
    ("agent", "Runs here · replays recorded runs", "Step through an AI agent's tests",
     "Thirty graded runs of an agent that routes questions to specialists, calls an optimizer, and has every number "
     "checked against its tools. Then try to get past its guardrails.",
     "Tool orchestration, failure handling, guardrails and evaluation.",
     "See the test runs", "agent-runs"),
]


def demos_section() -> None:
    st.markdown('<div id="demos"></div><div class="section-head"><h2>Try it</h2>'
                "<p>Four working demos. No sign-in, and nothing you click costs anyone money.</p></div>",
                unsafe_allow_html=True)
    for row in (DEMOS[:2], DEMOS[2:]):
        cols = st.columns(len(row), gap="medium")
        for col, (key, where, title, what, shows, label, target) in zip(cols, row):
            with col, st.container(key=f"demo-{key}"):
                st.markdown(f'<div class="demo"><p class="demo-where">{html.escape(where)}</p>'
                            f'<h3 class="demo-title">{html.escape(title)}</h3><p class="demo-what">{html.escape(what)}</p>'
                            f'<p class="demo-for">Shows: {html.escape(shows)}</p></div>', unsafe_allow_html=True)
                if target in PAGES:
                    # a key starting "demo-" would pick up the tile styling
                    if st.button(label, key=f"open-demo-{key}", type="primary", width="stretch"):
                        st.switch_page(PAGES[target])
                else:
                    st.link_button(label, target, type="primary", width="stretch")


def projects_section() -> None:
    st.markdown('<div id="projects"></div>', unsafe_allow_html=True)
    projects, live = build_projects()
    st.markdown(
        f"""<div class="section-head"><h2>Projects</h2>
<p>{len(projects)} end-to-end builds, each with the data, the model and the decision it supports. Open one to read the full write-up.</p></div>""",
        unsafe_allow_html=True,
    )
    if not live:
        st.markdown('<p class="note">Live details from GitHub are unavailable right now, so this is the saved project list.</p>',
                    unsafe_allow_html=True)

    domains_present = [d for d in DOMAINS if any(d == p["domain"] or d in p["also"] for p in projects)]
    f1, f2, f3 = st.columns([1.0, 3.0, 0.9], gap="medium", vertical_alignment="bottom")
    query = f1.text_input("Search", placeholder="Try RAG or Snowflake")
    picked = f2.pills("Domain", domains_present, selection_mode="multi", default=None)
    sort = f3.selectbox("Sort by", ["Featured", "Recently updated", "Most stars"])

    shown = projects
    if query:
        q = query.lower()
        shown = [p for p in shown if q in " ".join(
            [p["title"], p["name"], p["result"], p["description"], p["language"], p["domain"], *p["also"], *p["stack"]]).lower()]
    if picked:
        shown = [p for p in shown if {p["domain"], *p["also"]} & set(picked)]

    if sort == "Featured":
        shown = sorted(shown, key=lambda p: (p["order"], -(dt.datetime.fromisoformat(
            p["updated"].replace("Z", "+00:00")).timestamp() if p["updated"] else 0)))
    elif sort == "Recently updated":
        shown = sorted(shown, key=lambda p: p["updated"] or "", reverse=True)
    else:
        shown = sorted(shown, key=lambda p: p["stars"], reverse=True)

    if not shown:
        st.markdown('<div class="empty">No projects match that search. Clear the search box or pick another domain.</div>',
                    unsafe_allow_html=True)
        return

    st.write("")
    rest = shown
    if sort == "Featured" and not query and not picked:
        n_lead = load_curation().get("lead_count", 1)
        for p in shown[:n_lead]:
            project_card(p, lead=True)
            st.write("")
        rest = shown[n_lead:]

    for i in range(0, len(rest), 2):
        cols = st.columns(2, gap="medium")
        for col, p in zip(cols, rest[i:i + 2]):
            with col:
                project_card(p)


def experience_section() -> None:
    items = "".join(
        f"""<div class="tl-item"><div class="tl-when">{html.escape(w)}</div>
<div class="tl-org">{html.escape(o)}</div><div class="tl-role">{html.escape(r)}</div>
<p>{html.escape(d)}</p></div>"""
        for w, o, r, d in EXPERIENCE
    )
    st.markdown(
        f"""<div class="section-head"><h2>Experience</h2>
<p>Production models in finance, a utility and industrial diagnostics, measured in revenue, accuracy and hours saved.</p></div>
<div class="timeline">{items}</div>""",
        unsafe_allow_html=True,
    )


def toolkit_section() -> None:
    rows = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>" for k, v in TOOLKIT)
    st.markdown(
        f"""<div class="section-head"><h2>Toolkit</h2></div><dl class="toolkit">{rows}</dl>""",
        unsafe_allow_html=True,
    )


def footer() -> None:
    contact = f'<a href="{LINKEDIN}" target="_blank" rel="noopener">message me on LinkedIn</a>'
    if EMAIL:
        contact += f' or email <a href="mailto:{EMAIL}">{html.escape(EMAIL)}</a>'
    st.markdown(
        f"""<div class="foot">
<div><h2>Hiring for data science?</h2><p>The fastest way to reach me is to {contact}.</p></div>
<p class="small">Projects come straight from <a href="https://github.com/{GITHUB_USER}" target="_blank" rel="noopener">GitHub</a>.</p>
</div>""",
        unsafe_allow_html=True,
    )


def home_page() -> None:
    hero()
    demos_section()
    projects_section()
    experience_section()
    toolkit_section()
    footer()


# ---------------------------------------------------------------------------
# Pages: the home page, plus project pages opened from their cards (no nav bar)
# ---------------------------------------------------------------------------
HOME = st.Page(home_page, title=f"{NAME}, data science projects", default=True)
PAGES = {  # keys are the "page" values in projects.json
    "power-test": st.Page(HERE / "app_pages" / "power_test.py", title="How many questions does a fair test need?",
                          url_path="power-test"),
    "agent-runs": st.Page(HERE / "app_pages" / "agent_runs.py", title="How the park agent was tested",
                          url_path="agent-runs"),
    "container-planner": st.Page(HERE / "app_pages" / "container_planner.py",
                                 title="Where should the empty containers go?", url_path="container-planner"),
}
current = st.navigation([HOME, *PAGES.values()], position="hidden")
if current.url_path != HOME.url_path:
    st.page_link(HOME, label="Back to projects", icon=":material/arrow_back:")
current.run()
