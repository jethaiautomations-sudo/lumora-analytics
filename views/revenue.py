from __future__ import annotations

import pandas as pd
import streamlit as st

from core import bi
from ui import bi_charts as bc
from ui import components as ui
from ui.theme import PLOTLY_CONFIG, fmt_change, fmt_value

SECTION = "Revenue"
TITLE = "Revenue analytics"
SUBTITLE = "Trends at any granularity, and where revenue comes from by category, product, region and country."

ROW_CHART_HEIGHT = 380   # charts that share a row are the same height, so their cards line up


def render(ctx) -> None:
    with st.container(key="card_rev_trend"):
        with ui.section_head("Revenue trend", "Yearly view uses all history up to the end date; the others use the selected period.",
                             "rev_gran"):
            gran = st.segmented_control("Granularity", ["Daily", "Weekly", "Monthly", "Yearly"], default="Weekly",
                                        key="rev_gran", label_visibility="collapsed") or "Weekly"
        source = ctx.orders[ctx.orders["order_date"] <= pd.Timestamp(ctx.end)] if gran == "Yearly" else ctx.cur_o
        trend = bi.revenue_trend(source, gran)
        st.plotly_chart(bc.revenue_trend(trend, gran), use_container_width=True, config=PLOTLY_CONFIG)

    c, p = bi.totals(ctx.cur_o), bi.totals(ctx.prev_o)
    change = bi.pct(c["revenue"], p["revenue"])
    with st.container(key="sec_rev_cmp"):
        ui.mini_stats([
            ("Selected period", fmt_value(c["revenue"], "usd0"), ctx.period_label),
            ("Previous period", fmt_value(p["revenue"], "usd0"), ctx.compare_label),
            ("Change", fmt_change(change, "pct"), f"{fmt_value(c['revenue'] - p['revenue'], 'usd0')} difference"),
            ("Avg. daily revenue", fmt_value(c["revenue"] / max(1, (ctx.end - ctx.start).days + 1), "usd0"), "Selected period"),
        ])
        with st.container(key="card_rev_cmp"):
            ui.section_title("Current vs previous period", "Daily revenue lined up by day of the period.")
            st.plotly_chart(bc.period_comparison(bi.revenue_trend(ctx.cur_o, "Daily"), bi.revenue_trend(ctx.prev_o, "Daily")),
                            use_container_width=True, config=PLOTLY_CONFIG)

    a, b = st.columns(2)
    cats = bi.breakdown(ctx.cur_o, ctx.prev_o, "category")
    with a:
        with st.container(key="card_rev_cat"):
            ui.section_title("Revenue by category", "Grey bar: previous period.")
            st.plotly_chart(bc.ranked_bars(cats, "revenue", prev="prev_revenue", colors=[bc.cat_color(n) for n in cats["name"]],
                                           height=ROW_CHART_HEIGHT, legend=False),
                            use_container_width=True, config=PLOTLY_CONFIG)
    with b:
        with st.container(key="card_rev_tree"):
            ui.section_title("Revenue contribution", "Each category and its products, as a share of revenue.")
            prods = bi.product_table(ctx.cur_o, ctx.prev_o)
            st.plotly_chart(bc.contribution_treemap(prods, height=ROW_CHART_HEIGHT), use_container_width=True, config=PLOTLY_CONFIG)

    with st.container(key="card_rev_prod"):
        with ui.section_head("Revenue by product", "Ranked, with the previous period in grey.", "rev_n", ratio=(3, 1)):
            n = st.selectbox("Show", [10, 20, 40], index=0, key="rev_n", label_visibility="collapsed",
                             format_func=lambda x: f"Top {x}" if x < 40 else "All")
        top = prods.head(n)
        st.plotly_chart(bc.ranked_bars(top, "revenue", prev="prev_revenue", colors=[bc.cat_color(c) for c in top["category"]],
                                       legend=False),
                        use_container_width=True, config=PLOTLY_CONFIG)

    a, b = st.columns([3, 2])
    countries = bi.breakdown(ctx.cur_o, ctx.prev_o, "country")
    with a:
        with st.container(key="card_rev_map"):
            ui.section_title("Revenue by country", "Darker teal = more revenue.")
            st.plotly_chart(bc.country_map(countries, height=ROW_CHART_HEIGHT), use_container_width=True, config=PLOTLY_CONFIG)
    with b:
        with st.container(key="card_rev_region"):
            ui.section_title("Revenue by region", "Grey bar: previous period.")
            reg = bi.breakdown(ctx.cur_o, ctx.prev_o, "region")
            st.plotly_chart(bc.ranked_bars(reg, "revenue", prev="prev_revenue", colors=[bc.cat_color(n) for n in reg["name"]],
                                           height=ROW_CHART_HEIGHT, legend=False),
                            use_container_width=True, config=PLOTLY_CONFIG)

    with st.expander(f"Country breakdown ({len(countries)} countries)", icon=":material/public:"):
        ui.data_table(countries, [("name", "Country", "text"), ("revenue", "Revenue", "usd0"), ("prev_revenue", "Previous", "usd0"),
                                  ("growth_pct", "Growth", "growth"), ("share_pct", "Share", "share"), ("orders", "Orders", "int"),
                                  ("customers", "Customers", "int"), ("aov", "AOV", "usd2")])
