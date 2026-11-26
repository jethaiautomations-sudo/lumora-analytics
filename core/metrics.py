"""KPI and business logic.

Same definitions as the n8n "Calculate KPIs" node, so the dashboard and the
emailed report always agree:
- AOV = revenue / orders
- Conversion rate = orders / sessions
- Paid ROAS = revenue from channels with ad spend / ad spend
- Return rate = returns / orders
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd


def safe_div(a: float, b: float) -> float | None:
    return a / b if b else None


def pct_change(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev in (None, 0):
        return None
    return (cur / prev - 1) * 100


# ---------- filtering & periods ----------

def filter_sales(df: pd.DataFrame, start: date, end: date, channels: list[str] | None = None) -> pd.DataFrame:
    mask = (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
    if channels:
        mask &= df["channel"].isin(channels)
    return df.loc[mask]


def previous_period(start: date, end: date) -> tuple[date, date]:
    """The period of the same length right before [start, end]."""
    days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    return prev_end - timedelta(days=days - 1), prev_end


# ---------- totals ----------

def totals(df: pd.DataFrame) -> dict:
    paid = df[df["ad_spend_usd"] > 0]
    t = {
        "sessions": float(df["sessions"].sum()),
        "orders": float(df["orders"].sum()),
        "revenue": float(df["revenue_usd"].sum()),
        "ad_spend": float(df["ad_spend_usd"].sum()),
        "returns": float(df["returns"].sum()),
        "new_customers": float(df["new_customers"].sum()),
        "paid_revenue": float(paid["revenue_usd"].sum()),
    }
    t["aov"] = safe_div(t["revenue"], t["orders"])
    cr = safe_div(t["orders"], t["sessions"])
    t["conversion_rate"] = cr * 100 if cr is not None else None
    t["roas"] = safe_div(t["paid_revenue"], t["ad_spend"])
    rr = safe_div(t["returns"], t["orders"])
    t["return_rate"] = rr * 100 if rr is not None else None
    return t


@dataclass
class KPI:
    key: str
    label: str
    value: float | None
    previous: float | None
    fmt: str            # usd0 | usd2 | int | pct2 | pct1 | x2
    change_mode: str    # pct | pts | x
    good_when: str      # up | down
    hint: str = ""

    @property
    def change(self) -> float | None:
        if self.value is None or self.previous is None:
            return None
        if self.change_mode == "pct":
            return pct_change(self.value, self.previous)
        return self.value - self.previous

    @property
    def is_good(self) -> bool | None:
        c = self.change
        if c is None or abs(c) < 1e-9:
            return None
        return (c > 0) == (self.good_when == "up")


KPI_SPECS = [
    # key, label, fmt, change mode, good when, hint
    ("revenue", "Revenue", "usd0", "pct", "up", "Total order revenue"),
    ("orders", "Orders", "int", "pct", "up", "Completed orders"),
    ("aov", "Avg. order value", "usd2", "pct", "up", "Revenue ÷ orders"),
    ("conversion_rate", "Conversion rate", "pct2", "pts", "up", "Orders ÷ sessions"),
    ("roas", "Paid ROAS", "x2", "x", "up", "Paid revenue ÷ ad spend"),
    ("return_rate", "Return rate", "pct1", "pts", "down", "Returns ÷ orders"),
]


def kpi_summary(cur: dict, prev: dict) -> list[KPI]:
    return [KPI(k, label, cur[k], prev[k], fmt, mode, good, hint)
            for k, label, fmt, mode, good, hint in KPI_SPECS]


# ---------- tables ----------

def channel_table(cur_df: pd.DataFrame, prev_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    channels = sorted(set(cur_df["channel"]) | set(prev_df["channel"]))
    total_rev = cur_df["revenue_usd"].sum()
    for ch in channels:
        c = totals(cur_df[cur_df["channel"] == ch])
        p = totals(prev_df[prev_df["channel"] == ch])
        rows.append({
            "Channel": ch,
            "Sessions": c["sessions"],
            "Orders": c["orders"],
            "Revenue": c["revenue"],
            "Revenue (prev)": p["revenue"],
            "Revenue Δ %": pct_change(c["revenue"], p["revenue"]),
            "Share %": (c["revenue"] / total_rev * 100) if total_rev else None,
            "Conv. rate %": c["conversion_rate"],
            "AOV": c["aov"],
            "Ad spend": c["ad_spend"],
            "Ad spend (prev)": p["ad_spend"],
            "ROAS": c["roas"],
            "ROAS (prev)": p["roas"],
            "Return rate %": c["return_rate"],
            "Return rate (prev) %": p["return_rate"],
        })
    out = pd.DataFrame(rows)
    return out.sort_values("Revenue", ascending=False).reset_index(drop=True) if not out.empty else out


def daily_series(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("date", as_index=False)[["sessions", "orders", "revenue_usd", "ad_spend_usd", "returns"]].sum()
    return g


def weekly_series(df: pd.DataFrame, end: date, weeks: int | None = None) -> pd.DataFrame:
    """Rolling 7-day weeks counted back from `end` (same windows as the report)."""
    if df.empty:
        return pd.DataFrame()
    first = df["date"].min().date()
    rows = []
    k = 0
    while True:
        w_end = end - timedelta(days=7 * k)
        w_start = w_end - timedelta(days=6)
        if w_start < first or (weeks is not None and k >= weeks):
            break
        t = totals(filter_sales(df, w_start, w_end))
        rows.append({"week_start": pd.Timestamp(w_start), "week_end": pd.Timestamp(w_end), **t})
        k += 1
    return pd.DataFrame(rows[::-1])


def weekly_by_channel(df: pd.DataFrame, end: date) -> pd.DataFrame:
    frames = []
    for ch, part in df.groupby("channel"):
        w = weekly_series(part, end)
        if not w.empty:
            w["channel"] = ch
            frames.append(w)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------- alerts ----------

ALERT_RULES = {
    "roas_drop_pct": 25,       # paid ROAS down by this % or more
    "return_rate_max": 15,     # return rate at or above this %
    "revenue_drop_pct": 10,    # channel revenue down by this % or more
    "revenue_jump_pct": 30,    # channel revenue up by this % or more
}


def alerts(channels: pd.DataFrame, rules: dict = ALERT_RULES) -> list[dict]:
    """Rule-based checks that run before any AI step."""
    out: list[dict] = []
    for _, r in channels.iterrows():
        ch = r["Channel"]
        roas_chg = pct_change(r["ROAS"], r["ROAS (prev)"])
        spend_chg = pct_change(r["Ad spend"], r["Ad spend (prev)"])
        if roas_chg is not None and roas_chg <= -rules["roas_drop_pct"]:
            detail = f"ROAS fell from {r['ROAS (prev)']:.2f}× to {r['ROAS']:.2f}×"
            if spend_chg is not None and spend_chg > 0:
                detail += f" while ad spend rose {spend_chg:.0f}%"
            out.append({"level": "critical", "channel": ch, "title": "Paid efficiency dropping", "detail": detail + "."})
        rr = r["Return rate %"]
        if rr is not None and pd.notna(rr) and rr >= rules["return_rate_max"]:
            prev = r["Return rate (prev) %"]
            prev_txt = f" (was {prev:.1f}%)" if prev is not None and pd.notna(prev) else ""
            out.append({"level": "warning", "channel": ch, "title": "High return rate",
                        "detail": f"{rr:.1f}% of orders were returned{prev_txt}."})
        chg = r["Revenue Δ %"]
        if chg is not None and pd.notna(chg):
            if chg <= -rules["revenue_drop_pct"]:
                out.append({"level": "warning", "channel": ch, "title": "Revenue down",
                            "detail": f"Revenue fell {abs(chg):.1f}% vs the previous period."})
            elif chg >= rules["revenue_jump_pct"]:
                out.append({"level": "positive", "channel": ch, "title": "Revenue surge",
                            "detail": f"Revenue grew {chg:.1f}% vs the previous period."})
    order = {"critical": 0, "warning": 1, "positive": 2}
    return sorted(out, key=lambda a: order[a["level"]])


def kpi_payload(cur: dict, prev: dict, channels: pd.DataFrame, start: date, end: date) -> dict:
    """KPI JSON handed to the LLM (mirrors the n8n workflow)."""
    def r(v, n=2):
        return None if v is None or pd.isna(v) else round(float(v), n)

    def diff(a, b):
        return None if a is None or b is None or pd.isna(a) or pd.isna(b) else a - b

    # Payload-only extras (not shown on the dashboard): total ad spend and the
    # per-channel changes the model needs, so it never has to calculate them.
    kpis = kpi_summary(cur, prev) + [
        KPI("ad_spend", "Ad spend", cur["ad_spend"], prev["ad_spend"], "usd0", "pct", "down")]
    rows = []
    for row in channels.to_dict("records"):
        row = dict(row)
        row["Revenue Δ $"] = diff(row.get("Revenue"), row.get("Revenue (prev)"))
        row["Ad spend Δ %"] = pct_change(row.get("Ad spend"), row.get("Ad spend (prev)"))
        row["Return rate Δ pts"] = diff(row.get("Return rate %"), row.get("Return rate (prev) %"))
        rows.append(row)
    return {
        "period": {"start": str(start), "end": str(end)},
        "kpis": {k.key: {"current": r(k.value), "previous": r(k.previous), "change": r(k.change), "change_unit": k.change_mode}
                 for k in kpis},
        "channels": [{k: (r(v) if isinstance(v, (int, float)) or v is None else v) for k, v in row.items()}
                     for row in rows],
        # Rule-based checks (same as the Marketing channels page), most severe first.
        "alerts": [{k: a[k] for k in ("level", "channel", "title", "detail")}
                   for a in (alerts(channels) if not channels.empty else [])],
    }
