"""Wake the portfolio and every live demo it links to, and fail if one doesn't load.

Streamlit Community Cloud puts an app to sleep after about 12 hours without a visitor, and the next
visitor gets a "Yes, get this app back up!" page instead of the demo. The keep-awake workflow runs
this every few hours: it opens each app in a headless browser, clicks the wake button if the app is
asleep, and waits for the app itself to draw. An app that never loads, or shows a Python exception,
fails the run, so GitHub's failed-workflow email doubles as an uptime alert.

The apps are the portfolio plus every streamlit.app homepage in projects.json, so a new live demo is
covered as soon as its card links it.

    pip install playwright && python -m playwright install chromium
    python scripts/wake_apps.py
"""
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PORTFOLIO = "https://daniel-livingston.streamlit.app/"
LOAD_LIMIT = 300  # seconds for one app to wake and draw; a cold start with a big install can take minutes
WAKE_BUTTON = re.compile(r"get this app back up", re.IGNORECASE)


def app_urls() -> list[str]:
    curation = json.loads((Path(__file__).resolve().parent.parent / "projects.json").read_text(encoding="utf-8"))
    homepages = {p.get("homepage", "") for p in curation["projects"].values()}
    return [PORTFOLIO] + sorted(h for h in homepages if ".streamlit.app" in h)


def visit(page, url: str) -> tuple[bool, str]:
    """(ok, what happened). The app runs in an iframe on the streamlit.app page; the wake button doesn't."""
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    woke, start = False, time.time()
    while time.time() - start < LOAD_LIMIT:
        button = page.get_by_role("button", name=WAKE_BUTTON)
        if not woke and button.count():
            button.first.click()
            woke = True
        for frame in page.frames:
            try:
                drawn = frame.query_selector('[data-testid="stMainBlockContainer"]')
                running = frame.query_selector('[data-testid="stStatusWidget"]')
                error = frame.query_selector('[data-testid="stException"]')
            except Exception:  # the frame navigated while we looked
                continue
            if error:
                return False, f"shows an exception: {error.inner_text()[:300]!r}"
            if drawn and not running:
                return True, f"{'woken and ' if woke else ''}loaded in {time.time() - start:.0f} s"
        page.wait_for_timeout(3_000)
    return False, f"{'woken but ' if woke else ''}not drawn after {LOAD_LIMIT} s"


def main() -> int:
    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for url in app_urls():
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            try:
                ok, what = visit(page, url)
            except Exception as e:  # a network error is a failed check, not a crash of the whole run
                ok, what = False, f"error: {e}"
            page.close()
            failures += not ok
            print(f"{'ok  ' if ok else 'FAIL'} {url}: {what}", flush=True)
        browser.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
