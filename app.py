"""Lumora Analytics: sales performance & BI dashboard.

Run with:  streamlit run app.py
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Lumora Analytics", page_icon=str(Path(__file__).resolve().parent / "assets" / "logo.png"), layout="wide",
                   initial_sidebar_state="expanded")

from core import bi  # noqa: E402
from core import metrics as m  # noqa: E402
from core import settings  # noqa: E402
from core.data import DataError, load_ai_report, load_sales  # noqa: E402
from ui import components as ui  # noqa: E402
from ui.theme import inject_css, register_plotly_template  # noqa: E402
from views import (ai_report, automation, channels, customers, explorer, overview, products,  # noqa: E402
                   profitability, revenue, sales_team)

PAGES = {
    "overview": overview, "revenue": revenue, "sales_team": sales_team, "products": products,
    "customers": customers, "profitability": profitability,
    "channels": channels, "ai_report": ai_report, "automation": automation, "explorer": explorer,
}
MARKETING_PAGES = {"channels", "ai_report", "automation"}
PRESETS = ["Last 7 days", "Last 30 days", "Last 90 days", "Month to date", "Quarter to date",
           "Year to date", "Last 12 months", "Custom"]


# ---------- cached loaders ----------

@st.cache_data(show_spinner=False, ttl=300)
def get_orders() -> pd.DataFrame:
    return bi.load_orders()


@st.cache_data(show_spinner=False, ttl=300)
def get_targets() -> pd.DataFrame:
    return bi.load_targets()


@st.cache_data(show_spinner=False, ttl=300)
def get_marketing(sheet_id: str | None) -> pd.DataFrame:
    return load_sales(sheet_id)


@st.cache_data(show_spinner=False, ttl=300)
def get_ai_report(sheet_id: str | None) -> dict | None:
    return load_ai_report(sheet_id)


# ---------- context passed to every page ----------

@dataclass
class Context:
    # sales BI (orders)
    orders: pd.DataFrame          # all orders after dimension filters (any date)
    cur_o: pd.DataFrame           # selected period
    prev_o: pd.DataFrame          # previous period of the same length
    prev2_o: pd.DataFrame         # the period before that (for growth comparison)
    targets: pd.DataFrame
    filters: bi.Filters
    # dates
    start: date
    end: date
    prev_start: date
    prev_end: date
    period_label: str
    compare_label: str
    # marketing (daily channel data) for the marketing & AI pages
    df: pd.DataFrame
    channels: list[str]
    cur_df: pd.DataFrame
    prev_df: pd.DataFrame
    cur: dict
    prev: dict
    channel_table: pd.DataFrame
    ai_report: dict | None


def preset_range(preset: str, max_d: date, min_d: date) -> tuple[date, date]:
    if preset.startswith("Last") and "months" not in preset:
        n = int(preset.split()[1])
        start = max_d - timedelta(days=n - 1)
    elif preset == "Last 12 months":
        start = (pd.Timestamp(max_d) - pd.DateOffset(months=12) + pd.Timedelta(days=1)).date()
    elif preset == "Month to date":
        start = max_d.replace(day=1)
    elif preset == "Quarter to date":
        start = date(max_d.year, 3 * ((max_d.month - 1) // 3) + 1, 1)
    elif preset == "Year to date":
        start = max_d.replace(month=1, day=1)
    else:
        return st.session_state.get("range", (max_d - timedelta(days=29), max_d))
    return max(min_d, start), max_d


def fmt_range(a: date, b: date) -> str:
    return f"{a:%d %b} – {b:%d %b %Y}" if a.year == b.year else f"{a:%d %b %Y} – {b:%d %b %Y}"


def filter_bar(orders: pd.DataFrame, marketing: pd.DataFrame, page_key: str) -> tuple[date, date, bi.Filters, list[str]]:
    min_d, max_d = orders["order_date"].min().date(), orders["order_date"].max().date()
    opts = {c: sorted(orders[c].astype(str).unique()) for c in ["region", "category", "salesperson", "segment", "channel"]}
    mkt_channels = sorted(marketing["channel"].unique())

    ss = st.session_state
    if "preset" not in ss:
        ss.preset = "Last 30 days"
    if "range" not in ss:
        ss.range = preset_range(ss.preset, max_d, min_d)
    for key in ["f_region", "f_category", "f_salesperson", "f_segment", "f_channel", "f_mkt"]:
        ss.setdefault(key, [])

    def on_preset():
        if ss.preset != "Custom":
            ss.range = preset_range(ss.preset, max_d, min_d)

    def on_range():
        ss.preset = "Custom"

    def clear_filters():
        for key in ["f_region", "f_category", "f_salesperson", "f_segment", "f_channel", "f_mkt"]:
            ss[key] = []

    c1, c2, c3, c4, c5 = st.columns([1.1, 1.5, 2.2, 0.75, 0.75], vertical_alignment="bottom")
    c1.selectbox("Period", PRESETS, key="preset", on_change=on_preset)
    c2.date_input("Date range", key="range", min_value=min_d, max_value=max_d, on_change=on_range, format="DD/MM/YYYY")

    active = sum(bool(ss[k]) for k in ["f_region", "f_category", "f_salesperson", "f_segment", "f_channel", "f_mkt"])
    with c3.popover(f"Filters · {active} active" if active else "Filters", icon=":material/filter_list:", use_container_width=True):
        a, b = st.columns(2)
        a.multiselect("Region", opts["region"], key="f_region", placeholder="All regions")
        b.multiselect("Category", opts["category"], key="f_category", placeholder="All categories")
        a.multiselect("Salesperson", opts["salesperson"], key="f_salesperson", placeholder="All salespeople")
        b.multiselect("Customer segment", opts["segment"], key="f_segment", placeholder="All segments")
        a.multiselect("Sales channel", opts["channel"], key="f_channel", placeholder="All sales channels")
        b.multiselect("Marketing channel", mkt_channels, key="f_mkt", placeholder="All marketing channels",
                      help="Used on the Marketing channels, AI report and Automation pages.")
        st.button("Clear all filters", on_click=clear_filters, icon=":material/filter_alt_off:", key="clear_f")

    rng = ss.range
    if not isinstance(rng, (tuple, list)) or len(rng) < 2:
        st.info("Pick an end date to complete the date range.", icon=":material/event:")
        st.stop()
    start, end = rng[0], rng[1]
    f = bi.Filters(ss.f_region, ss.f_category, ss.f_salesperson, ss.f_segment, ss.f_channel)

    mkt_selected = ss.f_mkt or mkt_channels
    if page_key in MARKETING_PAGES:
        # marketing pages: the daily channel rows behind the page, for the selected channels and period
        export = m.filter_sales(marketing[marketing["channel"].isin(mkt_selected)], start, end).copy()
        export["date"] = export["date"].dt.strftime("%Y-%m-%d")
        what = "daily marketing data (sessions, orders, revenue, ad spend by channel)"
    else:
        export = bi.in_period(bi.apply_filters(orders, f), start, end).drop(columns=["customer_first_order"]).copy()
        export["order_date"] = export["order_date"].dt.strftime("%Y-%m-%d")
        what = "order lines"
    c4.download_button("Export", export.to_csv(index=False).encode(), file_name=f"lumora_{page_key}_{start}_{end}.csv",
                       mime="text/csv", icon=":material/download:", use_container_width=True,
                       key=f"export_{page_key}", disabled=export.empty,
                       help=f"Download the {what} for {fmt_range(start, end)} with your current filters, as CSV.")
    if c5.button("Refresh", icon=":material/refresh:", use_container_width=True, key=f"refresh_{page_key}"):
        st.cache_data.clear()
        st.toast("Data reloaded.", icon=":material/check_circle:")
        st.rerun()
    return start, end, f, mkt_selected


def main() -> None:
    inject_css()
    register_plotly_template()
    st.session_state.setdefault("page", "overview")

    sheet_id = settings.gsheet_id()
    try:
        with st.spinner("Loading data…"):
            orders = get_orders()
            targets = get_targets()
            marketing = get_marketing(sheet_id)
            report = get_ai_report(sheet_id)
    except (DataError, bi.BIDataError) as e:
        st.error(f"Could not load data. {e}")
        st.stop()

    if orders.empty:
        ui.empty_state("No data yet", "Add rows to data/orders.csv, or run data/generate_sample_data.py.")
        st.stop()

    page = st.session_state.page if st.session_state.page in PAGES else "overview"
    source = ("Google Sheets" if sheet_id else "Local files") if page in MARKETING_PAGES else "Orders file"
    through = (marketing["date"].max() if page in MARKETING_PAGES else orders["order_date"].max()).strftime("%d %b %Y")
    page = ui.sidebar(page, through, source)
    view = PAGES[page]

    header_slot = st.container()
    start, end, f, mkt_channels = filter_bar(orders, marketing, page)
    prev_start, prev_end = bi.previous_period(start, end)
    p2_start, p2_end = bi.previous_period(prev_start, prev_end)

    scoped = bi.apply_filters(orders, f)
    mkt = marketing[marketing["channel"].isin(mkt_channels)]
    mcur, mprev = m.filter_sales(mkt, start, end), m.filter_sales(mkt, prev_start, prev_end)
    ctx = Context(
        orders=scoped, cur_o=bi.in_period(scoped, start, end), prev_o=bi.in_period(scoped, prev_start, prev_end),
        prev2_o=bi.in_period(scoped, p2_start, p2_end), targets=targets, filters=f,
        start=start, end=end, prev_start=prev_start, prev_end=prev_end,
        period_label=fmt_range(start, end), compare_label=fmt_range(prev_start, prev_end),
        df=mkt, channels=mkt_channels, cur_df=mcur, prev_df=mprev, cur=m.totals(mcur), prev=m.totals(mprev),
        channel_table=m.channel_table(mcur, mprev), ai_report=report,
    )
    with header_slot:
        ui.page_header(view.SECTION, view.TITLE, view.SUBTITLE, ctx.period_label, ctx.compare_label)

    empty = ctx.cur_df.empty if page in MARKETING_PAGES else ctx.cur_o.empty
    if empty:
        ui.empty_state("No data for this selection", "Try a wider date range or clear some filters.")
        return
    if page not in MARKETING_PAGES and ctx.prev_o.empty:
        st.caption("No data for the previous period, so comparisons are not shown.")
    # Keyed wrapper: assets/style.css sets the gap between page sections on .st-key-page_*
    with st.container(key=f"page_{page}"):
        view.render(ctx)


main()
