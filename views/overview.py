"""Executive overview: the 10-second view of the business.

Shows only: 6 headline KPIs, one revenue trend, up to 3 highlights, and compact
category/region breakdowns. Everything else lives on its own page.
"""
from __future__ import annotations

import streamlit as st

from core import bi
from ui import bi_charts as bc
from ui import components as ui
from ui.theme import PLOTLY_CONFIG, fmt_value

SECTION = "Overview"
TITLE = "Executive overview"
SUBTITLE = "How the business is doing in the selected period, compared with the period before."

HEADLINE_KPIS = ["revenue", "orders", "aov", "customers", "margin", "target"]


def _highlights(ctx, cats, regs) -> list[dict]:
    """Up to 3 highlights: target pace, biggest growth driver, biggest risk.
    They add context the breakdowns don't show, rather than repeating them."""
    out = []

    reps = bi.salesperson_table(ctx.cur_o, ctx.prev_o, ctx.targets, ctx.start, ctx.end)
    if not reps.empty and reps["target"].sum() > 0:
        ach = reps["revenue"].sum() / reps["target"].sum() * 100
        behind = int((reps["achievement_pct"] < 85).sum())
        gap = reps["revenue"].sum() - reps["target"].sum()
        detail = (f"{fmt_value(abs(gap), 'usd0')} {'ahead of' if gap >= 0 else 'short of'} target"
                  + (f"; {behind} of {len(reps)} salespeople below 85%." if behind else "; every salesperson is at 85% or more."))
        out.append({"level": "positive" if ach >= 100 else ("warning" if ach >= 85 else "critical"),
                    "channel": f"{ach:.0f}% of target", "title": "On track" if ach >= 100 else "Behind target",
                    "detail": detail})

    movers = [(r["name"], r["revenue"] - r["prev_revenue"], r["growth_pct"], kind)
              for df, kind in ((cats, "category"), (regs, "region")) for _, r in df.iterrows() if r["prev_revenue"] > 0]
    if movers:
        name, delta, g, kind = max(movers, key=lambda m: m[1])
        if delta > 0:
            out.append({"level": "positive", "channel": name, "title": "Biggest growth driver",
                        "detail": f"{fmt_value(delta, 'usd0')} more revenue than the previous period ({g:+.1f}%), the largest gain of any {kind}."})

    prods = bi.product_table(ctx.cur_o, ctx.prev_o)
    prods = prods[prods["prev_revenue"] > 0]
    if len(prods):
        prods = prods.assign(delta=prods["revenue"] - prods["prev_revenue"])
        worst = prods.loc[prods["delta"].idxmin()]
        if worst["delta"] < 0:
            out.append({"level": "critical" if worst["growth_pct"] <= -25 else "warning", "channel": worst["name"],
                        "title": "Biggest risk",
                        "detail": f"Revenue down {fmt_value(-worst['delta'], 'usd0')} ({worst['growth_pct']:+.1f}%), the largest drop of any product."})
    return out[:3]


def render(ctx) -> None:
    kpis = bi.executive_kpis(ctx.cur_o, ctx.prev_o, ctx.prev2_o, ctx.targets, ctx.start, ctx.end,
                             ctx.prev_start, ctx.prev_end, ctx.filters.salespeople or None)
    by_key = {k.key: k for k in kpis}
    sparks = bi.weekly_kpi_series(ctx.orders, ctx.end)
    ui.kpi_grid([by_key[k] for k in HEADLINE_KPIS], sparks, "prior", columns=6)

    cats = bi.breakdown(ctx.cur_o, ctx.prev_o, "category")
    regs = bi.breakdown(ctx.cur_o, ctx.prev_o, "region")

    left, right = st.columns([2, 1])
    with left:
        with st.container(key="card_ov_trend"):
            gran = bi.auto_granularity(ctx.start, ctx.end)
            ui.section_title("Revenue trend", f"{gran} revenue, with the previous period as a dotted line.")
            trend = bi.revenue_trend(ctx.cur_o, gran)
            prev = bi.revenue_trend(ctx.prev_o, gran)
            st.plotly_chart(bc.revenue_trend(trend, gran, height=300, show_profit=False, prev=prev),
                            use_container_width=True, config=PLOTLY_CONFIG)
            ui.nav_link("Explore revenue", "revenue", "ov_go_revenue")
    with right:
        with st.container(key="card_ov_high"):
            ui.section_title("Highlights", "What stands out this period.")
            ui.alert_list(_highlights(ctx, cats, regs))

    a, b = st.columns(2)
    with a:
        with st.container(key="card_ov_cat"):
            ui.section_title("Revenue by category", "Share of revenue and change vs the previous period.")
            ui.breakdown_list(cats, bc.cat_color)
            ui.nav_link("Product analytics", "products", "ov_go_products")
    with b:
        with st.container(key="card_ov_region"):
            ui.section_title("Revenue by region", "Share of revenue and change vs the previous period.")
            ui.breakdown_list(regs, bc.cat_color)
            ui.nav_link("Revenue by country", "revenue", "ov_go_regions")
