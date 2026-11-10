# Daniel Livingston: Data Science Portfolio

A free, self-updating portfolio site built with Streamlit. Every repository I own and have starred on GitHub appears here automatically, with its README one click away.

## How it works

- The app asks the GitHub API for the repos starred by `livingdw67` and keeps only the ones I own. It checks once a day; change `REFRESH` at the top of `streamlit_app.py` to check more or less often.
- `projects.json` adds the curated layer: a readable title, a domain, the headline result, the stack, and the order of the featured list. Repos without an entry still show up, titled from the repo name and tagged by keywords.
- "Read the write-up" opens the repo's README inside the app, with relative images and links fixed so they render. READMEs are also cached for a day.
- If GitHub is unreachable or rate-limited, the app keeps showing the last list it got and tries again after 15 minutes. If it has never reached GitHub since starting, it shows the curated list, so the page never breaks.

## Add or feature a project

1. Star the repo on GitHub. It appears within a day, or straight away if you reboot the app from the Streamlit Community Cloud dashboard.
2. Optionally add an entry to `projects.json` keyed by the repo name (`title`, `domain`, `also`, `result`, `stack`, and `homepage` for a live demo link). `also` lists extra domains: they show after the main one on the card and count for the domain filter, while the card keeps the main domain's colour.
3. Add the name to `featured_order` to control its position. The first `lead_count` names (2 by default here) get large lead cards.

### Project pages

A project can also have its own page inside the app, opened by a button on its card. The pages are in `app_pages/` and are registered in `PAGES` at the bottom of `streamlit_app.py`. Navigation is hidden, so the home page looks the same, and each page gets a "Back to projects" link. To link a page from a card, set `page` (the key in `PAGES`) and `page_label` (the button text) in the project's `projects.json` entry.

- `power-test` (`app_pages/power_test.py`): how many questions a fair Segment Assistant vs Cortex Analyst test needs, and what each round found. Its data, `power_test_rounds.json`, is a copy of `practice_eval/power_app/rounds.json` in the snowpark-customer-segmentation repo.
- `agent-runs` (`app_pages/agent_runs.py`): the park agent's 30 graded test runs, replayed from saved results, plus its input screen and number check to try. Its data, `agent_runs.json`, is written by `python scripts/export_agent_runs.py <path to park-crowd-forecast>`; rerun it after a new eval run.
- `container-planner` (`app_pages/container_planner.py`): an illustrative empty-container repositioning plan. A demand forecast for 15 depots feeds a mixed-integer program (HiGHS through SciPy) that is solved in the app on every click.
- `ask` (`app_pages/ask.py`): "Ask about my work". A visitor picks one of the questions in `TOPICS` (`ask_my_work.py`) and reads verbatim quotes from the featured READMEs and this site's own text, each pinned to its source. No model is called. Its data, `ask_corpus.json`, is written by `python scripts/export_ask_corpus.py`; rerun it after a featured README changes.

### Hero demo

Beside the headline, "Ask the Segment Assistant" (`segment_demo.py`) replays seven recorded, graded Segment Assistant answers, each with its route, plan, code's fixes to the plan, rows and figure check, and Cortex Analyst's answer to the same question. One follow-up shows the conversation state. Nothing calls a model. Its data, `segment_demo.json`, is written by `python scripts/export_segment_demo.py <path to snowpark-customer-segmentation>`; the questions are picked in that script.

### Demos strip

`DEMOS` in `streamlit_app.py` lists the five tiles under the hero ("Try it"). A tile's target is either a key in `PAGES`, which opens in the app, or a URL, which opens the live app.

Domains with their own colour: `Applied AI`, `Energy & industry`, `Finance`, `Customer analytics`. `Analytics engineering` is light slate. A repo with no curated domain, and no keyword match, shows as `Data science` (also slate).

## Deploy on Streamlit Community Cloud (free)

1. Push this folder to a public GitHub repo, for example `livingdw67/portfolio`.
2. Go to [share.streamlit.io](https://share.streamlit.io), choose **Create app**, pick the repo and branch, and set the main file to `streamlit_app.py`.
3. Under **App URL**, choose a custom subdomain such as `daniel-livingston` to get `daniel-livingston.streamlit.app`.
4. Optional but recommended: in the app's **Settings → Secrets**, add a GitHub token so the app never hits GitHub's anonymous rate limit:

   ```toml
   GITHUB_TOKEN = "github_pat_..."
   ```

   A fine-grained token with read-only access to public repositories is enough.

Free apps go to sleep after about 12 hours without a visitor, and the next visitor gets a wake-up page instead of the app. The **Keep the apps awake** workflow (`.github/workflows/keep-awake.yml`) runs `scripts/wake_apps.py` every 6 hours. It opens the portfolio and every `streamlit.app` homepage in `projects.json` in a headless browser, wakes any that are asleep, and fails if one doesn't load or shows an exception, so a failed-run email from GitHub means a demo is broken. Run it by hand from the Actions tab. GitHub pauses scheduled workflows in a repo with no commits for 60 days; turn it back on there if that happens.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Personalise

Name, role, credentials, intro, principles, experience, toolkit and contact links live at the top of `streamlit_app.py`. Colours and fonts follow the personal brand guide (`Branding/brand-guide.md`): the Streamlit theme is in `.streamlit/config.toml`, and the page's own styles use the CSS variables in the `:root` block below the settings.

## License

MIT ([LICENSE](LICENSE)).
