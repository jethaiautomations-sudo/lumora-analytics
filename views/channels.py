from __future__ import annotations

import pandas as pd
import streamlit as st

from core import metrics as m
from ui import charts
from ui import components as ui
from ui.theme import PLOTLY_CONFIG

SECTION = "Marketing channels"
TITLE = "Marketing channels"
SUBTITLE = "Website sessions, conversion and ad efficiency by acquisition channel (daily marketing data, 2026)."

METRICS = {
    "Revenue": ("revenue", "usd"),
    "Orders": ("orders", "int"),
    "Conversion rate": ("conversion_rate", "pct"),
    "Return rate": ("return_rate", "pct"),
}
ROW_CHART_HEIGHT = 320   # charts that share a row are the same height, so their cards line up
TOGGLE_ROW = 48          # segmented control (32px) + the 16px gap below it


def render(ctx) -> None:
    kpis = m.kpi_summary(ctx.cur, ctx.prev)
    weekly = m.weekly_series(ctx.df, ctx.end, weeks=12)
    sparks = {k.key: weekly[k.key].tolist() for k in kpis} if not weekly.empty else {}
    ui.kpi_grid(kpis, sparks, "prior")

    with st.container(key="card_alerts"):
        ui.section_title("Alerts", "Automatic checks on every marketing channel.")
        ui.alert_list(m.alerts(ctx.channel_table))

    with st.container(key="card_stack"):
        ui.section_title("Weekly revenue by channel", "Rolling 7-day weeks ending on the last day of the selected period.")
        wch = m.weekly_by_channel(ctx.df, ctx.end)
        if wch.empty:
            ui.empty_state("Not enough history", "Weekly trends need at least one full week of data.")
        else:
            st.plotly_chart(charts.channel_stacked(wch), use_container_width=True, config=PLOTLY_CONFIG)

    c1, c2 = st.columns(2)
    with c1:
        with st.container(key="card_spend"):
            ui.section_title("Ad spend vs paid ROAS", "Paid channels only (channels with ad spend).")
            paid = ctx.df[ctx.df["ad_spend_usd"] > 0]
            wp = m.weekly_series(paid, ctx.end)
            if wp.empty:
                ui.empty_state("No paid channels selected", "Add Google Ads or Paid Social in the channel filter.")
            else:
                st.plotly_chart(charts.spend_vs_roas(wp, height=ROW_CHART_HEIGHT), use_container_width=True, config=PLOTLY_CONFIG)
    with c2:
        with st.container(key="card_metric"):
            ui.section_title("Weekly trend", "The highlighted bar is the week ending on the last day of the selected period.")
            choice = st.segmented_control("Metric", list(METRICS), default="Revenue", key="ch_metric",
                                          label_visibility="collapsed") or "Revenue"
            field, fmt = METRICS[choice]
            wk = m.weekly_series(ctx.df, ctx.end)
            if wk.empty:
                ui.empty_state("Not enough history", "Weekly trends need at least one full week of data.")
            else:
                # the toggle row (control + gap) takes the rest of the row height
                st.plotly_chart(charts.weekly_metric(wk, field, choice, fmt, highlight_end=pd.Timestamp(ctx.end),
                                                     height=ROW_CHART_HEIGHT - TOGGLE_ROW),
                                use_container_width=True, config=PLOTLY_CONFIG)

    with st.container(key="sec_ch_score"):
        ui.section_title("Channel scorecard", "Selected period vs previous period.")
        ui.channel_html_table(ctx.channel_table)
