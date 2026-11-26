"""Plotly charts for the sales BI pages. Same theme and palette as ui/charts.py."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ui.charts import _hex_to_rgba
from ui.theme import COLORS, FALLBACK, fmt_change

C = COLORS
CATEGORY_COLORS = {"Furniture": "#2DD4BF", "Decor": "#3B82F6", "Bedding & Bath": "#818CF8",
                   "Kitchen & Dining": "#38BDF8", "Outdoor": "#A78BFA", "Lighting": "#5EEAD4"}
REGION_COLORS = {"North America": "#2DD4BF", "Europe": "#3B82F6", "Asia Pacific": "#818CF8"}

HOVER_FMT = {"usd": "$%{x:,.0f}", "int": "%{x:,.0f}", "pct": "%{x:.1f}%"}
TICK = {"usd": dict(tickprefix="$", tickformat="~s"), "int": dict(tickformat="~s"), "pct": dict(ticksuffix="%")}


def cat_color(name: str, i: int = 0) -> str:
    return CATEGORY_COLORS.get(name, REGION_COLORS.get(name, FALLBACK[i % len(FALLBACK)]))


def _label(v: float, fmt: str) -> str:
    if fmt == "usd":
        return f"${v/1e6:,.2f}M" if abs(v) >= 1e6 else (f"${v/1e3:,.1f}K" if abs(v) >= 1e3 else f"${v:,.0f}")
    if fmt == "pct":
        return f"{v:.1f}%"
    return f"{v:,.0f}"


# ---------- revenue ----------

def revenue_trend(trend: pd.DataFrame, freq_label: str, height: int = 340, show_profit: bool = True,
                  prev: pd.DataFrame | None = None) -> go.Figure:
    fig = go.Figure()
    tick = {"Daily": "%d %b", "Weekly": "%d %b", "Monthly": "%b %Y", "Yearly": "%Y"}[freq_label]
    if freq_label in ("Monthly", "Yearly") or len(trend) <= 20:
        fig.add_trace(go.Bar(x=trend["period"], y=trend["revenue"], name="Revenue",
                             marker=dict(color=_hex_to_rgba(C["teal"], 0.75), line=dict(width=0)),
                             hovertemplate=f"%{{x|{tick}}}<br>Revenue: $%{{y:,.0f}}<extra></extra>"))
    else:
        fig.add_trace(go.Scatter(x=trend["period"], y=trend["revenue"], name="Revenue", mode="lines",
                                 line=dict(color=C["teal"], width=2.2), fill="tozeroy",
                                 fillcolor=_hex_to_rgba(C["teal"], 0.08),
                                 hovertemplate=f"%{{x|{tick}}}<br>Revenue: $%{{y:,.0f}}<extra></extra>"))
    if show_profit:
        fig.add_trace(go.Scatter(x=trend["period"], y=trend["gross_profit"], name="Gross profit", mode="lines",
                                 line=dict(color=C["blue"], width=1.8, dash="dot"),
                                 hovertemplate="Gross profit: $%{y:,.0f}<extra></extra>"))
    if prev is not None and len(prev):
        n = min(len(prev), len(trend))
        fig.add_trace(go.Scatter(x=trend["period"].iloc[:n], y=prev["revenue"].values[:n], name="Previous period",
                                 mode="lines", line=dict(color=C["faint"], width=1.5, dash="dot"),
                                 customdata=prev["period"].dt.strftime("%d %b %Y").values[:n],
                                 hovertemplate="Previous (%{customdata}): $%{y:,.0f}<extra></extra>"))
    fig.update_layout(height=height, bargap=0.25, yaxis=TICK["usd"], xaxis=dict(tickformat=tick), hovermode="x unified")
    return fig


def period_comparison(cur: pd.DataFrame, prev: pd.DataFrame, height: int = 300) -> go.Figure:
    """Daily revenue, current vs previous period, aligned by day number."""
    fig = go.Figure()
    n = min(len(cur), len(prev))
    x = list(range(1, len(cur) + 1))
    if n:
        fig.add_trace(go.Scatter(x=x[:n], y=prev["revenue"].values[:n], name="Previous period", mode="lines",
                                 line=dict(color=C["faint"], width=1.6, dash="dot"),
                                 customdata=prev["period"].dt.strftime("%d %b %Y").values[:n],
                                 hovertemplate="Previous (%{customdata}): $%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=x, y=cur["revenue"], name="Selected period", mode="lines",
                             line=dict(color=C["teal"], width=2.4),
                             customdata=cur["period"].dt.strftime("%d %b %Y"),
                             hovertemplate="Selected (%{customdata}): $%{y:,.0f}<extra></extra>"))
    fig.update_layout(height=height, yaxis=TICK["usd"], xaxis=dict(title=dict(text="Day of period", font=dict(size=11))))
    return fig


def ranked_bars(df: pd.DataFrame, value: str, label: str = "name", fmt: str = "usd", height: int | None = None,
                color: str | None = None, colors: list[str] | None = None, prev: str | None = None,
                extra: str | None = None, extra_label: str = "", extra_fmt: str = "pct",
                legend: bool | None = None) -> go.Figure:
    """Horizontal ranked bars, biggest at the top. legend=None shows it only when a previous-period bar is drawn."""
    d = df.iloc[::-1]
    height = height or max(220, 34 * len(d) + 40)
    fig = go.Figure()
    if prev is not None:
        fig.add_trace(go.Bar(y=d[label], x=d[prev], orientation="h", name="Previous period",
                             marker=dict(color=C["border"]), hovertemplate=f"%{{y}}<br>Previous: {HOVER_FMT[fmt]}<extra></extra>"))
    cd = d[extra] if extra else None
    extra_hover = ""
    if extra:
        extra_hover = f"<br>{extra_label}: " + ("%{customdata:.1f}%" if extra_fmt == "pct" else "%{customdata:,.0f}")
    fig.add_trace(go.Bar(
        y=d[label], x=d[value], orientation="h", name="Selected period",
        marker=dict(color=colors[::-1] if colors else (color or C["teal"]), line=dict(width=0)),
        text=[_label(v, fmt) for v in d[value]], textposition="outside", cliponaxis=False,
        textfont=dict(color=C["text"], size=11), customdata=cd,
        hovertemplate=f"%{{y}}<br>{HOVER_FMT[fmt]}{extra_hover}<extra></extra>"))
    fig.update_layout(height=height, barmode="group", bargap=0.3, bargroupgap=0.06, hovermode="closest",
                      showlegend=(prev is not None) if legend is None else legend, margin=dict(l=8, r=56, t=8, b=8),
                      xaxis=dict(showgrid=True, gridcolor=C["grid"], **TICK[fmt]), yaxis=dict(showgrid=False))
    return fig


def contribution_treemap(df_cat_prod: pd.DataFrame, height: int = 380) -> go.Figure:
    """Category -> product revenue contribution."""
    cats = df_cat_prod.groupby("category")["revenue"].sum()
    total = cats.sum()
    labels, parents, values, colors = ["All revenue"], [""], [total], [C["surface2"]]
    for i, (cat, rev) in enumerate(cats.sort_values(ascending=False).items()):
        labels.append(cat); parents.append("All revenue"); values.append(rev); colors.append(_hex_to_rgba(cat_color(cat, i), 0.55))
        for _, r in df_cat_prod[df_cat_prod["category"] == cat].iterrows():
            labels.append(r["name"]); parents.append(cat); values.append(r["revenue"]); colors.append(_hex_to_rgba(cat_color(cat, i), 0.30))
    parent_ids = ["" if not p else (p if p == "All revenue" else f"All revenue/{p}") for p in parents]
    ids = ["All revenue"] + [f"All revenue/{l}" if p == "All revenue" else f"All revenue/{p}/{l}" for l, p in zip(labels[1:], parents[1:])]
    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parent_ids, values=values, branchvalues="total",
        marker=dict(colors=colors, line=dict(color=C["bg"], width=1.5)),
        texttemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percentRoot:.1%}",
        textfont=dict(color=C["text"], size=12),
        hovertemplate="%{label}<br>$%{value:,.0f} · %{percentRoot:.1%} of total<extra></extra>",
        tiling=dict(pad=3), root=dict(color=C["surface"]), pathbar=dict(visible=False),
    ))
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=0, b=0))
    return fig


def country_map(by_country: pd.DataFrame, height: int = 340) -> go.Figure:
    fig = go.Figure(go.Choropleth(
        locations=by_country["name"], locationmode="country names", z=by_country["revenue"],
        colorscale=[[0, "#13302D"], [0.5, "#1E7F74"], [1, C["teal"]]], marker_line_color=C["bg"], marker_line_width=0.5,
        colorbar=dict(thickness=8, len=0.6, tickprefix="$", tickformat="~s", tickfont=dict(color=C["muted"]), outlinewidth=0),
        hovertemplate="%{location}<br>$%{z:,.0f}<extra></extra>",
    ))
    fig.update_geos(showframe=False, showcoastlines=False, showcountries=True, countrycolor=C["border"],
                    landcolor=C["surface2"], bgcolor="rgba(0,0,0,0)", showocean=False, showlakes=False,
                    projection_type="natural earth")
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=0, b=0))
    return fig


def donut(labels, values, colors, center_title: str, center_value: str, height: int = 300) -> go.Figure:
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.7, sort=False, textinfo="none",
                           marker=dict(colors=colors, line=dict(color=C["bg"], width=2)),
                           hovertemplate="%{label}<br>%{value:,.0f} · %{percent}<extra></extra>"))
    fig.update_layout(height=height, legend=dict(orientation="v", x=1, y=0.5, xanchor="left", yanchor="middle"),
                      annotations=[dict(text=f"<b>{center_value}</b><br><span style='font-size:11px;color:{C['muted']}'>{center_title}</span>",
                                        showarrow=False, font=dict(size=18, color=C["text"]))])
    return fig


# ---------- sales team ----------

def target_vs_actual(sp: pd.DataFrame, height: int | None = None) -> go.Figure:
    d = sp.sort_values("revenue")
    height = height or max(260, 34 * len(d) + 40)
    colors = [C["ok"] if a >= 100 else (C["warn"] if a >= 85 else C["bad"]) for a in d["achievement_pct"].fillna(0)]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=d["name"], x=d["target"], orientation="h", name="Target",
                         marker=dict(color="rgba(255,255,255,0.06)", line=dict(color=C["border"], width=1)),
                         hovertemplate="%{y}<br>Target: $%{x:,.0f}<extra></extra>"))
    fig.add_trace(go.Bar(y=d["name"], x=d["revenue"], orientation="h", name="Actual", width=0.45,
                         marker=dict(color=colors), customdata=d["achievement_pct"],
                         text=[f"{a:.0f}%" if pd.notna(a) else "" for a in d["achievement_pct"]], textposition="outside",
                         textfont=dict(color=C["text"], size=11), cliponaxis=False,
                         hovertemplate="%{y}<br>Actual: $%{x:,.0f}<br>Achievement: %{customdata:.1f}%<extra></extra>"))
    fig.update_layout(height=height, barmode="overlay", bargap=0.25, hovermode="closest", margin=dict(l=8, r=48, t=8, b=8),
                      xaxis=dict(showgrid=True, gridcolor=C["grid"], tickprefix="$", tickformat="~s"), yaxis=dict(showgrid=False))
    return fig


def growth_bars(df: pd.DataFrame, label: str = "name", value: str = "growth_pct", height: int | None = None) -> go.Figure:
    d = df.dropna(subset=[value]).sort_values(value)
    height = height or max(260, 30 * len(d) + 40)
    labels = [fmt_change(v, "pct") for v in d[value]]   # "↑ 13.7%" / "↓ 6.1%": Plotly formats can't add arrows
    fig = go.Figure(go.Bar(
        y=d[label], x=d[value], orientation="h",
        marker=dict(color=[C["ok"] if v >= 0 else C["bad"] for v in d[value]]),
        text=labels, textposition="outside", cliponaxis=False, customdata=labels,
        textfont=dict(color=C["text"], size=11), hovertemplate="%{y}<br>Growth: %{customdata}<extra></extra>"))
    # headroom on both sides so outside labels ("↓ 12.9%") don't run into the names or the edge
    lo, hi = min(0.0, d[value].min()) if len(d) else 0.0, max(0.0, d[value].max()) if len(d) else 1.0
    pad = (hi - lo) or 1.0
    fig.update_layout(height=height, hovermode="closest", margin=dict(l=8, r=48, t=8, b=8),
                      xaxis=dict(ticksuffix="%", showgrid=True, gridcolor=C["grid"], zeroline=True, zerolinecolor=C["border"],
                                 range=[lo - 0.2 * pad if lo < 0 else lo, hi + 0.12 * pad]),
                      yaxis=dict(showgrid=False))
    return fig


# ---------- products ----------

def product_scatter(pt: pd.DataFrame, height: int = 380) -> go.Figure:
    fig = go.Figure()
    for i, cat in enumerate(sorted(pt["category"].unique())):
        d = pt[pt["category"] == cat]
        fig.add_trace(go.Scatter(
            x=d["revenue"], y=d["gross_margin_pct"], mode="markers", name=cat,
            marker=dict(size=(d["units"] / max(pt["units"].max(), 1)) ** 0.5 * 34 + 6, color=cat_color(cat, i),
                        opacity=0.8, line=dict(color=C["bg"], width=1)),
            text=d["name"], customdata=d[["units", "gross_profit"]].values,
            hovertemplate="%{text}<br>Revenue: $%{x:,.0f}<br>Gross margin: %{y:.1f}%<br>Units: %{customdata[0]:,.0f}"
                          "<br>Gross profit: $%{customdata[1]:,.0f}<extra></extra>"))
    fig.update_layout(height=height, hovermode="closest",
                      xaxis=dict(title=dict(text="Revenue", font=dict(size=11)), tickprefix="$", tickformat="~s", showgrid=True, gridcolor=C["grid"]),
                      yaxis=dict(title=dict(text="Gross margin", font=dict(size=11)), ticksuffix="%"))
    return fig


# ---------- customers ----------

def new_vs_returning(trend: pd.DataFrame, height: int = 320) -> go.Figure:
    fig = go.Figure()
    for t, color in (("Returning", C["blue"]), ("New", C["teal"])):
        d = trend[trend["type"] == t]
        fig.add_trace(go.Bar(x=d["period"], y=d["customers"], name=f"{t} customers",
                             marker=dict(color=_hex_to_rgba(color, 0.8)), customdata=d["revenue"],
                             hovertemplate=f"{t}: %{{y:,.0f}} customers · $%{{customdata:,.0f}}<extra></extra>"))
    fig.update_layout(height=height, barmode="stack", bargap=0.3, xaxis=dict(tickformat="%b %Y"), yaxis=dict(tickformat="~s"))
    return fig


def frequency_bars(freq: pd.Series, cap: int, height: int = 300) -> go.Figure:
    labels = [f"{i}+" if i == cap else str(i) for i in freq.index]
    fig = go.Figure(go.Bar(x=labels, y=freq.values, marker=dict(color=_hex_to_rgba(C["teal"], 0.75)),
                           text=[f"{v:,}" for v in freq.values], textposition="outside", cliponaxis=False,
                           textfont=dict(color=C["text"], size=11),
                           hovertemplate="%{x} orders: %{y:,} customers<extra></extra>"))
    fig.update_layout(height=height, hovermode="closest", bargap=0.35,
                      xaxis=dict(title=dict(text="Orders per customer", font=dict(size=11)), type="category"),
                      yaxis=dict(tickformat="~s"))
    return fig


# ---------- profitability ----------

def profit_waterfall(t: dict, height: int = 360) -> go.Figure:
    steps = [("Gross sales", t["gross_sales"], "absolute"), ("Discounts", -t["discounts"], "relative"),
             ("Net revenue", t["revenue"], "total"), ("COGS", -t["cogs"], "relative"),
             ("Gross profit", t["gross_profit"], "total"), ("Shipping", -t["shipping"], "relative"),
             ("Net profit", t["net_profit"], "total")]
    fig = go.Figure(go.Waterfall(
        x=[s[0] for s in steps], y=[s[1] for s in steps], measure=[s[2] for s in steps],
        text=[_label(abs(s[1]), "usd") for s in steps], textposition="outside", cliponaxis=False,
        textfont=dict(color=C["text"], size=11),
        increasing=dict(marker=dict(color=C["teal"])), decreasing=dict(marker=dict(color=_hex_to_rgba(C["bad"], 0.8))),
        totals=dict(marker=dict(color=C["blue"])), connector=dict(line=dict(color=C["border"], width=1)),
        hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
    fig.update_layout(height=height, hovermode="closest", yaxis=TICK["usd"], showlegend=False, margin=dict(l=8, r=8, t=24, b=8))
    return fig


def margin_bars(df: pd.DataFrame, height: int | None = None) -> go.Figure:
    d = df.sort_values("gross_profit")
    height = height or max(240, 40 * len(d) + 40)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=d["name"], x=d["gross_profit"], orientation="h", name="Gross profit",
                         marker=dict(color=_hex_to_rgba(C["teal"], 0.8)), customdata=d["gross_margin_pct"],
                         hovertemplate="%{y}<br>Gross profit: $%{x:,.0f}<br>Margin: %{customdata:.1f}%<extra></extra>"))
    fig.add_trace(go.Bar(y=d["name"], x=d["net_profit"], orientation="h", name="Net profit",
                         marker=dict(color=_hex_to_rgba(C["blue"], 0.8)), customdata=d["net_margin_pct"],
                         hovertemplate="%{y}<br>Net profit: $%{x:,.0f}<br>Margin: %{customdata:.1f}%<extra></extra>"))
    fig.update_layout(height=height, barmode="group", bargap=0.28, hovermode="closest",
                      xaxis=dict(tickprefix="$", tickformat="~s", showgrid=True, gridcolor=C["grid"]), yaxis=dict(showgrid=False))
    return fig


def margin_trend(trend: pd.DataFrame, height: int = 300) -> go.Figure:
    d = trend.copy()
    d["margin"] = d["gross_profit"] / d["revenue"].where(d["revenue"] > 0) * 100
    fig = go.Figure(go.Scatter(x=d["period"], y=d["margin"], mode="lines+markers", line=dict(color=C["teal"], width=2.2),
                               marker=dict(size=5), hovertemplate="%{x|%b %Y}<br>Gross margin: %{y:.1f}%<extra></extra>"))
    fig.update_layout(height=height, yaxis=dict(ticksuffix="%"), xaxis=dict(tickformat="%b %Y"), hovermode="closest")
    return fig
