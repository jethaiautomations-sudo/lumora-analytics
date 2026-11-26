from __future__ import annotations

import pandas as pd
import streamlit as st

from core import bi
from ui import bi_charts as bc
from ui import components as ui
from ui.theme import PLOTLY_CONFIG, fmt_change, fmt_value

SECTION = "Profitability"
TITLE = "Profitability analysis"
SUBTITLE = "Where the money goes, from gross sales to profit after shipping."


def render(ctx) -> None:
    c, p = bi.totals(ctx.cur_o), bi.totals(ctx.prev_o)
    gm = c["gross_profit"] / c["revenue"] * 100 if c["revenue"] else None
    gm_prev = p["gross_profit"] / p["revenue"] * 100 if p["revenue"] else None
    nm = c["net_profit"] / c["revenue"] * 100 if c["revenue"] else None
    disc = c["discounts"] / c["gross_sales"] * 100 if c["gross_sales"] else None
    ui.mini_stats([
        ("Net revenue", fmt_value(c["revenue"], "usd0"), f"{fmt_change(bi.pct(c['revenue'], p['revenue']), 'pct')} vs previous"),
        ("Gross profit", fmt_value(c["gross_profit"], "usd0"), f"{fmt_change(bi.pct(c['gross_profit'], p['gross_profit']), 'pct')} vs previous"),
        ("Gross margin", fmt_value(gm, "pct1"), f"{fmt_change(gm - gm_prev, 'pts', 1) if gm is not None and gm_prev is not None else '—'} vs previous"),
        ("Profit after shipping", fmt_value(c["net_profit"], "usd0"), f"{fmt_change(bi.pct(c['net_profit'], p['net_profit']), 'pct')} vs previous"),
        ("Margin after shipping", fmt_value(nm, "pct1"), "Of net revenue"),
        ("Discounts given", fmt_value(c["discounts"], "usd0"), f"{fmt_value(disc, 'pct1')} of gross sales"),
    ])

    a, b = st.columns([3, 2])
    with a:
        with st.container(key="card_pf_fall"):
            ui.section_title("From gross sales to profit after shipping", "Selected period.")
            st.plotly_chart(bc.profit_waterfall(c, height=360), use_container_width=True, config=PLOTLY_CONFIG)
    with b:
        with st.container(key="card_pf_trend"):
            ui.section_title("Gross margin by month", "12 months up to the end of the selected period.")
            hist = ctx.orders[(ctx.orders["order_date"] <= pd.Timestamp(ctx.end)) &
                              (ctx.orders["order_date"] > pd.Timestamp(ctx.end) - pd.DateOffset(months=12))]
            st.plotly_chart(bc.margin_trend(bi.revenue_trend(hist, "Monthly"), height=360), use_container_width=True, config=PLOTLY_CONFIG)

    cats = bi.breakdown(ctx.cur_o, ctx.prev_o, "category")
    regs = bi.breakdown(ctx.cur_o, ctx.prev_o, "region")
    h = max(240, 40 * max(len(cats), len(regs)) + 40)   # same height so the two cards line up
    a, b = st.columns(2)
    with a:
        with st.container(key="card_pf_cat"):
            ui.section_title("Profit by category", "Gross profit and profit after shipping; margins on hover.")
            st.plotly_chart(bc.margin_bars(cats, height=h), use_container_width=True, config=PLOTLY_CONFIG)
    with b:
        with st.container(key="card_pf_reg"):
            ui.section_title("Profit by region", "Shipping costs differ by region, so margins after shipping do too.")
            st.plotly_chart(bc.margin_bars(regs, height=h), use_container_width=True, config=PLOTLY_CONFIG)

    # five columns so two tables fit side by side at 1366px
    pcols = [("name", "Product", "text"), ("category", "Category", "dot"), ("revenue", "Revenue", "usd0"),
             ("gross_margin_pct", "Gross %", "pct1"), ("net_margin_pct", "After shipping %", "pct1")]
    pt = bi.product_table(ctx.cur_o, ctx.prev_o)
    sold = pt[pt["revenue"] > 0]
    a, b = st.columns(2)
    with a:
        ui.section_title("Highest-margin products", "10 products keeping the most of each dollar after shipping.")
        ui.data_table(sold.sort_values("net_margin_pct", ascending=False).head(10), pcols)
    with b:
        ui.section_title("Lowest-margin products", "10 products with the lowest margin after shipping.")
        ui.data_table(sold.sort_values("net_margin_pct").head(10), pcols)

    with st.container(key="sec_pf_disc"):
        ui.section_title("Discount impact by segment", "How much discounting each customer segment receives, and what's left as profit.")
        seg = bi.breakdown(ctx.cur_o, ctx.prev_o, "segment")
        ui.data_table(seg, [("name", "Segment", "text"), ("gross_sales", "Gross sales", "usd0"), ("discounts", "Discounts", "usd0"),
                            ("discount_pct", "Discount rate", "pct1"), ("revenue", "Net revenue", "usd0"),
                            ("gross_margin_pct", "Gross margin", "pct1"), ("net_margin_pct", "Margin after shipping", "pct1")])

    with st.expander("How profit is calculated", icon=":material/calculate:"):
        st.markdown("- **Gross profit** = revenue − cost of goods.\n"
                    "- **Profit after shipping** = gross profit − shipping costs.\n"
                    "- Overheads (salaries, rent, software) aren't in the sample data, so they're not deducted.")
