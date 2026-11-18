"""SVG diagrams from assets/, shown as images so they keep their own styles inside Streamlit.

Used by the architecture section at the top of the home page and by app_pages/fleet_architecture.py.
Each SVG carries its colours and fonts in its own <style> block. On narrow screens the figure scrolls
sideways instead of shrinking its labels past reading size.
"""
import base64
import html
from functools import cache
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"

FLEET_SYSTEM = (
    "fleet_system.svg",
    "NASA C-MAPSS engine data flows through raw, staging, core, marts and a feature store. Core and marts feed one set "
    "of governed metric definitions that serves a fleet report, a plain-English question box and an MCP server for "
    "agents, checked by a reconciliation and an answer eval. The feature store feeds two XGBoost classifiers, a model "
    "registry, batch scoring and a maintenance action. Numbers 1 to 8 mark the changes I'd make next.",
)
FLEET_DEMO_PATH = (
    "fleet_demo_path.svg",
    "A visitor opens the Ask the Fleet app. The Ask tab checks the question log, then sends the question to a Genie "
    "space, which runs SQL on a serverless warehouse as a service principal that can only read two metric views and "
    "write the question log. The Report and Modeling tabs read files bundled with the app and use no compute.",
)


@cache
def _data_uri(name: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode((ASSETS / name).read_bytes()).decode()


def diagram(spec: tuple[str, str], min_width: int = 860) -> str:
    """HTML for one diagram: the SVG as an image in a bordered frame that scrolls sideways when narrow."""
    name, alt = spec
    return (f'<div class="arch-fig"><img src="{_data_uri(name)}" alt="{html.escape(alt)}" '
            f'style="min-width:{min_width}px"></div>')
