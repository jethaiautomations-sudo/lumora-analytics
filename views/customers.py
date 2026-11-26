from __future__ import annotations

import pandas as pd
import streamlit as st

from core import bi
from ui import bi_charts as bc
from ui import components as ui
from ui.theme import COLORS, PLOTLY_CONFIG, fmt_change, fmt_value

SECTION = "Customers"
TITLE = "Customer analytics"
SUBTITLE = "Who buys, how often, and which customers and segments drive revenue."

ROW_CHART_HEIGHT = 320   # charts that share a row are the same height, so their cards line up


def render(ctx) -> None:
    cm = bi.customer_metrics(ctx.cur_o, ctx.start, ctx.end, history=ctx.orders)
    if not cm:
        ui.empty_state("No customers in this selection", "Try a wider date range or clear some filters.")
        return
    prev = bi.customer_metrics(ctx.prev_o, ctx.prev_start, ctx.prev_end, history=ctx.orders) or {}
    chg = bi.pct(cm["customers"], prev.get("customers"))
    with st.container(key="sec_cu_stats"):
        ui.mini_stats([
            ("Unique customers", f"{cm['customers']:,}", f"{fmt_change(chg, 'pct')} vs previous period" if chg is not None else "Selected period"),
            ("New customers", f"{cm['new']:,}", f"{cm['new'] / cm['customers'] * 100:.0f}% of customers"),
            ("Returning customers", f"{cm['returning']:,}", f"{cm['returning'] / cm['customers'] * 100:.0f}% of customers"),
            ("Avg. spend per customer", fmt_value(cm["avg_spend"], "usd2"), "Selected period"),
            ("Repeat purchase rate", fmt_value(cm["lifetime_repeat_rate"], "pct1"), "Customers with 2+ orders ever"),
            ("Purchase frequency", f"{cm['lifetime_avg_orders']:.2f}", "Avg. orders per customer, lifetime"),
        ])
        st.caption(f"In this period alone, {cm['repeat_rate']:.1f}% of customers ordered more than once "
                   f"(avg. {cm['avg_frequency']:.2f} orders each).")

    a, b = st.columns([1, 2])
    with a:
        with st.container(key="card_cu_nvr"):
            ui.section_title("New vs returning", "Share of revenue in the selected period.")
            st.plotly_chart(bc.donut(["New", "Returning"], [cm["new_revenue"], cm["returning_revenue"]],
                                     [COLORS["teal"], COLORS["blue"]], "revenue",
                                     fmt_value(cm["new_revenue"] + cm["returning_revenue"], "usdk"), height=ROW_CHART_HEIGHT),
                            use_container_width=True, config=PLOTLY_CONFIG)
    with b:
        with st.container(key="card_cu_trend"):
            ui.section_title("New vs returning customers by month", "12 months up to the end of the selected period.")
            hist = ctx.orders[(ctx.orders["order_date"] <= pd.Timestamp(ctx.end)) &
                              (ctx.orders["order_date"] > pd.Timestamp(ctx.end) - pd.DateOffset(months=12))]
            st.plotly_chart(bc.new_vs_returning(bi.new_vs_returning_trend(hist), height=ROW_CHART_HEIGHT),
                            use_container_width=True, config=PLOTLY_CONFIG)

    with st.container(key="sec_cu_top"):
        ui.section_title("Top 10 customers by revenue", "Selected period.")
        top = bi.top_customers(ctx.cur_o, 10).reset_index(drop=True)
        top["rank"] = top.index + 1
        ui.data_table(top, [("rank", "", "rank"), ("customer_name", "Customer", "text"), ("segment", "Segment", "text"),
                            ("country", "Country", "text"), ("revenue", "Revenue", "usd0"), ("orders", "Orders", "int"),
                            ("aov", "AOV", "usd2"), ("gross_profit", "Gross profit", "usd0"), ("last_order", "Last order", "date")])

    seg = bi.breakdown(ctx.cur_o, ctx.prev_o, "segment")
    a, b = st.columns(2)
    with a:
        with st.container(key="card_cu_freq"):
            ui.section_title("Purchase frequency", "Lifetime orders per customer, for customers active in the period.")
            st.plotly_chart(bc.frequency_bars(cm["lifetime_frequency"], cap=8, height=300),
                            use_container_width=True, config=PLOTLY_CONFIG)
    with b:
        with st.container(key="card_cu_seg"):
            ui.section_title("Revenue by customer segment", "Grey bar: previous period.")
            st.plotly_chart(bc.ranked_bars(seg, "revenue", prev="prev_revenue", extra="share_pct", extra_label="Share",
                                           height=300, legend=False),
                            use_container_width=True, config=PLOTLY_CONFIG)

    with st.container(key="sec_cu_seg"):
        ui.section_title("Segment contribution", "Revenue, customers and order value by segment.")
        seg["rev_per_customer"] = seg["revenue"] / seg["customers"].where(seg["customers"] > 0)
        ui.data_table(seg, [("name", "Segment", "text"), ("revenue", "Revenue", "usd0"), ("share_pct", "Share", "share"),
                            ("growth_pct", "Growth", "growth"), ("customers", "Customers", "int"), ("orders", "Orders", "int"),
                            ("aov", "AOV", "usd2"), ("rev_per_customer", "Revenue / customer", "usd0")])
