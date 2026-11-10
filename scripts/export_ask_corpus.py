"""Write ask_corpus.json: the only text the "Ask about my work" page can quote.

Sources are what the site already shows (intro, principles, Experience, Toolkit, project
cards) plus the READMEs of the featured repos. A repo that GitHub reports as private stops
the export, so private work can't reach a public page by accident. The resume file is
deliberately not a source.

    python scripts/export_ask_corpus.py
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "ask_corpus.json"
USER = "livingdw67"
SITE = "https://daniel-livingston.streamlit.app"
MAX_WORDS = 130
SKIP_SECTION = re.compile(
    r"\b(run it|how to run|running|setup|set up|install\w*|getting started|prerequisites|quick ?start|reproduc\w*|"
    r"project structure|repo\w* (structure|layout|map)|structure|layout|license|acknowledg\w*|contributing|"
    r"table of contents|contents|environment variables|deploy\w*|api|commands?|tech(nology)? stack)\b",
    re.I,
)


def site_constants() -> dict:
    """Read the literal settings from streamlit_app.py so the two can never drift apart."""
    wanted = {"INTRO", "PRINCIPLES", "EXPERIENCE", "TOOLKIT"}
    found = {}
    for node in ast.parse((ROOT / "streamlit_app.py").read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in wanted:
            found[node.targets[0].id] = ast.literal_eval(node.value)
    missing = wanted - found.keys()
    if missing:
        sys.exit(f"streamlit_app.py no longer defines {sorted(missing)}")
    return found


def github(path: str, raw: bool = False) -> requests.Response:
    headers = {"Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(f"https://api.github.com{path}", headers=headers, timeout=30)
    response.raise_for_status()
    return response


def clean_markdown(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"<picture>.*?</picture>", " ", text, flags=re.S | re.I)
    text = re.sub(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)", " ", text)   # linked images and badges
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)                # images
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)             # links keep their words
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.M)                 # blockquote markers
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"\1", text)  # *emphasis*
    return text.replace("**", "").replace("`", "").replace("&nbsp;", " ")


def table_row(line: str) -> str:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return "; ".join(cell for cell in cells if cell) + "."


def sections_of(markdown: str) -> list[tuple[str, str]]:
    """Split a README on its headings and flatten each section to prose lines."""
    sections, heading, lines = [], "Overview", []
    for line in clean_markdown(markdown).splitlines():
        match = re.match(r"^#{1,6}\s+(.*)", line)
        if match:
            if lines:
                sections.append((heading, lines))
            heading, lines = match.group(1).strip(), []
        elif re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", line) and "-" in line:
            continue  # the divider under a table header
        elif line.strip().startswith("|"):
            lines.append(table_row(line))
        elif line.strip():
            lines.append(re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", line).strip())
    if lines:
        sections.append((heading, lines))
    return [(name, body) for name, body in sections if not SKIP_SECTION.search(name)]


def passages_from(body: list[str]) -> list[str]:
    """Group lines into passages of about MAX_WORDS, never splitting a line."""
    passages, current, words = [], [], 0
    for line in body:
        size = len(line.split())
        if current and words + size > MAX_WORDS:
            passages.append(" ".join(current))
            current, words = [], 0
        current.append(line)
        words += size
    if current:
        passages.append(" ".join(current))
    return passages


def main() -> None:
    constants = site_constants()
    curated = json.loads((ROOT / "projects.json").read_text(encoding="utf-8"))
    passages: list[dict] = []

    def site(key: str, kind: str, source: str, section: str, text: str) -> None:
        passages.append({"key": key, "kind": kind, "source": source, "section": section, "text": text, "url": SITE})

    site("site-intro", "about", "About Daniel", "Introduction", constants["INTRO"])
    for name, text in constants["PRINCIPLES"]:
        site("site-principles", "about", "How Daniel works", name, f"{name}. {text}")
    for when, organisation, role, what in constants["EXPERIENCE"]:
        key = "exp-" + re.sub(r"[^a-z]+", "-", organisation.lower()).strip("-")
        site(key, "experience", organisation, f"{role}, {when}", what)
    for name, text in constants["TOOLKIT"]:
        kind = "credentials" if name == "Credentials" else "toolkit"
        site("site-toolkit", kind, "Toolkit", name, f"{name}: {text}.")

    for repo in curated["featured_order"]:
        details = github(f"/repos/{USER}/{repo}").json()
        if details.get("private") or details.get("visibility") != "public":
            sys.exit(f"{repo} is not public; refusing to put it on a public page")
        card = curated["projects"].get(repo, {})
        title = card.get("title", repo)
        url = details["html_url"]
        stack = ", ".join(card.get("stack", []))
        summary = card.get("result", "")
        passages.append({"key": repo, "kind": "project", "source": title, "section": "Summary",
                         "text": f"{summary} Built with {stack}." if stack else summary, "url": url})
        for name, body in sections_of(github(f"/repos/{USER}/{repo}/readme", raw=True).text):
            for text in passages_from(body):
                if len(text.split()) >= 12:
                    passages.append({"key": repo, "kind": "project", "source": title, "section": name,
                                     "text": text, "url": url})

    payload = json.dumps({"passages": passages}, ensure_ascii=False, indent=1) + "\n"
    OUTPUT.write_bytes(payload.encode("utf-8"))   # bytes, so Windows doesn't rewrite line endings
    counts: dict[str, int] = {}
    for passage in passages:
        counts[passage["key"]] = counts.get(passage["key"], 0) + 1
    print(f"{len(passages)} passages, {OUTPUT.stat().st_size // 1024} KB")
    for key, count in sorted(counts.items(), key=lambda item: -item[1]):
        print(f"{count:4d}  {key}")


if __name__ == "__main__":
    main()
