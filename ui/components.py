"""Reusable UI pieces rendered as HTML (styled by assets/style.css).

Every value shown here is passed in from core/metrics.py; nothing is hardcoded.
HTML is built without leading indentation so Streamlit's markdown parser
doesn't turn it into code blocks.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from core.metrics import KPI
from ui.theme import COLORS, channel_color, fmt_change, fmt_value

ASSETS = Path(__file__).resolve().parent.parent / "assets"
LOGO_FILE = ASSETS / "logo.png" if (ASSETS / "logo.png").exists() else ASSETS / "logo.svg"


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


# ---------- sidebar ----------

@lru_cache(maxsize=1)
def _logo_img() -> str:
    """The brand logo (assets/logo.png, or logo.svg) as an <img> with a base64 data URI."""
    if not LOGO_FILE.exists():
        return '<div class="lm-logo lm-logo-fallback">L</div>'
    data = base64.b64encode(LOGO_FILE.read_bytes()).decode()
    mime = "image/png" if LOGO_FILE.suffix == ".png" else "image/svg+xml"
    return f'<img class="lm-logo" src="data:{mime};base64,{data}" width="36" height="36" alt="Lumora logo">'


NAV_GROUPS = [
    ("Sales analytics", [
        ("overview", "Overview", ":material/space_dashboard:"),
        ("revenue", "Revenue", ":material/monitoring:"),
        ("sales_team", "Sales team", ":material/groups:"),
        ("products", "Products", ":material/inventory_2:"),
        ("customers", "Customers", ":material/person_search:"),
        ("profitability", "Profitability", ":material/savings:"),
    ]),
    ("Marketing & AI", [
        ("channels", "Marketing channels", ":material/hub:"),
        ("ai_report", "AI report", ":material/auto_awesome:"),
        ("automation", "Automation", ":material/account_tree:"),
    ]),
    ("Data", [
        ("explorer", "Data explorer", ":material/table_rows:"),
    ]),
]


def sidebar(active: str, data_through: str, source: str) -> str:
    """Renders the navigation and returns the selected page key."""
    with st.sidebar:
        html(
            f'<div class="lm-brand">{_logo_img()}'
            '<div><div class="lm-brand-name">Lumora Analytics</div>'
            '<div class="lm-brand-sub">Lumora Home · Demo workspace</div></div></div>'
        )
        for group, items in NAV_GROUPS:
            html(f'<div class="lm-nav-label">{escape(group)}</div>')
            for key, label, icon in items:
                if st.button(label, key=f"nav_{key}", icon=icon,
                             type="primary" if key == active else "secondary",
                             use_container_width=True):
                    st.session_state.page = key
                    st.rerun()
        html(f'<div class="lm-status"><span class="lm-dot"></span>{escape(source)} · data through {escape(data_through)}</div>')
        html(
            '<div class="lm-profile"><div class="lm-avatar">JD</div>'
            '<div><div class="lm-profile-name">Jeth Divina</div>'
            '<div class="lm-profile-role">Analytics admin</div></div></div>'
        )
    return st.session_state.page


# ---------- header ----------

def page_header(section: str, title: str, subtitle: str, period_label: str, compare_label: str) -> None:
    html(
        '<div class="lm-header"><div>'
        f'<div class="lm-crumb">Lumora Home / <b>{escape(section)}</b></div>'
        f'<div class="lm-title" role="heading" aria-level="1">{escape(title)}</div>'
        f'<p class="lm-subtitle">{escape(subtitle)}</p></div>'
        f'<div class="lm-period"><b>{escape(period_label)}</b><span>vs {escape(compare_label)}</span></div>'
        '</div>'
    )


def section_title(title: str, subtitle: str = "") -> None:
    sub = f'<p class="lm-section-sub">{escape(subtitle)}</p>' if subtitle else ""
    html(f'<div class="lm-section-head"><p class="lm-section-title">{escape(title)}</p>{sub}</div>')


def section_head(title: str, subtitle: str, key: str, ratio: tuple[float, float] = (3, 2)):
    """Section title on the left and a right-aligned control slot on the right.

    Returns the control container; put the toggle/selector in it with `with`.
    """
    head, ctrl = st.columns(ratio, vertical_alignment="center")
    with head:
        section_title(title, subtitle)
    return ctrl.container(key=f"ctrl_{key}")


# ---------- KPI cards ----------

def _sparkline(values: list[float], color: str, w: int = 200, h: int = 34) -> str:
    vals = [v for v in values if v is not None and v == v]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    step = w / (len(vals) - 1)
    pts = [(i * step, h - 3 - (v - lo) / span * (h - 6)) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"0,{h} " + line + f" {w},{h}"
    gid = f"g{abs(hash((color, line))) % 10**8}"
    lx, ly = pts[-1]
    return (
        f'<svg class="lm-spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
        f'<defs><linearGradient id="{gid}" x1="0" x2="0" y1="0" y2="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity=".22"/><stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
        f'<polygon points="{area}" fill="url(#{gid})"/>'
        f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="1.6" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.4" fill="{color}"/></svg>'
    )


def kpi_grid(kpis: list[KPI], sparks: dict[str, list[float]], compare_label: str, columns: int | None = None) -> None:
    cards = []
    for k in kpis:
        dec = 1 if k.key in ("return_rate", "growth", "target") else 2
        chg = fmt_change(k.change, k.change_mode, dec)
        cls = "flat" if k.is_good is None else ("good" if k.is_good else "bad")
        color = COLORS["teal"] if k.is_good is not False else COLORS["bad"]
        cards.append(
            f'<div class="lm-card lm-kpi" title="{escape(k.hint)}">'
            f'<div class="lm-kpi-label"><span>{escape(k.label)}</span></div>'
            f'<div class="lm-kpi-value">{fmt_value(k.value, k.fmt)}</div>'
            f'<div class="lm-kpi-foot"><span class="lm-delta {cls}">{chg}</span>'
            f'<span class="lm-vs">vs {escape(compare_label)}</span></div>'
            f'{_sparkline(sparks.get(k.key, []), color)}</div>'
        )
    cls = f"lm-kpis lm-kpis-{columns}" if columns else "lm-kpis"
    html(f'<div class="{cls}">' + "".join(cards) + "</div>")


# ---------- alerts ----------

def alert_list(items: list[dict]) -> None:
    if not items:
        html('<div class="lm-empty"><b>No alerts</b>Every channel is within the normal range for this period.</div>')
        return
    rows = "".join(
        f'<div class="lm-alert {escape(a["level"])}"><div class="lm-alert-bar"></div><div>'
        f'<div class="lm-alert-title">{escape(a["title"])} <span>· {escape(a["channel"])}</span></div>'
        f'<div class="lm-alert-detail">{escape(a["detail"])}</div></div></div>'
        for a in items
    )
    html(f'<div class="lm-alerts">{rows}</div>')


# ---------- AI report ----------

def ai_report_card(report: dict, compact: bool = False) -> None:
    def ul(items):
        return "<ul>" + "".join(f"<li>{escape(t)}</li>" for t in items) + "</ul>"
    cols = "" if compact else (
        '<div class="lm-steps" style="margin-top:1.25rem">'
        f'<div class="lm-ai-list"><h4>Highlights</h4>{ul(report["highlights"])}</div>'
        f'<div class="lm-ai-list"><h4>Risks</h4>{ul(report["risks"])}</div>'
        f'<div class="lm-ai-list"><h4>Recommended actions</h4>{ul(report["actions"])}</div></div>'
    )
    sample = ('<span class="lm-pill neutral lm-sample" title="Example output. Connect n8n or add an API key '
              'to generate live reports.">Sample report</span>') if report.get("sample") else ""
    html(
        '<div class="lm-card"><div class="lm-ai-head">'
        '<span class="lm-ai-badge">✦ AI analyst · '
        f'{escape(report["week_start"])} to {escape(report["week_end"])}</span>{sample}</div>'
        f'<p class="lm-ai-summary">{escape(report["summary"])}</p>{cols}</div>'
    )


# ---------- tables ----------

def _pill(text: str, kind: str) -> str:
    return f'<span class="lm-pill {kind}">{escape(text)}</span>'


def channel_status(row: pd.Series) -> tuple[str, str]:
    roas, roas_prev = row.get("ROAS"), row.get("ROAS (prev)")
    rr = row.get("Return rate %")
    chg = row.get("Revenue Δ %")
    if pd.notna(roas) and pd.notna(roas_prev) and roas_prev and roas / roas_prev - 1 <= -0.25:
        return "At risk", "bad"
    if pd.notna(rr) and rr >= 15:
        return "Watch", "warn"
    if pd.notna(chg) and chg >= 10:
        return "Growing", "ok"
    return "Stable", "neutral"


def channel_html_table(df: pd.DataFrame) -> None:
    if df.empty:
        empty_state("No channel data", "Try widening the date range or selecting more channels.")
        return
    max_share = df["Share %"].max() or 1
    head = ("<tr><th>Channel</th><th>Status</th><th>Revenue</th><th>Change</th><th>Share</th>"
            "<th>Orders</th><th>Conv. rate</th><th>AOV</th><th>Ad spend</th><th>ROAS</th><th>Return rate</th></tr>")
    body = []
    for i, r in df.iterrows():
        status, kind = channel_status(r)
        chg = r["Revenue Δ %"]
        chg_kind = "neutral" if pd.isna(chg) else ("ok" if chg >= 0 else "bad")
        share_w = 0 if pd.isna(r["Share %"]) else max(4, r["Share %"] / max_share * 60)
        body.append(
            "<tr>"
            f'<td><span class="lm-chan"><i style="background:{channel_color(r["Channel"], i)}"></i>{escape(str(r["Channel"]))}</span></td>'
            f"<td>{_pill(status, kind)}</td>"
            f"<td>{fmt_value(r['Revenue'], 'usd0')}</td>"
            f"<td>{_pill(fmt_change(chg, 'pct'), chg_kind)}</td>"
            f'<td><span class="lm-bar" style="width:{share_w:.0f}px"></span>{fmt_value(r["Share %"], "pct1")}</td>'
            f"<td>{fmt_value(r['Orders'], 'int')}</td>"
            f"<td>{fmt_value(r['Conv. rate %'], 'pct2')}</td>"
            f"<td>{fmt_value(r['AOV'], 'usd2')}</td>"
            f"<td>{fmt_value(r['Ad spend'], 'usd0') if r['Ad spend'] else '—'}</td>"
            f"<td>{fmt_value(r['ROAS'], 'x2')}</td>"
            f"<td>{fmt_value(r['Return rate %'], 'pct1')}</td>"
            "</tr>"
        )
    html(f'<div class="lm-table-wrap"><table class="lm-table"><thead>{head}</thead><tbody>{"".join(body)}</tbody></table></div>')


# ---------- states ----------

def empty_state(title: str, body: str) -> None:
    html(f'<div class="lm-empty"><b>{escape(title)}</b>{escape(body)}</div>')


def workflow_steps(steps: list[tuple[str, str]]) -> None:
    items = "".join(
        f'<div class="lm-step"><div class="lm-step-n">{i:02d}</div><b>{escape(t)}</b><span>{escape(d)}</span></div>'
        for i, (t, d) in enumerate(steps, 1)
    )
    html(f'<div class="lm-steps">{items}</div>')


# ---------- generic BI table ----------

def _cell(v, fmt: str, row=None) -> str:
    if fmt == "text":
        return escape(str(v))
    if fmt == "dot":
        from ui.bi_charts import cat_color
        return f'<span class="lm-chan"><i style="background:{cat_color(str(v))}"></i>{escape(str(v))}</span>'
    if fmt == "growth":
        if v is None or pd.isna(v):
            return _pill("new", "neutral")
        return _pill(fmt_change(v, "pct"), "ok" if v >= 0 else "bad")
    if fmt == "achv":
        if v is None or pd.isna(v):
            return "—"
        return _pill(f"{v:.0f}%", "ok" if v >= 100 else ("warn" if v >= 85 else "bad"))
    if fmt == "share":
        if v is None or pd.isna(v):
            return "—"
        return f'<span class="lm-bar" style="width:{max(3, min(v, 100) * 0.9):.0f}px"></span>{v:.1f}%'
    if fmt == "rank":
        return f'<span class="lm-pill neutral">#{int(v)}</span>'
    if fmt == "date":
        return pd.Timestamp(v).strftime("%d %b %Y")
    if fmt == "spark":
        if not isinstance(v, (list, tuple)):
            return "—"
        svg = _sparkline(list(v), COLORS["bad"], w=120, h=26)
        return f'<span style="display:inline-block;width:120px">{svg}</span>'

    return fmt_value(v, fmt)


def data_table(df: pd.DataFrame, columns: list[tuple[str, str, str]], empty_msg: str = "No rows for this selection.") -> None:
    """columns: (field, header, format). Formats: text, dot, usd0, usd2, int, pct1, growth, achv, share, rank, date."""
    if df is None or df.empty:
        empty_state("Nothing to show", empty_msg)
        return
    left = {"text", "dot", "rank"}
    cls = lambda fmt: ' class="l"' if fmt in left else ""  # noqa: E731
    head = "".join(f"<th{cls(fmt)}>{escape(h)}</th>" for _, h, fmt in columns)
    body = "".join(
        "<tr>" + "".join(f"<td{cls(fmt)}>{_cell(r[f], fmt, r)}</td>" for f, _, fmt in columns) + "</tr>"
        for _, r in df.iterrows()
    )
    html(f'<div class="lm-table-wrap"><table class="lm-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def mini_stats(items: list[tuple[str, str, str]]) -> None:
    """Small inline stat cards: (label, value, note)."""
    cards = "".join(
        f'<div class="lm-card lm-stat"><div class="lm-stat-label">{escape(l)}</div>'
        f'<div class="lm-stat-value">{escape(v)}</div><div class="lm-stat-note">{escape(n)}</div></div>'
        for l, v, n in items)
    n = len(items)
    narrow = 3 if n % 3 == 0 and n > 4 else min(n, 4)   # on narrower screens 6 cards become 3 x 2
    html(f'<div class="lm-stats" style="--n-wide:{n};--n-narrow:{narrow}">{cards}</div>')


def breakdown_list(df: pd.DataFrame, color_fn) -> None:
    """Compact list: name, revenue, share bar and growth. df from core.bi.breakdown()."""
    if df is None or df.empty:
        empty_state("Nothing to show", "No revenue in this selection.")
        return
    rows = []
    for i, r in df.iterrows():
        share = 0 if pd.isna(r["share_pct"]) else r["share_pct"]
        chg = r["growth_pct"]
        pill = _pill("new", "neutral") if pd.isna(chg) else _pill(fmt_change(chg, "pct"), "ok" if chg >= 0 else "bad")
        color = color_fn(r["name"], i)
        rows.append(
            '<div class="lm-bd-row">'
            f'<div class="lm-bd-name"><i style="background:{color}"></i>{escape(str(r["name"]))}</div>'
            f'<div class="lm-bd-val">{fmt_value(r["revenue"], "usd0")}</div>'
            f'<div class="lm-bd-track"><span style="width:{min(share, 100):.1f}%;background:{color}"></span></div>'
            f'<div class="lm-bd-share">{share:.1f}%</div><div class="lm-bd-chg">{pill}</div></div>'
        )
    html('<div class="lm-bd">' + "".join(rows) + "</div>")


def nav_link(label: str, page: str, key: str) -> None:
    """Small text button that opens another page (progressive disclosure)."""
    if st.button(label, key=key, icon=":material/arrow_forward:", type="tertiary"):
        st.session_state.page = page
        st.rerun()
