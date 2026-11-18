"""How the jet-engine fleet system fits together, and the changes I'd make next.

A page of the portfolio app (url /fleet-architecture), opened from the architecture section at the top of the
home page and from the Predictive Maintenance card. It describes livingdw67/cmapss-predictive-maintenance as of
commit b2bc04c (6 Nov 2026); code links are pinned to that commit so their line numbers stay right. The two
diagrams are SVG files in assets/, drawn by diagrams.py. Nothing here calls Snowflake or Databricks.
"""
import streamlit as st

from diagrams import FLEET_DEMO_PATH, FLEET_SYSTEM, diagram

REPO = "https://github.com/livingdw67/cmapss-predictive-maintenance"
AT = f"{REPO}/blob/b2bc04c727fd3300fe403df64cbf9abcd1e47258"
APP = "https://ask-the-fleet.streamlit.app"
TOUR = "https://claude.ai/artifact/Ai1U6EospZRsTgpSU9TxBL#tour"


def code(path: str, line: str = "", label: str = "") -> str:
    """Link to a file (and line) at the pinned commit."""
    anchor = f"#L{line.replace('–', '-L')}" if line else ""
    text = label or (f"{path.rsplit('/', 1)[-1]}:{line}" if line else path.rsplit("/", 1)[-1])
    return f'<a href="{AT}/{path}{anchor}" target="_blank" rel="noopener">{text}</a>'


st.markdown("""<style>
.fa-tbl { overflow-x: auto; border: 1px solid var(--border); border-radius: 10px; margin: .25rem 0 .5rem 0; }
.fa-tbl table { border-collapse: collapse; width: 100%; min-width: 720px; font-size: .93rem; margin: 0; }
.fa-tbl th, .fa-tbl td { text-align: left; vertical-align: top; padding: .65rem .9rem; border: none;
  border-bottom: 1px solid var(--line); }
.fa-tbl tr:last-child th, .fa-tbl tr:last-child td { border-bottom: none; }
.fa-tbl thead th { font-size: .74rem; letter-spacing: .08em; text-transform: uppercase; color: var(--faint);
  font-weight: 600; background: var(--surface); }
.fa-tbl tbody th { font-weight: 600; color: var(--ink); white-space: nowrap; }
.fa-tbl td { color: var(--muted); }
.fa-tbl td.live { color: var(--ink); }
.fa-defend { display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 1rem 1.25rem; }
.fa-defend div { border-top: 2px solid var(--teal); padding-top: .6rem; }
.fa-defend .h { font-weight: 600; color: var(--ink); margin: 0 0 .2rem 0; }
.fa-defend .b { color: var(--muted); font-size: .93rem; margin: 0; }
.fa-imp { background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
  padding: 1rem 1.25rem; margin: 0 0 .9rem 0; }
.fa-imp-head { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem .75rem; margin-bottom: .7rem; }
.fa-num { flex: none; width: 28px; height: 28px; border-radius: 50%; background: #e5736b; color: var(--paper);
  font-weight: 700; font-size: .9rem; display: inline-flex; align-items: center; justify-content: center; }
.fa-imp-title { flex: 1 1 18rem; font-weight: 600; font-size: 1.08rem; color: var(--ink); margin: 0; }
.fa-tag { font-size: .74rem; font-weight: 600; padding: .15rem .6rem; border-radius: 999px;
  border: 1px solid var(--border); color: var(--muted); white-space: nowrap; }
.fa-imp dl { display: grid; grid-template-columns: 5rem 1fr; gap: .45rem 1rem; margin: 0; }
.fa-imp dt { color: var(--faint); font-size: .76rem; font-weight: 600; letter-spacing: .06em;
  text-transform: uppercase; padding-top: .2rem; }
.fa-imp dd { margin: 0; color: var(--muted); }
.fa-imp dd.why { color: var(--ink); border-left: 3px solid var(--teal); padding-left: .75rem; }
.fa-imp code, .fa-tbl code { font-size: .85em; }
@media (max-width: 640px) {
  .fa-imp dl { grid-template-columns: 1fr; gap: .1rem; }
  .fa-imp dd { margin-bottom: .5rem; }
}
</style>""", unsafe_allow_html=True)

st.title("How the jet-engine fleet system fits together")
st.caption(
    "NASA's C-MAPSS data: 709 jet engines run to failure, built as a governed data product with two kinds of "
    "consumer. People and AI agents ask questions of one set of metric definitions, and two models decide which "
    "engine to pull. It was built on Snowflake and rebuilt on Databricks, where the live demo runs, and the pipeline "
    "also exists as a Kedro project. Below are how it fits together, the choices behind it, and eight changes I'd "
    "make next."
)

st.markdown(diagram(FLEET_SYSTEM), unsafe_allow_html=True)
st.caption(
    "The semantic path and the ML path share the same layers but nothing else. Amber boxes are the checks that run "
    "today. Each coral number is one of the changes listed further down."
)

st.subheader("The live demo, request by request")
st.markdown(diagram(FLEET_DEMO_PATH), unsafe_allow_html=True)
st.caption(
    "Only the Ask tab spends compute. The question log caps use at 50 questions a day, and Genie's SQL runs under an "
    "identity that can read two metric views and nothing beneath them. The report and Modeling tabs read files "
    "bundled with the app, so they stay up when the Databricks Free Edition daily quota runs out."
)
st.link_button("Ask the fleet a question", APP, type="primary")

st.subheader("One pipeline, three builds")
st.caption("The same layers and models exist three times. The design moved between platforms, and the checks moved with it.")
ROWS = [
    ("Orchestration", "Numbered scripts 02–17, run in order",
     "Asset Bundle job: ingest → transform → semantic layer, and train → score. Weekly schedule, paused",
     "<code>kedro run</code>: data_processing, training, scoring"),
    ("Transform", "SQL per layer", "Spark SQL into Delta tables; the feature table is keyed on engine and cycle",
     "pandas nodes, datasets declared in the catalog"),
    ("Training", "Snowpark notebook", "MLflow parent run, one nested run per class-imbalance strategy",
     "One <code>train_classifier</code> template, namespaced per horizon"),
    ("Registry", "Snowflake Model Registry",
     "Unity Catalog with a <code>@champion</code> alias; each model carries its own threshold",
     "<code>pipeline_ml_factory</code>: the scoring pipeline and both models as one MLflow model"),
    ("Semantic layer", "Semantic view <code>FLEET_RELIABILITY</code>",
     "Metric views <code>fleet_engines</code> and <code>fleet_cycles</code>", "None"),
    ("Plain English", "Cortex Analyst and a Snowflake-managed MCP server", "Genie space", "None"),
    ("Checks", "80 of 80 metrics reconciled; 594 of 600 on the 200-question eval",
     "The job fails unless 7 of 7 key metrics match SQL; Genie 6 of 6; recall 0.952 and 0.912 on 707 test engines",
     "10 unit tests; recall 0.930 and 0.912 on 707 test engines"),
]
body = "".join(f'<tr><th scope="row">{a}</th><td>{b}</td><td class="live">{c}</td><td>{d}</td></tr>' for a, b, c, d in ROWS)
st.markdown(
    '<div class="fa-tbl"><table><thead><tr><th scope="col"></th><th scope="col">Snowflake (original)</th>'
    '<th scope="col">Databricks (runs the live demo)</th><th scope="col">Kedro (runs locally)</th></tr></thead>'
    f"<tbody>{body}</tbody></table></div>",
    unsafe_allow_html=True,
)

st.subheader("Design choices behind it")
CHOICES = [
    ("Metrics split by grain", "Engine metrics and cycle metrics live in separate views, so an engine count can't fan "
                               "out to telemetry rows and long-lived engines don't get extra weight."),
    ("Ground truth from below the layer", "The reconciliation and the 200-question eval compute their answers from the "
                                          "staging tables, so the semantic layer is never graded against itself."),
    ("The threshold travels with the model", "Each registered model applies its own validation-tuned threshold, so a "
                                             "retrain can't leave a stale cutoff in the scoring code."),
    ("Test engines never choose anything", "Strategies and thresholds are picked on validation engines. Test results "
                                           "are logged but never used for selection."),
    ("Least privilege for the public", "The demo's identity can read two metric views and write one log table, so a "
                                       "question can't change data."),
    ("Built for its own outages", "Both outages so far came from cost limits. The report now runs from a snapshot, and "
                                  "page loads no longer wake the warehouse."),
]
st.markdown('<div class="fa-defend">' + "".join(f'<div><p class="h">{h}</p><p class="b">{b}</p></div>' for h, b in CHOICES)
            + "</div>", unsafe_allow_html=True)

st.subheader("What I'd change next")
st.caption("Numbered to match the markers on the first diagram, roughly in the order I'd do them.")
CHANGES = [
    ("Evaluate Genie the way I evaluated Cortex", "Evaluation",
     "Cortex Analyst scored 594 of 600 on 200 questions whose answers were computed from the staging tables "
     f"({code('cortex_analyst_eval_200/README.md', label='the eval')}). The Genie space behind the live demo has been "
     "checked on its 6 sample questions.",
     "Run the same 200 questions against Genie, 3 times each, and compare the two engines with a paired McNemar test. "
     "The ground truth is already stored and doesn't depend on the platform.",
     "A port isn't finished until it passes the eval the original passed."),
    ("Make a new model earn the champion alias", "MLOps",
     f"Every training run moves <code>@champion</code> to the new version "
     f"({code('databricks/src/03_train_register.py', '176')}). A retrain on bad data would replace a good model "
     "without a check.",
     "Register new versions as <code>@challenger</code>, score both on the same frozen engines, and promote only if a "
     "paired bootstrap shows the challenger is better at the agreed precision. My crowd-forecast project already "
     "works this way.",
     "Today every retrain wins by default. It should have to win on evidence."),
    ("Move the study's better inputs into the pipeline", "Features",
     f"The pipelines train on the original 8 features ({code('databricks/src/03_train_register.py', '44')}), which "
     "scored 0.857 F2. XGBoost on 14 sensors, normalized within each operating condition over 30 cycles, reached "
     f"0.931 F2 in the graph neural network study ({code('gnn/data.py', '71')}), which so far lives only in the "
     "research code.",
     "Add the per-condition scaling (fit on training engines only) and the 30-cycle windows to the feature table, "
     "retrain, and let change 2 decide whether the new model replaces the champion.",
     "The study showed the gain came from better inputs, not from the graph. That finding belongs in the feature store."),
    ("Let agents read the layer, not the tables under it", "Governance",
     "On Snowflake, the MCP server's role can select from every table in CORE and MARTS "
     f"({code('15_create_mcp_server.py', '58–61')}), so an agent's <code>run_sql</code> could skip the semantic view "
     "and compute its own MTTF. It can't write, but it isn't held to the governed definitions.",
     "Match the Databricks build, where the service principal can read the two metric views and nothing else. Test "
     "whether the semantic view answers under view-only grants; if it doesn't, replace <code>run_sql</code> with a "
     "tool that only accepts queries against the view.",
     "Read-only isn't the same as governed."),
    ("Write each metric once and generate both platforms", "Semantic layer",
     f"The metrics are written twice, as Snowflake YAML in {code('11_build_semantic_view.py')} and as metric-view YAML "
     f"in {code('databricks/src/05_semantic_layer.py')}. The AI instructions are copied again into "
     f"{code('databricks/setup_public_demo.py', '35')}, so one instruction fix had to go into two files.",
     "Keep one versioned spec in the repo (name, expression, grain, synonyms, instructions) that generates both, plus "
     "a check that both platforms return the same number for every metric. Changing a definition becomes a reviewed "
     "pull request with its eval result attached.",
     "Definitions live in git, are compiled to each engine and are tested on every change."),
    ("Keep score history, enforce schemas, watch for drift", "Data quality",
     "Tables are rebuilt with <code>CREATE OR REPLACE</code> or overwritten with <code>overwriteSchema</code> "
     f"({code('databricks/src/01_ingest.py', '53')}, {code('databricks/src/04_batch_score.py', '64')}), so a changed "
     "column passes silently and the risk-score table keeps only the latest run. Nothing watches feature or score drift.",
     "Append scores by scoring time and model version (both columns already exist). Add expectations at ingest and "
     "staging (row counts, sensor ranges, no duplicate engine-cycle rows) that fail the job. Drop "
     "<code>overwriteSchema</code>, so a schema change needs a deliberate migration. Check features and scores for "
     "drift over that history.",
     "Every alert should trace back to the model version that raised it, and drift should show up before accuracy drops."),
    ("Run the checks on every change", "CI",
     "The repo has no CI workflow. The unit tests, the reconciliation and both evals run by hand.",
     "On every pull request, run the Kedro tests and <code>databricks bundle validate</code>. When a metric definition "
     "changes, run the reconciliation plus the original 25 eval questions as a gate, and the full 200 nightly or on "
     "demand. The GNN tests need PyTorch Geometric, so they get their own job.",
     "The eval is the semantic layer's regression test. A definition change that lowers accuracy shouldn't merge."),
    ("Turn alerts into a plan with costs and capacity", "Decisions",
     "Thresholds maximize F2, a stand-in for “a missed failure costs more than a false alarm.” The decision matrix "
     "maps alerts to actions but ignores capacity: 135 of the 707 test engines land in “immediate action” at once.",
     "Set thresholds from the real cost of a missed failure against an early removal, then add a mixed-integer program "
     "that schedules removals within hangar and technician capacity, like the container planner on this site.",
     "A probability isn't a decision. The output should be a removal schedule."),
]
for i, (title, tag, now, change, why) in enumerate(CHANGES, 1):
    st.markdown(
        f'<div class="fa-imp" id="change-{i}"><div class="fa-imp-head"><span class="fa-num">{i}</span>'
        f'<p class="fa-imp-title">{title}</p><span class="fa-tag">{tag}</span></div>'
        f"<dl><dt>Now</dt><dd>{now}</dd><dt>Change</dt><dd>{change}</dd>"
        f'<dt>Why</dt><dd class="why">{why}</dd></dl></div>',
        unsafe_allow_html=True,
    )

st.markdown(
    "**A bigger redesign.** One survival model (XGBoost with an accelerated-failure-time objective, or a Weibull model "
    "with sensor covariates) would give the probability of failure within any horizon. The two classifiers could then "
    "never disagree, which removes the “anomaly, investigate” case, and the fleet-level Weibull analysis and the "
    "per-engine model would use the same math."
)

st.caption(
    f"Code: [the repo]({REPO}) · [its README]({REPO}#readme) · "
    f"[guided tour of the semantic layer]({TOUR}). Described as of commit b2bc04c, 6 Nov 2026."
)
