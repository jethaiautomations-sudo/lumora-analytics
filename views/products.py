from __future__ import annotations

import streamlit as st

from core import bi
from ui import bi_charts as bc
from ui import components as ui
from ui.theme import PLOTLY_CONFIG, fmt_change, fmt_value

SECTION = "Products"
TITLE = "Product analytics"
SUBTITLE = "Best and worst sellers, revenue and profit leaders, category performance and products in decline."

METRICS = {"Units sold": ("units", "int"), "Revenue": ("revenue", "usd0"), "Gross profit": ("gross_profit", "usd0")}


def render(ctx) -> None:
    pt = bi.product_table(ctx.cur_o, ctx.prev_o)
    if pt.empty:
        ui.empty_state("No product sales", "Try a wider date range or clear some filters.")
        return
    c, p = bi.totals(ctx.cur_o), bi.totals(ctx.prev_o)
    dec = bi.declining_products(ctx.orders, ctx.end)
    ui.mini_stats([
        ("Units sold", fmt_value(c["units"], "int"), f"{fmt_change(bi.pct(c['units'], p['units']), 'pct')} vs previous period"),
        ("Products sold", f"{int((pt['units'] > 0).sum())}", f"across {pt['category'].nunique()} categories"),
        ("Units per order", f"{c['units'] / c['orders']:.2f}" if c["orders"] else "—", "Average basket size"),
        ("Declining products", f"{len(dec)}", "Down 10%+ year on year"),
    ])

    # 1. Best and worst sellers
    with st.container(key="sec_pr_best"):
        with ui.section_head("Best and worst sellers", "Top 10 and bottom 10 products for the selected metric.", "pr_metric"):
            metric = st.segmented_control("Rank by", list(METRICS), default="Units sold", key="pr_metric",
                                          label_visibility="collapsed") or "Units sold"
        field, fmt = METRICS[metric]
        ranked = pt.sort_values(field, ascending=False).reset_index(drop=True)
        ranked["rank"] = ranked.index + 1
        cols = [("rank", "", "rank"), ("name", "Product", "text"), ("category", "Category", "dot"),
                (field, metric, fmt), ("growth_pct", "Growth", "growth")]
        a, b = st.columns(2)
        with a:
            ui.section_title("Top 10")
            ui.data_table(ranked.head(10), cols)
        with b:
            ui.section_title("Bottom 10")
            ui.data_table(ranked.tail(10).iloc[::-1], cols)

    # 2. Categories: the scatter is sized to the table so both cards line up
    cats = bi.breakdown(ctx.cur_o, ctx.prev_o, "category")
    a, b = st.columns(2)
    with a:
        with st.container(key="card_pr_cat"):
            ui.section_title("Category performance", "Revenue, growth, units and margin by category.")
            ui.data_table(cats, [("name", "Category", "dot"), ("revenue", "Revenue", "usd0"), ("growth_pct", "Growth", "growth"),
                                 ("units", "Units", "int"), ("gross_margin_pct", "Margin", "pct1")])
    with b:
        with st.container(key="card_pr_scatter"):
            ui.section_title("Revenue vs margin", "Bubble size = units sold. Top right = high revenue and high margin.")
            st.plotly_chart(bc.product_scatter(pt, height=max(300, 46 + 42 * len(cats))),
                            use_container_width=True, config=PLOTLY_CONFIG)

    # 3. Declining products
    with st.container(key="sec_pr_decline"):
        ui.section_title("Products with declining sales",
                         "Last 3 months vs the same 3 months a year earlier, down 10% or more. "
                         "Comparing year on year means normal seasonal dips aren't flagged.")
        if dec.empty:
            ui.empty_state("No declining products", "No product is down 10% or more year on year.")
        else:
            d = dec.rename(columns={"recent": "last_3m", "prior": "same_3m_ly"})
            ui.data_table(d, [("name", "Product", "text"), ("category", "Category", "dot"),
                              ("last_3m", "Last 3 months", "usd0"), ("same_3m_ly", "Same months last year", "usd0"),
                              ("change_pct", "Change", "growth"), ("spark", "Last 12 months", "spark")])
            st.caption(f"{len(d)} product(s) flagged, {fmt_value(d['same_3m_ly'].sum() - d['last_3m'].sum(), 'usd0')} "
                       "less revenue than a year ago.")

    # 4. Detail on demand
    with st.expander(f"Units sold for all {len(pt)} products", icon=":material/inventory_2:"):
        d = pt.sort_values("units", ascending=False)
        st.plotly_chart(bc.ranked_bars(d, "units", fmt="int", colors=[bc.cat_color(c) for c in d["category"]]),
                        use_container_width=True, config=PLOTLY_CONFIG)
