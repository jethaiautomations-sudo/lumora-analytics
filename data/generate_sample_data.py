"""Generates the SAMPLE order-level dataset used by the dashboard.

Lumora Home is a fictional home-goods company. Run this script to rebuild
data/orders.csv and data/sales_targets.csv (fixed seed, so results repeat):

    python data/generate_sample_data.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
rng = np.random.default_rng(2026)

START, END = pd.Timestamp("2025-01-01"), pd.Timestamp("2026-11-22")

# ---------- reference data ----------
REGIONS = {
    "North America": {"countries": {"United States": 0.78, "Canada": 0.22}, "ship": 9.0},
    "Europe": {"countries": {"United Kingdom": 0.40, "Germany": 0.35, "France": 0.25}, "ship": 12.0},
    "Asia Pacific": {"countries": {"Australia": 0.45, "Singapore": 0.25, "Philippines": 0.30}, "ship": 14.0},
}
REGION_WEIGHT = {"North America": 0.48, "Europe": 0.32, "Asia Pacific": 0.20}

SALESPEOPLE = {
    "North America": [("Maya Chen", 1.25), ("Daniel Brooks", 1.05), ("Sofia Ramirez", 0.95), ("Ethan Walker", 0.75)],
    "Europe": [("Clara Novak", 1.20), ("Luca Moretti", 1.00), ("Hannah Fischer", 0.90), ("Oliver Grant", 0.70)],
    "Asia Pacific": [("Aiko Tanaka", 1.15), ("Rafael Santos", 1.00), ("Priya Nair", 0.85), ("Liam O'Connor", 0.65)],
}

# category: (cost ratio of price, products [(name, price, popularity, yearly trend)])
CATALOG = {
    "Furniture": (0.55, [("Oak Dining Table", 899, 0.5, 0.05), ("Linen Lounge Chair", 449, 0.9, 0.10),
                         ("Walnut Coffee Table", 379, 0.8, -0.25), ("Modular Sofa", 1499, 0.35, 0.18),
                         ("Rattan Bar Stool", 159, 1.0, 0.00), ("Floating Wall Shelf", 89, 1.3, -0.30),
                         ("Storage Bench", 249, 0.7, 0.02)]),
    "Lighting": (0.42, [("Arc Floor Lamp", 229, 0.9, 0.12), ("Ceramic Table Lamp", 119, 1.4, 0.04),
                        ("Brass Pendant Light", 189, 0.8, 0.20), ("Paper Lantern Shade", 49, 1.6, -0.35),
                        ("LED Strip Kit", 39, 1.2, -0.10), ("Wall Sconce Pair", 149, 0.7, 0.08)]),
    "Kitchen & Dining": (0.38, [("Stoneware Dinner Set", 139, 1.5, 0.06), ("Copper Cookware Set", 349, 0.6, 0.15),
                                ("Glass Carafe", 34, 2.0, -0.05), ("Linen Napkins (4)", 29, 2.2, 0.00),
                                ("Marble Serving Board", 59, 1.4, 0.22), ("Chef Knife Block", 189, 0.6, -0.20),
                                ("Espresso Cups (6)", 45, 1.6, 0.10)]),
    "Bedding & Bath": (0.35, [("Linen Duvet Cover", 189, 1.4, 0.10), ("Cotton Sheet Set", 129, 1.8, 0.04),
                              ("Waffle Bath Towels", 69, 2.0, 0.08), ("Wool Throw Blanket", 99, 1.3, 0.25),
                              ("Down Pillow Pair", 119, 1.1, -0.12), ("Bath Mat", 39, 1.7, -0.08)]),
    "Decor": (0.33, [("Handmade Vase", 79, 1.6, 0.15), ("Woven Wall Hanging", 119, 0.9, -0.28),
                     ("Round Wall Mirror", 199, 1.0, 0.06), ("Scented Candle Trio", 42, 2.4, 0.18),
                     ("Jute Area Rug", 289, 0.8, 0.00), ("Picture Frame Set", 64, 1.3, -0.15),
                     ("Faux Olive Tree", 159, 0.9, 0.30)]),
    "Outdoor": (0.50, [("Teak Lounge Chair", 549, 0.5, 0.05), ("Outdoor Dining Set", 1299, 0.25, 0.12),
                       ("Solar String Lights", 49, 1.5, -0.18), ("Planter Trio", 89, 1.2, 0.08),
                       ("Outdoor Cushion Set", 119, 0.9, -0.05)]),
}
# Outdoor sells more in the Northern summer, Decor and Bedding in Q4
CAT_SEASON = {"Outdoor": [0.5, 0.6, 0.9, 1.3, 1.6, 1.7, 1.6, 1.3, 0.9, 0.6, 0.5, 0.5],
              "Decor": [0.9, 0.9, 1, 1, 1, 0.9, 0.9, 0.9, 1, 1.1, 1.4, 1.5],
              "Bedding & Bath": [1.1, 1, 1, 1, 0.9, 0.9, 0.9, 1, 1, 1.1, 1.3, 1.3]}
MONTH_SEASON = [0.85, 0.80, 0.92, 0.95, 1.0, 0.95, 0.92, 0.95, 1.0, 1.08, 1.35, 1.45]

SEGMENTS = {"Consumer": 0.72, "Small Business": 0.20, "Corporate": 0.08}
FIRST = ["Emma", "Noah", "Olivia", "Lucas", "Ava", "Mateo", "Isla", "Leo", "Mia", "Elijah", "Zara", "Kai", "Chloe",
         "Ivan", "Nina", "Theo", "Ruby", "Arjun", "Lena", "Hugo", "Grace", "Felix", "Amara", "Jonas", "Elena", "Marco"]
LAST = ["Reyes", "Smith", "Muller", "Dubois", "Patel", "Kim", "Rossi", "Jones", "Lopez", "Nguyen", "Brown", "Silva",
        "Wilson", "Schmidt", "Martin", "Cruz", "Taylor", "Ito", "Garcia", "Clarke", "Weber", "Laurent", "Hughes", "Tan"]
BIZ = ["Interiors", "Design Studio", "Hospitality Group", "Living Co.", "Home Staging", "Boutique Hotels", "Workspace Co."]


def pick(d: dict) -> str:
    keys = list(d)
    return keys[rng.choice(len(keys), p=np.array(list(d.values())) / sum(d.values()))]


products = []
pid = 1
for cat, (cost_ratio, items) in CATALOG.items():
    for name, price, pop, trend in items:
        products.append(dict(product_id=f"P{pid:03d}", product_name=name, category=cat, list_price=price,
                             unit_cost=round(price * cost_ratio * rng.uniform(0.92, 1.08), 2), popularity=pop, trend=trend))
        pid += 1
prod = pd.DataFrame(products)

customers: list[dict] = []


def new_customer(day: pd.Timestamp) -> dict:
    seg = pick(SEGMENTS)
    region = pick(REGION_WEIGHT)
    country = pick(REGIONS[region]["countries"])
    reps = SALESPEOPLE[region]
    rep = reps[rng.choice(len(reps), p=np.array([w for _, w in reps]) / sum(w for _, w in reps))][0]
    last = LAST[rng.integers(len(LAST))]
    name = f"{FIRST[rng.integers(len(FIRST))]} {last}" if seg == "Consumer" else f"{last} {BIZ[rng.integers(len(BIZ))]}"
    c = dict(customer_id=f"C{len(customers) + 10001}", customer_name=name, segment=seg, region=region,
             country=country, salesperson=rep, first_seen=day,
             loyalty=rng.gamma(1.2, 1.0) * {"Consumer": 1, "Small Business": 2.2, "Corporate": 3.5}[seg])
    customers.append(c)
    return c


rows = []
order_no = 100001
days = pd.date_range(START, END)
years_from_start = (days - START).days / 365.0
for day, t in zip(days, years_from_start):
    base = 30 * (1 + 0.18 * t) * MONTH_SEASON[day.month - 1] * (1.12 if day.dayofweek >= 5 else 1)
    if day.month == 11 and day.day >= 20:
        base *= 1.35
    n_orders = rng.poisson(base)
    repeat_p = min(0.55, 0.15 + 0.25 * t)
    for _ in range(n_orders):
        if customers and rng.random() < repeat_p:
            w = np.array([c["loyalty"] for c in customers])
            cust = customers[rng.choice(len(customers), p=w / w.sum())]
        else:
            cust = new_customer(day)
        seg = cust["segment"]
        channel = ("Direct sales" if seg != "Consumer" and rng.random() < 0.7
                   else ("Marketplace" if rng.random() < 0.25 else "Online store"))
        n_lines = rng.choice([1, 2, 3, 4], p=[0.55, 0.27, 0.12, 0.06])
        season = np.array([CAT_SEASON.get(c, [1] * 12)[day.month - 1] for c in prod["category"]])
        weights = prod["popularity"].values * season * np.maximum(0.2, 1 + prod["trend"].values * t)
        chosen = rng.choice(len(prod), size=n_lines, replace=False, p=weights / weights.sum())
        promo = 0.15 if (day.month == 11 and day.day >= 20) else 0.0
        for i in chosen:
            p = prod.iloc[i]
            qty = int(rng.integers(1, 4) if seg == "Consumer" else rng.integers(2, 9 if seg == "Small Business" else 16))
            disc = {"Consumer": 0.0, "Small Business": 0.08, "Corporate": 0.15}[seg] + promo + rng.choice([0, 0, 0.05, 0.10])
            disc = round(min(disc, 0.35), 2)
            price = p["list_price"]
            revenue = round(qty * price * (1 - disc), 2)
            cost = round(qty * p["unit_cost"], 2)
            ship = round(REGIONS[cust["region"]]["ship"] * (1 + 0.15 * qty) * (2.5 if price > 500 else 1), 2)
            rows.append(dict(order_id=f"SO-{order_no}", order_date=day.strftime("%Y-%m-%d"),
                             customer_id=cust["customer_id"], customer_name=cust["customer_name"], segment=seg,
                             region=cust["region"], country=cust["country"], salesperson=cust["salesperson"],
                             channel=channel, product_id=p["product_id"], product_name=p["product_name"],
                             category=p["category"], quantity=qty, unit_price=price, discount_pct=disc,
                             gross_sales=round(qty * price, 2), revenue=revenue, cogs=cost, shipping_cost=ship))
        order_no += 1

orders = pd.DataFrame(rows)
orders.to_csv(OUT / "orders.csv", index=False)

# ---------- monthly targets per salesperson ----------
orders["month"] = pd.to_datetime(orders["order_date"]).dt.to_period("M")
monthly = orders.groupby(["salesperson", "month"])["revenue"].sum()
targets = []
for (rep, month), actual in monthly.items():
    if month.year == 2025:
        annual = monthly.loc[rep][monthly.loc[rep].index.year == 2025].mean()
        target = annual * MONTH_SEASON[month.month - 1] * rng.uniform(0.95, 1.12)
    else:
        last_year = monthly.get((rep, pd.Period(f"2025-{month.month:02d}", "M")), actual)
        target = last_year * 1.18
    targets.append(dict(month=str(month), salesperson=rep, target_usd=round(target / 500) * 500))
pd.DataFrame(targets).to_csv(OUT / "sales_targets.csv", index=False)

print(f"orders.csv: {len(orders):,} lines, {orders['order_id'].nunique():,} orders, "
      f"{orders['customer_id'].nunique():,} customers")
