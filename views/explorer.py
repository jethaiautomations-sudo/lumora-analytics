from __future__ import annotations

import math

import streamlit as st

from core import bi
from ui import components as ui

SECTION = "Data explorer"
TITLE = "Data explorer"
SUBTITLE = "Every order line behind the charts. Search, sort, page through and export."

SORTABLE = {"Date": "order_date", "Revenue": "revenue", "Gross profit": "gross_profit", "Quantity": "quantity",
            "Customer": "customer_name", "Product": "product_name", "Salesperson": "salesperson"}


def render(ctx) -> None:
    with st.container(key="sec_ex"):
        _explorer(ctx)


def _explorer(ctx) -> None:
    """Controls, table and pager form one section (16px apart, not 32px)."""
    c1, c2, c3, c4 = st.columns([2.4, 1.2, 1, 0.9], vertical_alignment="bottom")
    query = c1.text_input("Search", placeholder="Order, customer, product, salesperson or country",
                          key="ex_search", icon=":material/search:")
    sort_label = c2.selectbox("Sort by", list(SORTABLE), index=0, key="ex_sort")
    descending = c3.selectbox("Order", ["Descending", "Ascending"], key="ex_order") == "Descending"
    page_size = c4.selectbox("Rows", [25, 50, 100], key="ex_size")

    df = ctx.cur_o
    if query:
        q = query.strip().lower()
        hay = (df["order_id"].astype(str) + " " + df["customer_name"].astype(str) + " " + df["product_name"].astype(str)
               + " " + df["salesperson"].astype(str) + " " + df["country"].astype(str)).str.lower()
        df = df[hay.str.contains(q, regex=False)]
    df = df.sort_values(SORTABLE[sort_label], ascending=not descending)

    if df.empty:
        ui.empty_state("No matching rows", "Clear the search or widen the date range.")
        return

    pages = max(1, math.ceil(len(df) / page_size))
    if st.session_state.get("ex_page", 1) > pages:
        st.session_state.ex_page = 1
    start = (st.session_state.get("ex_page", 1) - 1) * page_size
    view = df.iloc[start:start + page_size]
    cols = ["order_date", "order_id", "customer_name", "segment", "country", "salesperson", "product_name", "category",
            "quantity", "discount_pct", "revenue", "gross_profit"]
    st.dataframe(
        view[cols], hide_index=True, use_container_width=True, height=min(38 + 35 * len(view), 640),
        column_config={
            "order_date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
            "order_id": st.column_config.TextColumn("Order"),
            "customer_name": st.column_config.TextColumn("Customer"),
            "segment": st.column_config.TextColumn("Segment"),
            "country": st.column_config.TextColumn("Country"),
            "salesperson": st.column_config.TextColumn("Salesperson"),
            "product_name": st.column_config.TextColumn("Product"),
            "category": st.column_config.TextColumn("Category"),
            "quantity": st.column_config.NumberColumn("Qty", format="%d"),
            "discount_pct": st.column_config.NumberColumn("Discount", format="percent"),
            "revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
            "gross_profit": st.column_config.NumberColumn("Gross profit", format="$%.2f"),
        },
    )
    p1, p2, p3 = st.columns([3, 1, 1.2], vertical_alignment="center")
    p1.caption(f"Showing {start + 1:,}–{min(start + page_size, len(df)):,} of {len(df):,} order lines")
    p2.number_input("Page", min_value=1, max_value=pages, step=1, key="ex_page", label_visibility="collapsed")
    out = df.drop(columns=["customer_first_order"]).copy()
    out["order_date"] = out["order_date"].dt.strftime("%Y-%m-%d")
    p3.download_button("Download results", bi.to_export_csv(out), file_name="lumora_order_lines.csv",
                       mime="text/csv", icon=":material/download:", use_container_width=True)
