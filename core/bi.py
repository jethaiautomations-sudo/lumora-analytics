"""Sales BI logic on order-line data (data/orders.csv + data/sales_targets.csv).

Definitions used everywhere:
- Revenue       = net sales after discounts (sum of `revenue`)
- Gross sales   = list price x quantity, before discounts
- Gross profit  = revenue - COGS
- Net profit    = gross profit - shipping/fulfilment cost (no overheads in the data)
- Orders        = distinct order_id;  Units = sum of quantity
- AOV           = revenue / orders
- New customer  = first order ever falls inside the selected period
- Repeat rate   = share of the period's customers with 2+ orders in the period
- Target %      = revenue / monthly targets pro-rated to the days in the period
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from core.metrics import KPI

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ORDERS_FILE = DATA_DIR / "orders.csv"
TARGETS_FILE = DATA_DIR / "sales_targets.csv"

ORDER_COLUMNS = {"order_id", "order_date", "customer_id", "customer_name", "segment", "region", "country",
                 "salesperson", "channel", "product_id", "product_name", "category", "quantity", "unit_price",
                 "discount_pct", "gross_sales", "revenue", "cogs", "shipping_cost"}


class BIDataError(Exception):
    pass


# ---------- loading ----------

def prepare_orders(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    missing = ORDER_COLUMNS - set(df.columns)
    if missing:
        raise BIDataError(f"Orders data is missing columns: {', '.join(sorted(missing))}")
    df = df.dropna(subset=["order_id", "order_date"]).copy()
    df["order_date"] = pd.to_datetime(df["order_date"]).dt.normalize()
    for c in ["quantity", "unit_price", "discount_pct", "gross_sales", "revenue", "cogs", "shipping_cost"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["gross_profit"] = df["revenue"] - df["cogs"]
    df["net_profit"] = df["gross_profit"] - df["shipping_cost"]
    df["discount_amount"] = df["gross_sales"] - df["revenue"]
    # first purchase ever, used for new vs returning
    df["customer_first_order"] = df.groupby("customer_id")["order_date"].transform("min")
    for c in ["segment", "region", "country", "salesperson", "channel", "category", "product_name"]:
        df[c] = df[c].astype("category")
    return df


def load_orders(path: Path = ORDERS_FILE) -> pd.DataFrame:
    if not path.exists():
        raise BIDataError(f"Orders file not found: {path.name}")
    return prepare_orders(pd.read_csv(path))


def load_targets(path: Path = TARGETS_FILE) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["month", "salesperson", "target_usd"])
    t = pd.read_csv(path)
    t["month"] = pd.PeriodIndex(t["month"], freq="M")
    t["target_usd"] = pd.to_numeric(t["target_usd"], errors="coerce").fillna(0)
    return t


# ---------- filters & periods ----------

@dataclass
class Filters:
    regions: list[str]
    categories: list[str]
    salespeople: list[str]
    segments: list[str]
    channels: list[str]


def apply_filters(df: pd.DataFrame, f: Filters) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    for col, values in (("region", f.regions), ("category", f.categories), ("salesperson", f.salespeople),
                        ("segment", f.segments), ("channel", f.channels)):
        if values:
            mask &= df[col].isin(values)
    return df[mask]


def in_period(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    return df[(df["order_date"] >= pd.Timestamp(start)) & (df["order_date"] <= pd.Timestamp(end))]


def previous_period(start: date, end: date) -> tuple[date, date]:
    n = (end - start).days + 1
    pe = start - timedelta(days=1)
    return pe - timedelta(days=n - 1), pe


def pct(a, b):
    if b is None or b == 0 or pd.isna(b) or a is None or pd.isna(a):
        return None
    return (a / b - 1) * 100


def safe_div(a, b):
    return a / b if b else None


# ---------- targets ----------

def target_for_period(targets: pd.DataFrame, start: date, end: date, salespeople: list[str] | None = None) -> float:
    """Monthly targets pro-rated by the number of days of each month inside [start, end]."""
    if targets.empty:
        return 0.0
    t = targets if not salespeople else targets[targets["salesperson"].isin(salespeople)]
    total = 0.0
    for month, amount in t.groupby("month")["target_usd"].sum().items():
        m_start, m_end = month.start_time.date(), month.end_time.date()
        overlap = (min(end, m_end) - max(start, m_start)).days + 1
        if overlap > 0:
            total += amount * overlap / month.days_in_month
    return total


def target_by_salesperson(targets: pd.DataFrame, start: date, end: date) -> pd.Series:
    return pd.Series({rep: target_for_period(targets, start, end, [rep]) for rep in targets["salesperson"].unique()},
                     dtype=float)


# ---------- executive KPIs ----------

def totals(df: pd.DataFrame) -> dict:
    revenue = float(df["revenue"].sum())
    orders = int(df["order_id"].nunique())
    return {
        "revenue": revenue, "orders": orders, "units": float(df["quantity"].sum()),
        "aov": safe_div(revenue, orders), "customers": int(df["customer_id"].nunique()),
        "gross_sales": float(df["gross_sales"].sum()), "discounts": float(df["discount_amount"].sum()),
        "cogs": float(df["cogs"].sum()), "shipping": float(df["shipping_cost"].sum()),
        "gross_profit": float(df["gross_profit"].sum()), "net_profit": float(df["net_profit"].sum()),
    }


def executive_kpis(cur_df, prev_df, prev2_df, targets, start, end, prev_start, prev_end, salespeople) -> list[KPI]:
    c, p, p2 = totals(cur_df), totals(prev_df), totals(prev2_df)
    growth_now, growth_prev = pct(c["revenue"], p["revenue"]), pct(p["revenue"], p2["revenue"])
    t_now = target_for_period(targets, start, end, salespeople)
    t_prev = target_for_period(targets, prev_start, prev_end, salespeople)
    ach_now = c["revenue"] / t_now * 100 if t_now else None
    ach_prev = p["revenue"] / t_prev * 100 if t_prev else None
    gm_now = c["gross_profit"] / c["revenue"] * 100 if c["revenue"] else None
    gm_prev = p["gross_profit"] / p["revenue"] * 100 if p["revenue"] else None
    return [
        KPI("revenue", "Total revenue", c["revenue"], p["revenue"], "usd0", "pct", "up", "Net sales after discounts"),
        KPI("orders", "Total orders", c["orders"], p["orders"], "int", "pct", "up", "Distinct orders"),
        KPI("units", "Units sold", c["units"], p["units"], "int", "pct", "up", "Sum of quantity"),
        KPI("aov", "Avg. order value", c["aov"], p["aov"], "usd2", "pct", "up", "Revenue ÷ orders"),
        KPI("customers", "Customers", c["customers"], p["customers"], "int", "pct", "up", "Distinct customers who ordered"),
        KPI("growth", "Revenue growth", growth_now, growth_prev, "pct1", "pts", "up", "Revenue vs previous period"),
        KPI("target", "Target achievement", ach_now, ach_prev, "pct1", "pts", "up", "Revenue ÷ pro-rated sales target"),
        KPI("margin", "Gross margin", gm_now, gm_prev, "pct1", "pts", "up", "Gross profit ÷ revenue"),
    ]


def weekly_kpi_series(df: pd.DataFrame, end: date, weeks: int = 12) -> dict[str, list[float]]:
    """12 rolling weeks ending on `end`, for the KPI sparklines."""
    out: dict[str, list[float]] = {k: [] for k in ["revenue", "orders", "units", "aov", "customers", "margin"]}
    for k in range(weeks - 1, -1, -1):
        e = end - timedelta(days=7 * k)
        t = totals(in_period(df, e - timedelta(days=6), e))
        t["margin"] = t["gross_profit"] / t["revenue"] * 100 if t["revenue"] else None
        for key in out:
            out[key].append(t[key])
    return out


# ---------- revenue analytics ----------

FREQ = {"Daily": "D", "Weekly": "W-MON", "Monthly": "MS", "Yearly": "YS"}


def auto_granularity(start: date, end: date) -> str:
    days = (end - start).days + 1
    return "Daily" if days <= 45 else ("Weekly" if days <= 200 else "Monthly")


def revenue_trend(df: pd.DataFrame, freq_label: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["period", "revenue", "orders", "gross_profit"])
    g = (df.set_index("order_date")
         .groupby(pd.Grouper(freq=FREQ[freq_label], label="left", closed="left"))
         .agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"), gross_profit=("gross_profit", "sum"))
         .reset_index().rename(columns={"order_date": "period"}))
    return g


def breakdown(cur: pd.DataFrame, prev: pd.DataFrame, dim: str) -> pd.DataFrame:
    """Revenue, profit, orders, units by a dimension, with previous period and growth."""
    agg = dict(revenue=("revenue", "sum"), orders=("order_id", "nunique"), units=("quantity", "sum"),
               gross_profit=("gross_profit", "sum"), net_profit=("net_profit", "sum"),
               customers=("customer_id", "nunique"), discounts=("discount_amount", "sum"),
               gross_sales=("gross_sales", "sum"))
    c = cur.groupby(dim, observed=True).agg(**agg)
    p = prev.groupby(dim, observed=True).agg(prev_revenue=("revenue", "sum"), prev_units=("quantity", "sum"))
    out = c.join(p, how="outer").fillna(0)
    out = out[(out["revenue"] != 0) | (out["prev_revenue"] != 0)]
    total = out["revenue"].sum()
    out["share_pct"] = out["revenue"] / total * 100 if total else np.nan
    out["growth_pct"] = np.where(out["prev_revenue"] > 0, (out["revenue"] / out["prev_revenue"].where(out["prev_revenue"] > 0) - 1) * 100, np.nan)
    out["aov"] = out["revenue"] / out["orders"].where(out["orders"] > 0)
    out["gross_margin_pct"] = out["gross_profit"] / out["revenue"].where(out["revenue"] > 0) * 100
    out["net_margin_pct"] = out["net_profit"] / out["revenue"].where(out["revenue"] > 0) * 100
    out["discount_pct"] = out["discounts"] / out["gross_sales"].where(out["gross_sales"] > 0) * 100
    out = out.reset_index().rename(columns={dim: "name"})
    out["name"] = out["name"].astype(str)
    return out.sort_values("revenue", ascending=False).reset_index(drop=True)


# ---------- sales performance ----------

def salesperson_table(cur, prev, targets, start, end) -> pd.DataFrame:
    b = breakdown(cur, prev, "salesperson")
    if b.empty:
        return b
    both = pd.concat([cur, prev])
    region = both.groupby("salesperson", observed=True)["region"].agg(lambda s: s.mode().iat[0] if len(s) else "")
    t = target_by_salesperson(targets, start, end)
    b["region"] = b["name"].map(region).astype(str)
    b["target"] = b["name"].map(t).fillna(0)
    b["achievement_pct"] = b["revenue"] / b["target"].where(b["target"] > 0) * 100
    b["gap_to_target"] = b["revenue"] - b["target"]
    b["rank"] = b["revenue"].rank(ascending=False, method="min").astype(int)
    return b.sort_values("rank").reset_index(drop=True)


# ---------- products ----------

def product_table(cur, prev) -> pd.DataFrame:
    b = breakdown(cur, prev, "product_name")
    cat = pd.concat([cur, prev]).groupby("product_name", observed=True)["category"].first()
    cat.index = cat.index.astype(str)
    b["category"] = b["name"].map(cat.astype(str)).fillna("Other")
    return b


def declining_products(df_all: pd.DataFrame, end: date, months: int = 3, threshold: float = -10.0) -> pd.DataFrame:
    """Products whose revenue in the last `months` months is down `threshold`% or more
    against the same months a year earlier (year-over-year, so seasonality doesn't count as decline)."""
    end_ts = pd.Timestamp(end)
    recent_start = end_ts - pd.DateOffset(months=months) + pd.Timedelta(days=1)
    ly_start, ly_end = recent_start - pd.DateOffset(years=1), end_ts - pd.DateOffset(years=1)
    recent = df_all[(df_all["order_date"] >= recent_start) & (df_all["order_date"] <= end_ts)]
    prior = df_all[(df_all["order_date"] >= ly_start) & (df_all["order_date"] <= ly_end)]
    r = recent.groupby("product_name", observed=True)["revenue"].sum()
    p = prior.groupby("product_name", observed=True)["revenue"].sum()
    out = pd.DataFrame({"recent": r, "prior": p}).fillna(0)
    out.index = out.index.astype(str)
    out = out[out["prior"] > 0]
    out["change_pct"] = (out["recent"] / out["prior"] - 1) * 100

    last12 = df_all[df_all["order_date"] > end_ts - pd.DateOffset(months=12)]
    monthly = (last12.groupby([pd.Grouper(key="order_date", freq="MS"), "product_name"], observed=True)["revenue"]
               .sum().unstack(fill_value=0))
    monthly.columns = monthly.columns.astype(str)
    out["spark"] = pd.Series({c: monthly[c].tolist() for c in monthly.columns})
    cat = df_all.groupby("product_name", observed=True)["category"].first()
    cat.index = cat.index.astype(str)
    out["category"] = cat.astype(str)
    out = out[out["change_pct"] <= threshold].sort_values("change_pct")
    return out.reset_index(names="name")


# ---------- customers ----------

def customer_metrics(cur: pd.DataFrame, start: date, end: date, history: pd.DataFrame | None = None) -> dict:
    """`history` = all filtered orders up to `end`, used for lifetime repeat rate and frequency."""
    if cur.empty:
        return {}
    lifetime = None
    if history is not None:
        h = history[history["order_date"] <= pd.Timestamp(end)]
        lifetime = h[h["customer_id"].isin(cur["customer_id"].unique())].groupby("customer_id")["order_id"].nunique()
    per_cust = cur.groupby("customer_id").agg(orders=("order_id", "nunique"), revenue=("revenue", "sum"),
                                              first=("customer_first_order", "first"))
    is_new = per_cust["first"] >= pd.Timestamp(start)
    return {
        "customers": len(per_cust),
        "new": int(is_new.sum()),
        "returning": int((~is_new).sum()),
        "new_revenue": float(per_cust.loc[is_new, "revenue"].sum()),
        "returning_revenue": float(per_cust.loc[~is_new, "revenue"].sum()),
        "avg_spend": float(per_cust["revenue"].mean()),
        "repeat_rate": float((per_cust["orders"] >= 2).mean() * 100),
        "avg_frequency": float(per_cust["orders"].mean()),
        "frequency": per_cust["orders"].clip(upper=6).value_counts().sort_index(),
        "lifetime_repeat_rate": float((lifetime >= 2).mean() * 100) if lifetime is not None else None,
        "lifetime_frequency": lifetime.clip(upper=8).value_counts().sort_index() if lifetime is not None else None,
        "lifetime_avg_orders": float(lifetime.mean()) if lifetime is not None else None,
    }


def top_customers(cur: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    g = (cur.groupby(["customer_id", "customer_name", "segment", "country"], observed=True)
         .agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"), units=("quantity", "sum"),
              gross_profit=("gross_profit", "sum"), last_order=("order_date", "max"))
         .reset_index().sort_values("revenue", ascending=False).head(n))
    g["aov"] = g["revenue"] / g["orders"]
    return g.reset_index(drop=True)


def new_vs_returning_trend(df: pd.DataFrame, freq: str = "MS") -> pd.DataFrame:
    d = df.copy()
    d["period"] = d["order_date"].dt.to_period("M" if freq == "MS" else "W").dt.start_time
    d["period_first"] = d["customer_first_order"].dt.to_period("M" if freq == "MS" else "W").dt.start_time
    d["type"] = np.where(d["period_first"] == d["period"], "New", "Returning")
    return d.groupby(["period", "type"]).agg(customers=("customer_id", "nunique"), revenue=("revenue", "sum")).reset_index()
