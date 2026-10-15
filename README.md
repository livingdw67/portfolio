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

Free apps go to sleep when nobody has visited for a while; the next visitor clicks a button to wake it and waits a moment.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Personalise

Name, role, credentials, intro, principles, experience, toolkit and contact links live at the top of `streamlit_app.py`. Colours and fonts follow the personal brand guide (`Branding/brand-guide.md`): the Streamlit theme is in `.streamlit/config.toml`, and the page's own styles use the CSS variables in the `:root` block below the settings.
