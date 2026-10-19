"""
Law Firm Operations Dashboard

    streamlit run app.py

Reads the warehouse built by run_pipeline.py.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).resolve().parent / "data" / "warehouse.duckdb"

# Validated colour palette (categorical slots in fixed order, status colours reserved)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
BLUE_RAMP = ["#b7d3f6", "#6da7ec", "#2a78d6", "#184f95"]
CRITICAL = "#d03b3b"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e7e6e2"

st.set_page_config(page_title="Law Firm Operations", page_icon=None, layout="wide")


@st.cache_data
def load(table: str) -> pd.DataFrame:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.execute(f"SELECT * FROM {table}").df()


def style(fig: go.Figure, height: int = 340, y_format: str | None = None) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=INK_2, size=13), hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
        hoverlabel=dict(bgcolor="white", font_color=INK),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, ticks="")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickformat=y_format)
    return fig


def money(x: float) -> str:
    return f"${x / 1000:,.0f}k" if abs(x) >= 10000 else f"${x:,.0f}"


def md_money(x: float) -> str:
    """Money for markdown text: Streamlit treats a pair of $ signs as a maths formula."""
    return money(x).replace("$", "\\$")


if not DB_PATH.exists():
    st.error("No warehouse found. Run `python run_pipeline.py` first.")
    st.stop()

funnel = load("fct_intake_funnel")
atty = load("fct_attorney_month")
practice = load("fct_practice_month")
aging = load("fct_ar_aging")
weekly = load("fct_weekly_leads")
checks = load("meta_quality_checks")
cleaning = load("meta_cleaning_log")

for df, col in [(funnel, "month"), (atty, "month"), (practice, "month"), (weekly, "week")]:
    df[col] = pd.to_datetime(df[col])

# ---------------------------------------------------------------- header + filter
st.title("Law Firm Operations")
st.caption("One source of truth across CRM, practice management, billing and ad spend. "
           "Sample data for a 7 attorney firm, reporting date 30 Sep 2026.")

months = sorted(practice["month"].dt.to_period("M").unique())
f1, f2 = st.columns([2, 3])
with f1:
    start, end = st.select_slider(
        "Reporting period", options=months, value=(months[-12], months[-1]),
        format_func=lambda p: p.strftime("%b %Y"))
lo, hi = start.to_timestamp(), end.to_timestamp()


def in_period(df: pd.DataFrame, col: str = "month") -> pd.DataFrame:
    return df[(df[col] >= lo) & (df[col] <= hi)]


# ---------------------------------------------------------------- KPI row
p_prac, p_atty, p_funnel = in_period(practice), in_period(atty), in_period(funnel)
billed, collected = p_prac["billed"].sum(), p_prac["collected"].sum()
over_90 = aging.loc[aging["aging_bucket"] == "Over 90 days", "outstanding"].sum()
utilization = p_atty["billable_hours"].sum() / (140 * p_atty.groupby(["attorney", "month"]).ngroups)

kpis = [
    ("Billed", money(billed), "Invoices issued in the period"),
    ("Collected", money(collected), f"{collected / billed:.0%} of billed amount"),
    ("New clients retained", f"{int(p_funnel['retained'].sum()):,}", "From all intake channels"),
    ("Average utilization", f"{utilization:.0%}", "Against 140 billable hours a month"),
    ("Receivables over 90 days", money(over_90), f"{over_90 / aging['outstanding'].sum():.0%} of all receivables"),
]
for col, (label, value, note) in zip(st.columns(5), kpis):
    col.metric(label, value)
    col.caption(note)

tabs = st.tabs(["What needs attention", "Intake & marketing", "Team performance",
                "Revenue & collections", "Data quality"])

# ---------------------------------------------------------------- attention
with tabs[0]:
    st.subheader("What needs attention")
    alerts = weekly[weekly["is_anomaly"]]
    if not alerts.empty:
        for ch, grp in alerts.groupby("channel"):
            weeks = ", ".join(grp["week"].dt.strftime("%d %b %Y"))
            lost = (grp["trailing_avg"] - grp["leads"]).sum()
            st.error(f"**{ch} leads stopped arriving** in the weeks of {weeks}. "
                     f"About {lost:.0f} leads were lost against the usual run rate while ad spend continued. "
                     "Check the form and tracking integration.")

    ch = p_funnel.groupby("channel")[["leads", "retained", "spend_usd"]].sum()
    paid = ch[ch["spend_usd"] > 0].assign(cpr=lambda d: d["spend_usd"] / d["retained"])
    worst, best = paid["cpr"].idxmax(), paid["cpr"].idxmin()
    st.warning(f"**{worst} costs {md_money(paid.loc[worst, 'cpr'])} per retained client**, versus "
               f"{md_money(paid.loc[best, 'cpr'])} for {best}. Shifting part of that budget would bring in more clients for the same spend.")

    u = p_atty.groupby("attorney")["billable_hours"].sum() / (140 * p_atty.groupby("attorney")["month"].nunique())
    st.warning(f"**Workload is uneven.** {u.idxmax()} is at {u.max():.0%} utilization while "
               f"{u.idxmin()} is at {u.min():.0%}. Rebalancing new matters protects quality and retention.")

    by_area = aging.groupby("practice_area")["outstanding"].sum()
    old_area = aging[aging["aging_bucket"] == "Over 90 days"].groupby("practice_area")["outstanding"].sum()
    top = (old_area / by_area).idxmax()
    st.info(f"**{top} has the slowest collections:** {old_area[top] / by_area[top]:.0%} of its receivables "
            f"are more than 90 days old ({md_money(old_area[top])}).")

# ---------------------------------------------------------------- intake
with tabs[1]:
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Weekly leads by channel")
        channels = sorted(weekly["channel"].unique())
        pick = st.multiselect("Channels", channels, default=["Google Ads", "Website Organic"])
        wk = in_period(weekly, "week")
        fig = go.Figure()
        for i, name in enumerate(channels):          # colour follows the channel, not its position in the filter
            if name not in pick:
                continue
            d = wk[wk["channel"] == name]
            fig.add_trace(go.Scatter(x=d["week"], y=d["leads"], name=name, mode="lines",
                                     line=dict(color=SERIES[i], width=2)))
            a = d[d["is_anomaly"]]
            if not a.empty:
                fig.add_trace(go.Scatter(x=a["week"], y=a["leads"], mode="markers+text", name=f"{name} alert",
                                         marker=dict(color=CRITICAL, size=10, symbol="x"),
                                         text=["Alert"] + [""] * (len(a) - 1), textposition="top center",
                                         textfont=dict(color=INK), showlegend=False))
        st.plotly_chart(style(fig), width="stretch")

    with c2:
        st.subheader("Cost per retained client")
        cpr = paid.sort_values("cpr")
        fig = go.Figure(go.Bar(y=cpr.index, x=cpr["cpr"], orientation="h", marker_color=SERIES[0],
                               text=[money(v) for v in cpr["cpr"]], textposition="outside",
                               textfont=dict(color=INK), hovertemplate="%{y}: $%{x:,.0f}<extra></extra>"))
        fig.update_layout(hovermode="closest", bargap=0.45)
        fig.update_xaxes(showticklabels=False, range=[0, cpr["cpr"].max() * 1.25])
        st.plotly_chart(style(fig), width="stretch")
        st.caption("Referral clients cost nothing in ad spend and are excluded from this chart.")

    st.subheader("Intake funnel by channel")
    tbl = ch.join(p_funnel.groupby("channel")["consultations"].sum())
    tbl = pd.DataFrame({
        "Leads": tbl["leads"], "Consultations": tbl["consultations"], "Retained": tbl["retained"],
        "Lead to consult": tbl["consultations"] / tbl["leads"],
        "Consult to retained": tbl["retained"] / tbl["consultations"],
        "Ad spend": tbl["spend_usd"],
    }).sort_values("Retained", ascending=False)
    st.dataframe(tbl.style.format({"Lead to consult": "{:.0%}", "Consult to retained": "{:.0%}",
                                   "Ad spend": "${:,.0f}"}), width="stretch")

# ---------------------------------------------------------------- team
with tabs[2]:
    team = p_atty.groupby("attorney").agg(
        billable_hours=("billable_hours", "sum"), months=("month", "nunique"),
        standard=("standard_value", "sum"), billed=("billed", "sum"), collected=("collected", "sum"))
    team["utilization"] = team["billable_hours"] / (140 * team["months"])
    team["realization"] = team["billed"] / team["standard"]
    team["collection"] = team["collected"] / team["billed"]
    team = team.sort_values("utilization")

    st.subheader("Utilization against the 140 hour monthly target")
    fig = go.Figure(go.Bar(y=team.index, x=team["utilization"], orientation="h", marker_color=SERIES[0],
                           text=[f"{v:.0%}" for v in team["utilization"]], textposition="outside",
                           textfont=dict(color=INK), hovertemplate="%{y}: %{x:.0%}<extra></extra>"))
    fig.add_vline(x=1, line=dict(color=INK_2, width=1, dash="dot"),
                  annotation_text="Target", annotation_position="bottom right",
                  annotation_font_color=INK_2)
    fig.update_layout(hovermode="closest", bargap=0.45)
    st.plotly_chart(style(fig, height=320).update_xaxes(tickformat=".0%", range=[0, max(1.15, team["utilization"].max() + 0.15)]),
                    width="stretch")

    st.subheader("Realization and collections")
    st.caption("Realization: share of standard value actually billed. Collection: share of billed amount received.")
    st.dataframe(team[["billable_hours", "realization", "collection"]].sort_values("realization")
                 .rename_axis("Attorney")
                 .rename(columns={"billable_hours": "Billable hours", "realization": "Realization",
                                  "collection": "Collection rate"})
                 .style.format({"Billable hours": "{:,.0f}", "Realization": "{:.0%}", "Collection rate": "{:.0%}"}),
                 width="stretch")

# ---------------------------------------------------------------- revenue
with tabs[3]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Billed and collected by month")
        m = p_prac.groupby("month")[["billed", "collected"]].sum().reset_index()
        fig = go.Figure()
        for i, (col, name) in enumerate([("billed", "Billed"), ("collected", "Collected")]):
            fig.add_trace(go.Scatter(x=m["month"], y=m[col], name=name, mode="lines+markers",
                                     line=dict(color=SERIES[i], width=2), marker=dict(size=8)))
        st.plotly_chart(style(fig, y_format="$~s"), width="stretch")
        st.caption("Invoices from the last month or two are still inside normal payment terms, "
                   "so collections for recent months will rise as clients pay.")
    with c2:
        st.subheader("Billed revenue by practice area")
        areas = sorted(practice["practice_area"].unique())
        fig = go.Figure()
        for i, a in enumerate(areas):
            d = p_prac[p_prac["practice_area"] == a]
            fig.add_trace(go.Scatter(x=d["month"], y=d["billed"], name=a, mode="lines",
                                     line=dict(color=SERIES[i], width=2)))
        st.plotly_chart(style(fig, y_format="$~s"), width="stretch")

    st.subheader("Receivables by age")
    order = ["0-30 days", "31-60 days", "61-90 days", "Over 90 days"]
    ag = aging.groupby("aging_bucket")["outstanding"].sum().reindex(order)
    fig = go.Figure(go.Bar(x=ag.index, y=ag.values, marker_color=BLUE_RAMP,
                           text=[money(v) for v in ag.values], textposition="outside",
                           textfont=dict(color=INK), hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
    fig.update_layout(hovermode="closest", bargap=0.45)
    fig.update_yaxes(range=[0, ag.max() * 1.2])
    st.plotly_chart(style(fig, height=300, y_format="$~s"), width="stretch")

# ---------------------------------------------------------------- data quality
with tabs[4]:
    st.subheader("Automated checks")
    st.caption("These run every time the pipeline runs. A FAIL stops the dashboard from refreshing.")
    icon = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}
    st.dataframe(checks.assign(status=checks["status"].map(icon))
                 .rename(columns={"check": "Check", "failing_rows": "Rows affected", "status": "Status"}),
                 width="stretch", hide_index=True)
    st.subheader("What the cleaning step fixed")
    st.dataframe(cleaning.rename(columns={"table": "Source", "issue": "Issue",
                                          "rows_affected": "Rows", "action": "Action taken"}),
                 width="stretch", hide_index=True)
