"""Colours, number formatting and the Plotly theme."""
from __future__ import annotations

import math
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

CSS_FILE = Path(__file__).resolve().parent.parent / "assets" / "style.css"

COLORS = {
    "bg": "#0A0B0E",
    "surface": "#111318",
    "surface2": "#16191F",
    "border": "#23272F",
    "grid": "#1D2128",
    "text": "#E7E9EE",
    "muted": "#8B909C",
    "faint": "#5D626D",
    "teal": "#2DD4BF",
    "blue": "#3B82F6",
    "ok": "#34D399",
    "bad": "#F87171",
    "warn": "#FBBF24",
}

# Consistent colour per channel, accent-led
CHANNEL_COLORS = {
    "Email": "#2DD4BF",
    "Google Ads": "#3B82F6",
    "Organic Search": "#818CF8",
    "Marketplace": "#38BDF8",
    "Paid Social": "#A78BFA",
}
FALLBACK = ["#2DD4BF", "#3B82F6", "#818CF8", "#38BDF8", "#A78BFA", "#64748B"]


def channel_color(name: str, i: int = 0) -> str:
    return CHANNEL_COLORS.get(name, FALLBACK[i % len(FALLBACK)])


def inject_css() -> None:
    css = CSS_FILE.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def register_plotly_template() -> None:
    c = COLORS
    tpl = go.layout.Template()
    tpl.layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, -apple-system, Segoe UI, sans-serif", color=c["muted"], size=12),
        colorway=FALLBACK,
        margin=dict(l=8, r=8, t=8, b=8),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=c["surface2"], bordercolor=c["border"], font=dict(color=c["text"], size=12)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(color=c["muted"], size=12), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, linecolor=c["border"], tickcolor=c["border"], zeroline=False,
                   tickfont=dict(color=c["muted"])),
        yaxis=dict(showgrid=True, gridcolor=c["grid"], zeroline=False, linecolor=c["border"],
                   tickfont=dict(color=c["muted"])),
    )
    pio.templates["lumora"] = tpl
    pio.templates.default = "lumora"


PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}


# ---------- formatting ----------

def _bad(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def fmt_value(v, kind: str) -> str:
    if _bad(v):
        return "—"
    if kind == "usd0":
        return f"${v:,.0f}"
    if kind == "usd2":
        return f"${v:,.2f}"
    if kind == "usdk":
        return f"${v/1000:,.1f}K" if abs(v) >= 1000 else f"${v:,.0f}"
    if kind == "int":
        return f"{v:,.0f}"
    if kind == "pct2":
        return f"{v:.2f}%"
    if kind == "pct1":
        return f"{v:.1f}%"
    if kind == "x2":
        return f"{v:.2f}×"
    return str(v)


def fmt_change(change, mode: str, decimals: int = 1) -> str:
    """Change with a direction arrow instead of a sign: "↑ 13.7%", "↓ 0.57 pts", "– 0.0%".

    Missing values (no comparison possible) stay "—". A change that rounds to zero gets the flat dash.
    """
    if _bad(change):
        return "—"
    places = 1 if mode == "pct" else decimals if mode == "pts" else 2
    a = round(abs(change), places)
    arrow = "–" if a == 0 else ("↑" if change > 0 else "↓")
    unit = "%" if mode == "pct" else " pts" if mode == "pts" else "×"
    return f"{arrow} {a:.{places}f}{unit}"
