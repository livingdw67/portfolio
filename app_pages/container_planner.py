"""Where should the empty containers go? A demand forecast feeds a mixed-integer program that decides
which empties to truck between depots.

A page of the portfolio app, opened from the demos strip on the home page (url /container-planner).
The network is illustrative: real metro locations, synthetic volumes. HiGHS solves the program through
SciPy, so every click runs in the app and costs nothing.
"""
import math
from statistics import NormalDist

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

N = NormalDist()
INK, SUB, MUTED, GRID, SURFACE, CARD = "#f2f5f9", "#9fb1c7", "#6f86a3", "#2b3f58", "#0e1a2b", "#16283f"
TEAL, AMBER, CORAL, BLUE, SLATE = "#5fc4c0", "#f0a742", "#e5736b", "#7fa6d1", "#6f86a3"
US_STATES = "https://cdn.jsdelivr.net/npm/vega-datasets@v2.11.0/data/us-10m.json"

# Depot, latitude, longitude, forecast orders needing an empty this week (mean), empties on hand,
# empties freed by deliveries booked this week, yard space for empties at the end of the week.
# More moves end in the Sun Belt than start there, so empties pile up in the south and run short in the
# north and in Los Angeles.
DEPOTS = pd.DataFrame([
    ("Boston", 42.36, -71.06, 140, 20, 70, 160),
    ("New York", 40.71, -74.01, 260, 60, 140, 260),
    ("Philadelphia", 39.95, -75.17, 150, 30, 95, 170),
    ("Washington", 38.91, -77.04, 170, 35, 125, 180),
    ("Chicago", 41.88, -87.63, 220, 45, 120, 230),
    ("Charlotte", 35.23, -80.84, 120, 55, 150, 120),
    ("Nashville", 36.16, -86.78, 100, 45, 125, 100),
    ("Atlanta", 33.75, -84.39, 170, 60, 195, 150),
    ("Orlando", 28.54, -81.38, 130, 80, 190, 110),
    ("Tampa", 27.95, -82.46, 110, 70, 165, 100),
    ("Dallas", 32.78, -96.80, 190, 70, 225, 150),
    ("Houston", 29.76, -95.37, 170, 65, 205, 140),
    ("Phoenix", 33.45, -112.07, 120, 60, 165, 90),
    ("Denver", 39.74, -104.99, 110, 35, 90, 110),
    ("Los Angeles", 34.05, -118.24, 210, 40, 115, 220),
], columns=["depot", "lat", "lon", "demand", "on_hand", "returns", "yard"])
DEPOTS["available"] = DEPOTS["on_hand"] + DEPOTS["returns"]
ROAD_FACTOR = 1.2      # road miles per great-circle mile
MAX_MILES = 1_500      # longer repositioning runs aren't considered
DISPATCH = 250         # fixed cost of sending a truck: driver time, loading and unloading
OVERFLOW = 30          # renting outside space for an empty that doesn't fit the yard, per week
TANGENTS = np.linspace(-3.5, 3.5, 29)  # where the expected-cost curves are cut, in forecast errors


def road_miles(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return ROAD_FACTOR * 3958.8 * 2 * math.asin(math.sqrt(h))


ARCS = pd.DataFrame([(i, j, road_miles(a, b)) for i, a in DEPOTS.iterrows() for j, b in DEPOTS.iterrows()
                     if i != j and road_miles(a, b) <= MAX_MILES], columns=["i", "j", "miles"])


def loss(z):
    """Standard normal loss: E[max(0, Z - z)]."""
    return N.pdf(z) - z * (1 - N.cdf(z))


def expected_lost(stock, mu, sd):
    """Orders expected to go unfilled when `stock` empties meet Normal(mu, sd) demand."""
    return sd * loss((stock - mu) / sd)


def expected_overflow(stock, mu, sd, yard):
    """Empties expected to be left over beyond the yard's space at the end of the week."""
    return sd * loss((mu + yard - stock) / sd)


# ----------------------------------------------------------------------------- the program
@st.cache_data(show_spinner=False, max_entries=256)
def solve(cv, lost_cost, mile_cost, per_truck, use_uncertainty):
    """Moves that minimise trucking plus the cost of lost orders and yard overflow.

    With `use_uncertainty`, lost orders and overflow are their expected values under the forecast's
    error, a convex curve the program sees through tangent cuts. Without it, the program plans to the
    point forecast as if it were certain, the usual spreadsheet approach. Returns one row per move."""
    d, a = DEPOTS, ARCS
    nd, na = len(d), len(a)
    sd = (cv * d["demand"]).clip(lower=1.0).to_numpy()
    mu, avail, yard = d["demand"].to_numpy(float), d["available"].to_numpy(float), d["yard"].to_numpy(float)
    # variables: containers on each arc (x), trucks on each arc (y), lost orders (l), overflow (o)
    X, Y, L, O = 0, na, 2 * na, 2 * na + nd
    n = 2 * na + 2 * nd
    cost = np.zeros(n)
    cost[Y:Y + na] = DISPATCH + mile_cost * a["miles"].to_numpy()
    cost[L:L + nd], cost[O:O + nd] = lost_cost, OVERFLOW

    rows, cols, vals, lo, hi = [], [], [], [], []
    r = 0

    def add(entries, lower, upper):
        nonlocal r
        for c, v in entries:  # plain statements: Streamlit's magic would print a bare tuple of appends
            rows.append(r)
            cols.append(c)
            vals.append(v)
        lo.append(lower)
        hi.append(upper)
        r += 1

    for k in range(na):  # a truck carries at most `per_truck` empties
        add([(X + k, 1.0), (Y + k, -per_truck)], -np.inf, 0)
    out_arcs = [np.flatnonzero(a["i"].to_numpy() == i) for i in range(nd)]
    in_arcs = [np.flatnonzero(a["j"].to_numpy() == i) for i in range(nd)]
    for i in range(nd):  # a depot can't send more than it has
        add([(X + k, 1.0) for k in out_arcs[i]], -np.inf, avail[i])
    # stock_i = avail_i + inflow_i - outflow_i. Each cut says var_i >= value + slope * (stock_i - point).
    for i in range(nd):
        if use_uncertainty:
            lost_cuts = [(mu[i] + z * sd[i], expected_lost(mu[i] + z * sd[i], mu[i], sd[i]), -(1 - N.cdf(z))) for z in TANGENTS]
            over_cuts = [(mu[i] + yard[i] + z * sd[i], expected_overflow(mu[i] + yard[i] + z * sd[i], mu[i], sd[i], yard[i]),
                          N.cdf(z)) for z in TANGENTS]
        else:
            lost_cuts, over_cuts = [(mu[i], 0.0, -1.0)], [(mu[i] + yard[i], 0.0, 1.0)]
        for var, cuts in ((L + i, lost_cuts), (O + i, over_cuts)):
            for point, value, slope in cuts:
                flow = [(X + k, -slope) for k in in_arcs[i]] + [(X + k, slope) for k in out_arcs[i]]
                add([(var, 1.0)] + flow, value + slope * (avail[i] - point), np.inf)

    A = coo_matrix((vals, (rows, cols)), shape=(r, n)).tocsr()
    upper = np.concatenate([avail[a["i"]], np.ceil(avail[a["i"]] / per_truck), np.full(2 * nd, np.inf)])
    res = milp(cost, constraints=LinearConstraint(A, lo, hi), bounds=Bounds(np.zeros(n), upper),
               integrality=np.concatenate([np.ones(2 * na), np.zeros(2 * nd)]),
               options={"time_limit": 10, "mip_rel_gap": 1e-3})
    if res.x is None:
        raise RuntimeError(res.message)
    x, y = np.round(res.x[X:X + na]), np.round(res.x[Y:Y + na])
    moves = a.assign(containers=x, trucks=y)
    return moves[moves["containers"] > 0].reset_index(drop=True)


def evaluate(moves, cv, lost_cost, mile_cost):
    """Each depot's stock after the moves and the plan's exact expected costs under the forecast's error."""
    d = DEPOTS.copy()
    sd = (cv * d["demand"]).clip(lower=1.0)
    inflow = moves.groupby("j")["containers"].sum().reindex(d.index, fill_value=0)
    outflow = moves.groupby("i")["containers"].sum().reindex(d.index, fill_value=0)
    d["sent"], d["received"] = outflow, inflow
    d["stock"] = d["available"] + inflow - outflow
    d["lost"] = [expected_lost(s, m, e) for s, m, e in zip(d["stock"], d["demand"], sd)]
    d["overflow"] = [expected_overflow(s, m, e, y) for s, m, e, y in zip(d["stock"], d["demand"], sd, d["yard"])]
    d["fill"] = 1 - d["lost"] / d["demand"]
    trucking = float((moves["trucks"] * (DISPATCH + mile_cost * moves["miles"])).sum()) if len(moves) else 0.0
    costs = {"Trucking": trucking, "Lost orders": lost_cost * d["lost"].sum(), "Yard overflow": OVERFLOW * d["overflow"].sum()}
    return d, costs


NO_MOVES = pd.DataFrame(columns=["i", "j", "miles", "containers", "trucks"])
PLANS = {"Uses the forecast's error": True, "Plans to the point forecast": False, "Moves nothing": None}


def plan(name, cv, lost_cost, mile_cost, per_truck):
    flag = PLANS[name]
    return NO_MOVES if flag is None else solve(cv, lost_cost, mile_cost, per_truck, flag)


def rough(x):
    """Round dollars for prose about made-up volumes: $29k, $1.5M."""
    return f"\\${x / 1e6:,.1f}M" if abs(x) >= 1e6 else f"\\${x / 1e3:,.0f}k"


def money(x, md=False):
    """Dollars; md=True escapes the sign for markdown, where a pair of $ would start maths."""
    return ("\\$" if md else "$") + f"{x:,.0f}"


# ----------------------------------------------------------------------------- page
st.title("Where should the empty containers go?")
st.caption(
    "A moving-and-storage network has 15 depots. Customers keep moving south, so empties pile up in the Sun Belt "
    "and run short in the north. Each week a forecast says how many orders each depot will need an empty for, and a "
    "mixed-integer program decides which empties to truck where, trading trucking cost against lost orders and "
    "overflowing yards. Change the costs or the forecast's accuracy and it re-plans in about a second. The depots are "
    "real metros; the volumes are made up."
)

c1, c2, c3, c4 = st.columns(4, gap="medium")
lost_cost = c1.slider("Margin lost on an unfilled order", 200, 2000, 1000, 50, format="$%d",
                      help="A customer who can't get a container books elsewhere.")
mile_cost = c2.slider("Truck cost per mile", 1.5, 4.0, 2.0, 0.1, format="$%.2f",
                      help=f"Plus \\${DISPATCH} a dispatch for driver time and loading.")
per_truck = c3.slider("Empties per truck", 1, 8, 4, 1)
cv = c4.slider("Forecast error", 5, 40, 20, 5, format="%d%%",
               help="The forecast's typical error, as a share of the forecast (the coefficient of variation).") / 100

with st.spinner("Solving…"):
    results = {name: evaluate(plan(name, cv, lost_cost, mile_cost, per_truck), cv, lost_cost, mile_cost) for name in PLANS}
best_moves = plan("Uses the forecast's error", cv, lost_cost, mile_cost, per_truck)
best, best_costs = results["Uses the forecast's error"]
total = {name: sum(c.values()) for name, (_, c) in results.items()}

with st.container(horizontal=True):
    st.metric("Expected weekly cost", money(total["Uses the forecast's error"]), border=True,
              delta=f"{money(total['Moves nothing'] - total[next(iter(PLANS))])} less than moving nothing", delta_color="off",
              delta_arrow="off")
    st.metric("Empties moved", f"{int(best_moves['containers'].sum()):,}", border=True,
              help=f"On {int(best_moves['trucks'].sum())} trucks")
    st.metric("Orders filled", f"{1 - best['lost'].sum() / best['demand'].sum():.1%}", border=True,
              help="Expected, under the forecast's error")
    gap = total["Plans to the point forecast"] - total["Uses the forecast's error"]
    st.metric("Saved by using the forecast's error", money(gap), border=True,
              help="Against the same program planning to the point forecast as if it were certain")

# ----------------------------------------------------------------------------- map
before = DEPOTS["available"] - DEPOTS["demand"]
depots = best.assign(balance=before, position=np.where(before < 0, "Short before moves", "Spare before moves"),
                     fill_pct=best["fill"] * 100, label=DEPOTS["depot"])
lines = best_moves.assign(lat=DEPOTS.loc[best_moves["i"], "lat"].to_numpy(), lon=DEPOTS.loc[best_moves["i"], "lon"].to_numpy(),
                          lat2=DEPOTS.loc[best_moves["j"], "lat"].to_numpy(), lon2=DEPOTS.loc[best_moves["j"], "lon"].to_numpy(),
                          origin=DEPOTS.loc[best_moves["i"], "depot"].to_numpy(),
                          dest=DEPOTS.loc[best_moves["j"], "depot"].to_numpy())
proj = dict(type="albersUsa")
states = alt.Chart(alt.topo_feature(US_STATES, "states")).mark_geoshape(fill=CARD, stroke=GRID, strokeWidth=0.8).project(**proj)
routes = alt.Chart(lines).mark_rule(color=TEAL, opacity=0.85, strokeCap="round").encode(
    longitude="lon:Q", latitude="lat:Q", longitude2="lon2:Q", latitude2="lat2:Q",
    strokeWidth=alt.StrokeWidth("containers:Q", scale=alt.Scale(range=[1.5, 7]), legend=None),
    tooltip=[alt.Tooltip("origin:N", title="From"), alt.Tooltip("dest:N", title="To"),
             alt.Tooltip("containers:Q", title="Empties"), alt.Tooltip("trucks:Q", title="Trucks"),
             alt.Tooltip("miles:Q", title="Road miles", format=",.0f")]).project(**proj)
dots = alt.Chart(depots).mark_circle(opacity=1, stroke=SURFACE, strokeWidth=1.5).encode(
    longitude="lon:Q", latitude="lat:Q",
    size=alt.Size("demand:Q", scale=alt.Scale(range=[60, 420]), legend=None),
    color=alt.Color("position:N", scale=alt.Scale(domain=["Short before moves", "Spare before moves"], range=[AMBER, BLUE]),
                    legend=alt.Legend(title=None, orient="bottom", labelColor=SUB, symbolStrokeWidth=0)),
    tooltip=[alt.Tooltip("depot:N", title="Depot"), alt.Tooltip("demand:Q", title="Forecast orders"),
             alt.Tooltip("available:Q", title="Empties available"), alt.Tooltip("balance:Q", title="Spare (+) or short (−)"),
             alt.Tooltip("received:Q", title="Received"), alt.Tooltip("sent:Q", title="Sent"),
             alt.Tooltip("fill_pct:Q", title="Orders filled, %", format=".1f")]).project(**proj)
# Labels go right of the dot, except where a neighbour or a route is in the way (or, for Los Angeles, the map's edge)
PLACES = {"Philadelphia": ("right", -8, -2), "Tampa": ("right", -8, -2), "Los Angeles": ("center", 0, 16)}
spots = depots["depot"].map(lambda d: PLACES.get(d, ("left", 8, -2)))
names = [alt.Chart(depots[spots == spot]).mark_text(align=spot[0], dx=spot[1], dy=spot[2], fontSize=11, color=SUB).encode(
    longitude="lon:Q", latitude="lat:Q", text="label:N").project(**proj) for spot in set(spots)]
st.altair_chart(
    alt.layer(states, routes, dots, *names).properties(height=470).configure(background="transparent",
                                                                            font="Segoe UI, Open Sans, sans-serif")
    .configure_view(stroke=None),
    theme=None, width="stretch",
    alt=f"Map of the plan: {int(best_moves['containers'].sum())} empties moved on {len(best_moves)} routes from depots with spare "
        "empties to depots that are short")
st.caption("Teal lines are the plan's moves, thicker for more empties. Amber depots are short of empties before any moves, "
           "blue ones have spare. Dot size is the week's forecast orders. Hover for the numbers.")

# ----------------------------------------------------------------------------- three plans
st.subheader("Three ways to plan the same week")
rows = [dict(plan=name, part=part, cost=value) for name, (_, costs) in results.items() for part, value in costs.items()]
bars = pd.DataFrame(rows)
bars["total"] = bars["plan"].map(total)
order = list(PLANS)
stack = alt.Chart(bars).mark_bar(size=24, cornerRadius=2).encode(
    y=alt.Y("plan:N", sort=order, title=None, axis=alt.Axis(labelLimit=240, ticks=False, domain=False, labelFontSize=12)),
    x=alt.X("sum(cost):Q", title="Expected cost this week", axis=alt.Axis(format="$,.0f", tickCount=5)),
    color=alt.Color("part:N", scale=alt.Scale(domain=["Trucking", "Lost orders", "Yard overflow"], range=[TEAL, AMBER, SLATE]),
                    legend=alt.Legend(title=None, orient="top", labelColor=SUB)),
    order=alt.Order("part_order:Q"),
    tooltip=[alt.Tooltip("plan:N", title="Plan"), alt.Tooltip("part:N", title="Cost"),
             alt.Tooltip("cost:Q", title="Expected", format="$,.0f"), alt.Tooltip("total:Q", title="Plan total", format="$,.0f")])
labels = alt.Chart(pd.DataFrame({"plan": order, "total": [total[p] for p in order]})).mark_text(
    align="left", dx=6, color=INK, fontSize=12).encode(y=alt.Y("plan:N", sort=order), x="total:Q",
                                                       text=alt.Text("total:Q", format="$,.0f"))
st.altair_chart(
    alt.layer(stack.transform_calculate(part_order="indexof(['Trucking','Lost orders','Yard overflow'], datum.part)"), labels)
    .properties(height=200).configure(background="transparent", font="Segoe UI, Open Sans, sans-serif")
    .configure_view(stroke=None).configure_axis(domainColor=GRID, tickColor=GRID, gridColor=GRID, labelColor=SUB,
                                                titleColor=SUB, titleFontWeight="normal"),
    theme=None, width="stretch", alt="Expected weekly cost of each plan, split into trucking, lost orders and yard overflow")
point_moved = int(plan("Plans to the point forecast", cv, lost_cost, mile_cost, per_truck)["containers"].sum())
best_moved = int(best_moves["containers"].sum())
st.caption(
    "Every plan is scored the same way: its expected cost when demand misses the forecast by the error set above. "
    "The point-forecast plan treats the forecast as exact, so it covers a shortfall whenever a sure sale is worth the "
    "trucking. Using the error, the program weighs each extra empty by the chance it will actually be needed. "
    + (f"Here that means moving more empties ({best_moved:,} against {point_moved:,}), because an unfilled order costs "
       "much more than the trucking that would prevent it." if best_moved > point_moved else
       f"Here that means moving fewer empties ({best_moved:,} against {point_moved:,}): the last few would cost more "
       "to truck than the orders they would probably save." if best_moved < point_moved else
       f"Here both move {best_moved:,} empties.")
    + f" It comes out {money(gap, md=True)} a week ahead."
)

# ----------------------------------------------------------------------------- forecast accuracy in dollars
st.subheader("What a better forecast is worth")
grid = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
with st.spinner("Re-planning at each forecast error…"):
    curve = pd.DataFrame([dict(error=round(g * 100), plan=name,
                               cost=sum(evaluate(plan(name, g, lost_cost, mile_cost, per_truck), g, lost_cost, mile_cost)[1].values()))
                          for g in grid for name in PLANS])
x = alt.X("error:Q", title="Forecast error (% of the forecast)", scale=alt.Scale(domain=[5, 40]),
          axis=alt.Axis(values=[round(g * 100) for g in grid]))
yv = alt.Y("cost:Q", title="Expected weekly cost", axis=alt.Axis(format="$,.0f", tickCount=5))
line = alt.Chart(curve).mark_line(strokeCap="round", point=alt.OverlayMarkDef(size=36, filled=True)).encode(
    x=x, y=yv,
    color=alt.Color("plan:N", scale=alt.Scale(domain=order, range=[TEAL, SLATE, MUTED]),
                    legend=alt.Legend(title=None, orient="top", labelColor=SUB)),
    strokeDash=alt.StrokeDash("plan:N", scale=alt.Scale(domain=order, range=[[1, 0], [6, 4], [2, 3]]), legend=None),
    strokeWidth=alt.condition(alt.datum.plan == order[0], alt.value(3), alt.value(2)),
    tooltip=[alt.Tooltip("plan:N", title="Plan"), alt.Tooltip("error:Q", title="Forecast error, %"),
             alt.Tooltip("cost:Q", title="Expected weekly cost", format="$,.0f")])
now = alt.Chart(pd.DataFrame({"error": [cv * 100]})).mark_rule(color=INK, opacity=0.35).encode(x=x)
st.altair_chart(
    alt.layer(now, line).properties(height=300).configure(background="transparent", font="Segoe UI, Open Sans, sans-serif")
    .configure_view(stroke=None).configure_axis(domainColor=GRID, tickColor=GRID, gridColor=GRID, labelColor=SUB,
                                                titleColor=SUB, titleFontWeight="normal").configure_axisX(grid=False),
    theme=None, width="stretch", alt="Expected weekly cost of each plan as forecast error grows from 5% to 40%")
best_curve = curve[curve["plan"] == order[0]].set_index("error")["cost"]
here, better = best_curve.loc[round(cv * 100)], best_curve.loc[max(5, round(cv * 100) - 5)]
st.caption(
    f"The faint line marks the error set above. At {cv:.0%}, cutting the forecast's error by five points is worth about "
    f"{rough(here - better)} a week here, about {rough((here - better) * 52)} a year, before the program changes at all. "
    "The gap between the solid and dashed lines is what using the error, rather than ignoring it, is worth at each accuracy."
    if cv > 0.05 else
    "At 5% error the forecast is close to certain, so the two planning methods nearly agree. Raise the error to see them part."
)

# ----------------------------------------------------------------------------- details
with st.expander("The moves", icon=":material/local_shipping:"):
    table = lines.assign(cost=lines["trucks"] * (DISPATCH + mile_cost * lines["miles"]))[
        ["origin", "dest", "containers", "trucks", "miles", "cost"]].sort_values("cost", ascending=False)
    st.dataframe(table, hide_index=True,
                 column_config={"origin": "From", "dest": "To", "containers": st.column_config.NumberColumn("Empties", format="%d"),
                                "trucks": st.column_config.NumberColumn("Trucks", format="%d"),
                                "miles": st.column_config.NumberColumn("Road miles", format="%.0f"),
                                "cost": st.column_config.NumberColumn("Trucking", format="$%.0f")})
with st.expander("Each depot", icon=":material/warehouse:"):
    st.dataframe(depots[["depot", "demand", "available", "received", "sent", "stock", "lost", "overflow", "fill"]], hide_index=True,
                 column_config={"depot": "Depot", "demand": "Forecast orders", "available": "Empties available",
                                "received": st.column_config.NumberColumn("Received", format="%d"),
                                "sent": st.column_config.NumberColumn("Sent", format="%d"),
                                "stock": st.column_config.NumberColumn("After moves", format="%d"),
                                "lost": st.column_config.NumberColumn("Expected lost orders", format="%.1f"),
                                "overflow": st.column_config.NumberColumn("Expected overflow", format="%.1f"),
                                "fill": st.column_config.NumberColumn("Orders filled", format="percent")})
with st.expander("How the program works", icon=":material/functions:"):
    st.markdown(
        "**Decisions.** For each pair of depots within "
        f"{MAX_MILES:,} road miles: $x_{{ij}}$, the empties sent from $i$ to $j$, and $y_{{ij}}$, the trucks, both whole "
        "numbers. That makes it a mixed-integer program.\n\n"
        "**Stock after the moves.** $s_i = a_i + \\sum_j x_{ji} - \\sum_j x_{ij}$, where $a_i$ is the depot's empties on "
        "hand plus those freed by deliveries already booked this week. A depot can't send more than $a_i$, and "
        f"$x_{{ij}} \\le {per_truck}\\,y_{{ij}}$ at the setting above.\n\n"
        "**Demand.** Normal, with the forecast as its mean and the forecast error times the forecast as its standard "
        "deviation $\\sigma_i$.\n\n"
        "**Objective.** Minimise "
        f"$\\sum_{{ij}} y_{{ij}}\\,({DISPATCH} + c\\,d_{{ij}}) + p\\,\\sum_i \\mathrm{{E}}[\\text{{lost}}_i] + {OVERFLOW}"
        "\\sum_i \\mathrm{E}[\\text{overflow}_i]$, with $c$ the cost per mile, $d_{ij}$ the road miles and $p$ the margin "
        "of an unfilled order. Expected lost orders are $\\sigma_i\\,L\\big((s_i-\\mu_i)/\\sigma_i\\big)$, where $L$ is the "
        "standard normal loss function; overflow is the same on the other tail, past the yard's space. Both are convex in "
        f"$s_i$, so {len(TANGENTS)} tangent lines per depot make them linear without losing the optimum's shape.\n\n"
        "**The point-forecast plan** solves the same program with demand fixed at the forecast: lost orders are "
        "$\\max(0, \\mu_i - s_i)$. **Scoring** uses the exact expected costs for all three plans.\n\n"
        f"**Solver.** HiGHS through SciPy's `milp`, {2 * len(ARCS)} integer variables, solved to within 0.1% of the best "
        "possible. Distances are great-circle miles times 1.2."
    )
st.caption("Illustrative network: real metro locations, made-up volumes, not any company's data. "
           "[Code on GitHub](https://github.com/livingdw67/portfolio/blob/main/app_pages/container_planner.py)")
