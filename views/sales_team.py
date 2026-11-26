from __future__ import annotations

import streamlit as st

from core import bi
from ui import bi_charts as bc
from ui import components as ui
from ui.theme import PLOTLY_CONFIG, fmt_value

SECTION = "Sales team"
TITLE = "Sales performance"
SUBTITLE = "Leaderboard, targets and growth for every salesperson. Targets are monthly, pro-rated to the selected days."

COLS = [("rank", "", "rank"), ("name", "Salesperson", "text"), ("region", "Region", "dot"), ("revenue", "Revenue", "usd0"),
        ("orders", "Orders", "int"), ("aov", "AOV", "usd2"), ("target", "Target", "usd0"),
        ("achievement_pct", "Achievement", "achv"), ("growth_pct", "Growth", "growth")]


def render(ctx) -> None:
    sp = bi.salesperson_table(ctx.cur_o, ctx.prev_o, ctx.targets, ctx.start, ctx.end)
    if sp.empty:
        ui.empty_state("No sales for this selection", "Try a wider date range or clear some filters.")
        return
    team_rev, team_target = sp["revenue"].sum(), sp["target"].sum()
    on_target = int((sp["achievement_pct"] >= 100).sum())
    ui.mini_stats([
        ("Team achievement", fmt_value(team_rev / team_target * 100 if team_target else None, "pct1"),
         f"{fmt_value(team_rev, 'usd0')} of {fmt_value(team_target, 'usd0')} target"),
        ("On or above target", f"{on_target} of {len(sp)}", "Salespeople at 100%+"),
        ("Avg. revenue per salesperson", fmt_value(team_rev / len(sp), "usd0"), "Selected period"),
        ("Avg. order value", fmt_value(team_rev / sp["orders"].sum() if sp["orders"].sum() else None, "usd2"), "Across the team"),
    ])

    # 1. Who's leading and who needs help
    a, b = st.columns(2)
    short = [c for c in COLS if c[0] in ("rank", "name", "revenue", "achievement_pct", "growth_pct")]
    with a:
        ui.section_title("Top 5 performers", "By revenue.")
        ui.data_table(sp.head(5), short)
    with b:
        ui.section_title("Bottom 5 performers", "By revenue.")
        ui.data_table(sp.tail(5).iloc[::-1], short)

    # 2. Targets and growth (same chart height so the cards line up)
    h = max(260, 34 * len(sp) + 40)
    a, b = st.columns(2)
    with a:
        with st.container(key="card_st_target"):
            ui.section_title("Target vs actual", "Outline = target, bar = actual. Green 100%+, amber 85–99%, red below 85%.")
            st.plotly_chart(bc.target_vs_actual(sp, height=h), use_container_width=True, config=PLOTLY_CONFIG)
    with b:
        with st.container(key="card_st_growth"):
            ui.section_title("Sales growth", "Revenue change vs the previous period.")
            st.plotly_chart(bc.growth_bars(sp, height=h), use_container_width=True, config=PLOTLY_CONFIG)

    # 3. Detail on demand
    with st.container(key="sec_st_more"):
        with st.expander(f"Full leaderboard ({len(sp)} salespeople)", icon=":material/leaderboard:"):
            ui.data_table(sp, COLS)
        with st.expander("Compare salespeople by revenue, orders or AOV", icon=":material/bar_chart:"):
            metric = st.segmented_control("Metric", ["Revenue", "Orders", "AOV"], default="Revenue",
                                          key="st_metric", label_visibility="collapsed") or "Revenue"
            field, fmt = {"Revenue": ("revenue", "usd"), "Orders": ("orders", "int"), "AOV": ("aov", "usd")}[metric]
            d = sp.sort_values(field, ascending=False)
            st.plotly_chart(bc.ranked_bars(d, field, fmt=fmt, colors=[bc.cat_color(r) for r in d["region"]]),
                            use_container_width=True, config=PLOTLY_CONFIG)
