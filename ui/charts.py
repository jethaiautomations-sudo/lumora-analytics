"""Plotly chart builders. Each takes a DataFrame from core/metrics.py."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ui.theme import COLORS, channel_color

C = COLORS


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def revenue_trend(cur: pd.DataFrame, prev: pd.DataFrame, height: int = 320) -> go.Figure:
    """Daily revenue for the selected period, with the previous period overlaid by day number."""
    fig = go.Figure()
    n = min(len(cur), len(prev))
    if n:
        fig.add_trace(go.Scatter(
            x=cur["date"].iloc[:n], y=prev["revenue_usd"].iloc[:n].values,
            name="Previous period", mode="lines",
            line=dict(color=C["faint"], width=1.5, dash="dot"),
            customdata=prev["date"].dt.strftime("%d %b").iloc[:n].values,
            hovertemplate="Previous (%{customdata}): $%{y:,.0f}<extra></extra>",
        ))
    fig.add_trace(go.Scatter(
        x=cur["date"], y=cur["revenue_usd"], name="Revenue", mode="lines+markers" if len(cur) <= 31 else "lines",
        line=dict(color=C["teal"], width=2.4), marker=dict(size=5),
        fill="tozeroy", fillcolor=_hex_to_rgba(C["teal"], 0.08),
        hovertemplate="Revenue: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(height=height, yaxis=dict(tickprefix="$", tickformat="~s"),
                      xaxis=dict(tickformat="%d %b"))
    return fig


def weekly_metric(weekly: pd.DataFrame, field: str, label: str, fmt: str, highlight_end=None, height: int = 300) -> go.Figure:
    tick = {"usd": dict(tickprefix="$", tickformat="~s"), "pct": dict(ticksuffix="%"), "x": dict(ticksuffix="×"), "int": dict(tickformat="~s")}[fmt]
    hover = {"usd": "$%{y:,.0f}", "pct": "%{y:.2f}%", "x": "%{y:.2f}×", "int": "%{y:,.0f}"}[fmt]
    colors = [C["teal"] if (highlight_end is not None and we == highlight_end) else _hex_to_rgba(C["blue"], 0.55)
              for we in weekly["week_end"]]
    fig = go.Figure(go.Bar(
        x=weekly["week_end"], y=weekly[field], marker=dict(color=colors, line=dict(width=0)),
        customdata=weekly["week_start"].dt.strftime("%d %b"),
        hovertemplate=f"Week %{{customdata}} – %{{x|%d %b}}<br>{label}: {hover}<extra></extra>",
        name=label,
    ))
    fig.update_layout(height=height, yaxis=tick, hovermode="closest", bargap=0.25, showlegend=False,
                      xaxis=dict(tickformat="%b"))
    return fig


def channel_compare(ch: pd.DataFrame, height: int = 320) -> go.Figure:
    d = ch.sort_values("Revenue")
    fig = go.Figure()
    fig.add_trace(go.Bar(y=d["Channel"], x=d["Revenue (prev)"], orientation="h", name="Previous period",
                         marker=dict(color=C["border"]), hovertemplate="%{y}<br>Previous: $%{x:,.0f}<extra></extra>"))
    fig.add_trace(go.Bar(y=d["Channel"], x=d["Revenue"], orientation="h", name="Selected period",
                         marker=dict(color=[channel_color(c) for c in d["Channel"]]),
                         text=[f"${v/1000:,.1f}K" for v in d["Revenue"]], textposition="outside",
                         textfont=dict(color=C["text"], size=11), cliponaxis=False,
                         hovertemplate="%{y}<br>Selected: $%{x:,.0f}<extra></extra>"))
    fig.update_layout(height=height, barmode="group", bargap=0.3, bargroupgap=0.08, hovermode="closest",
                      xaxis=dict(showgrid=True, gridcolor=C["grid"], tickprefix="$", tickformat="~s"),
                      yaxis=dict(showgrid=False), margin=dict(l=8, r=40, t=8, b=8))
    return fig


def channel_mix(ch: pd.DataFrame, height: int = 320) -> go.Figure:
    d = ch[ch["Revenue"] > 0]
    fig = go.Figure(go.Pie(
        labels=d["Channel"], values=d["Revenue"], hole=0.68, sort=False,
        marker=dict(colors=[channel_color(c, i) for i, c in enumerate(d["Channel"])], line=dict(color=C["bg"], width=2)),
        textinfo="none", hovertemplate="%{label}<br>$%{value:,.0f} · %{percent}<extra></extra>",
    ))
    total = d["Revenue"].sum()
    fig.update_layout(height=height, showlegend=True, legend=dict(orientation="v", x=1, y=0.5, xanchor="left", yanchor="middle"),
                      annotations=[dict(text=f"<b>${total/1000:,.1f}K</b><br><span style='font-size:11px;color:{C['muted']}'>revenue</span>",
                                        showarrow=False, font=dict(size=18, color=C["text"]))],
                      margin=dict(l=8, r=8, t=8, b=8))
    return fig


def spend_vs_roas(weekly_paid: pd.DataFrame, height: int = 320) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=weekly_paid["week_end"], y=weekly_paid["ad_spend"], name="Ad spend",
                         marker=dict(color=_hex_to_rgba(C["blue"], 0.55)),
                         hovertemplate="Ad spend: $%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=weekly_paid["week_end"], y=weekly_paid["roas"], name="ROAS", yaxis="y2", mode="lines+markers",
                             line=dict(color=C["teal"], width=2.2), marker=dict(size=4),
                             hovertemplate="ROAS: %{y:.2f}×<extra></extra>"))
    fig.update_layout(height=height, bargap=0.3,
                      yaxis=dict(tickprefix="$", tickformat="~s", title=None),
                      yaxis2=dict(overlaying="y", side="right", ticksuffix="×", showgrid=False, zeroline=False,
                                  tickfont=dict(color=C["muted"])),
                      xaxis=dict(tickformat="%b"))
    return fig


def channel_stacked(weekly_ch: pd.DataFrame, height: int = 340) -> go.Figure:
    fig = go.Figure()
    order = weekly_ch.groupby("channel")["revenue"].sum().sort_values(ascending=False).index
    for i, ch in enumerate(order):
        d = weekly_ch[weekly_ch["channel"] == ch]
        color = channel_color(ch, i)
        fig.add_trace(go.Scatter(x=d["week_end"], y=d["revenue"], name=ch, mode="lines", stackgroup="one",
                                 line=dict(width=1, color=color), fillcolor=_hex_to_rgba(color, 0.35),
                                 hovertemplate=f"{ch}: $%{{y:,.0f}}<extra></extra>"))
    fig.update_layout(height=height, yaxis=dict(tickprefix="$", tickformat="~s"), xaxis=dict(tickformat="%b"))
    return fig
