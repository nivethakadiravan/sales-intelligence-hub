"""Sales Intelligence Hub - Streamlit dashboard.

Run:  streamlit run app.py
"""

from __future__ import annotations

from datetime import date

import mysql.connector
import pandas as pd
import plotly.express as px
import streamlit as st

from src.auth import authenticate
from src.db import execute, run_query
from src.queries import QUERIES, render

st.set_page_config(page_title="Sales Intelligence Hub", page_icon="📊", layout="wide")

PRODUCTS = {"DS": "Data Science", "DA": "Data Analytics", "BA": "Business Analytics", "FSD": "Full Stack Development"}
METHODS = ["Cash", "UPI", "Card"]
COLORS = {"received": "#2a9d8f", "pending": "#e76f51", "gross": "#264653"}


# =====================================================================
# Helpers
# =====================================================================
def inr(value) -> str:
    """Format a number in Indian style: ₹12,34,567."""
    try:
        n = int(round(float(value or 0)))
    except (TypeError, ValueError):
        return "₹0"
    sign, s = ("-" if n < 0 else ""), str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return f"{sign}₹{s}"


def current_user() -> dict | None:
    return st.session_state.get("user")


def is_super_admin() -> bool:
    user = current_user()
    return bool(user and user["role"] == "Super Admin")


def scope_branch_id() -> int | None:
    """None = all branches (Super Admin); otherwise the admin's branch."""
    return None if is_super_admin() else current_user()["branch_id"]


@st.cache_data(ttl=300)
def load_branches() -> pd.DataFrame:
    return run_query("SELECT branch_id, branch_name, branch_admin_name FROM branches ORDER BY branch_name")


def branch_filter_widget(key: str) -> int | None:
    """Branch selector for Super Admin; fixed branch for Admin."""
    if not is_super_admin():
        st.caption(f"Branch: **{current_user()['branch_name']}**")
        return current_user()["branch_id"]
    branches = load_branches()
    options = ["All branches"] + branches["branch_name"].tolist()
    choice = st.selectbox("Branch", options, key=key)
    if choice == "All branches":
        return None
    return int(branches.loc[branches["branch_name"] == choice, "branch_id"].iloc[0])


def sales_frame(branch_id: int | None) -> pd.DataFrame:
    sql = """
        SELECT cs.sale_id, cs.date, b.branch_name, cs.name, cs.mobile_number,
               cs.product_name, cs.gross_sales, cs.received_amount,
               cs.pending_amount, cs.status
        FROM customer_sales cs
        JOIN branches b ON b.branch_id = cs.branch_id
        WHERE (%(bid)s IS NULL OR cs.branch_id = %(bid)s)
        ORDER BY cs.date DESC, cs.sale_id DESC
    """
    df = run_query(sql, {"bid": branch_id})
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def payments_frame(branch_id: int | None) -> pd.DataFrame:
    sql = """
        SELECT ps.payment_id, ps.sale_id, ps.payment_date, ps.amount_paid,
               ps.payment_method, cs.name, cs.product_name, b.branch_name
        FROM payment_splits ps
        JOIN customer_sales cs ON cs.sale_id = ps.sale_id
        JOIN branches b ON b.branch_id = cs.branch_id
        WHERE (%(bid)s IS NULL OR cs.branch_id = %(bid)s)
        ORDER BY ps.payment_date DESC, ps.payment_id DESC
    """
    df = run_query(sql, {"bid": branch_id})
    if not df.empty:
        df["payment_date"] = pd.to_datetime(df["payment_date"])
    return df


MONEY_COLS = ["gross_sales", "received_amount", "pending_amount", "amount_paid",
              "total_gross_sales", "total_received", "total_pending", "total_collection"]


def show_table(df: pd.DataFrame, height: int | None = None) -> None:
    config = {c: st.column_config.NumberColumn(c.replace("_", " ").title(), format="₹%.2f")
              for c in df.columns if c in MONEY_COLS}
    for c in ("date", "payment_date"):
        if c in df.columns:
            config[c] = st.column_config.DateColumn(c.replace("_", " ").title(), format="DD MMM YYYY")
    kwargs = {"height": height} if height else {}
    st.dataframe(df, width="stretch", hide_index=True, column_config=config, **kwargs)


def kpi_row(df: pd.DataFrame) -> None:
    gross = df["gross_sales"].sum() if not df.empty else 0
    received = df["received_amount"].sum() if not df.empty else 0
    pending = df["pending_amount"].sum() if not df.empty else 0
    pending_pct = (pending / gross * 100) if gross else 0
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total sales", f"{len(df):,}")
    c2.metric("Gross revenue", inr(gross))
    c3.metric("Received", inr(received), f"{(received / gross * 100) if gross else 0:.1f}% collected")
    c4.metric("Pending", inr(pending), f"{pending_pct:.1f}% outstanding", delta_color="inverse")
    open_n = int((df["status"] == "Open").sum()) if not df.empty else 0
    c5.metric("Open / Closed", f"{open_n} / {len(df) - open_n}")


# =====================================================================
# Login
# =====================================================================
def login_page() -> None:
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.title("📊 Sales Intelligence Hub")
        st.caption("Branch-based sales & payment tracking")
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", width="stretch", type="primary")
        if submitted:
            if not username or not password:
                st.error("Enter both username and password.")
                return
            try:
                user = authenticate(username, password)
            except mysql.connector.Error as exc:
                st.error(f"Could not reach the database: {exc.msg}")
                return
            if user:
                st.session_state["user"] = user
                st.rerun()
            else:
                st.error("Invalid username or password.")


def logout() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.cache_data.clear()
    st.rerun()


# =====================================================================
# Pages
# =====================================================================
def page_dashboard() -> None:
    st.header("Business overview")
    branch_id = branch_filter_widget("dash_branch")
    sales = sales_frame(branch_id)
    payments = payments_frame(branch_id)
    if sales.empty:
        st.info("No sales recorded yet.")
        return

    kpi_row(sales)
    st.divider()

    # --- Branch comparison (all branches) / product mix (single branch)
    left, right = st.columns(2)
    with left:
        if branch_id is None:
            st.subheader("Branch-wise sales comparison")
            by_branch = (sales.groupby("branch_name")[["received_amount", "pending_amount"]]
                         .sum().reset_index()
                         .assign(total=lambda d: d.received_amount + d.pending_amount)
                         .sort_values("total", ascending=False))
            fig = px.bar(by_branch, x="branch_name", y=["received_amount", "pending_amount"],
                         labels={"value": "Amount (₹)", "branch_name": "", "variable": ""},
                         color_discrete_map={"received_amount": COLORS["received"],
                                             "pending_amount": COLORS["pending"]})
        else:
            st.subheader("Revenue by product")
            by_prod = sales.groupby("product_name")[["received_amount", "pending_amount"]].sum().reset_index()
            fig = px.bar(by_prod, x="product_name", y=["received_amount", "pending_amount"],
                         labels={"value": "Amount (₹)", "product_name": "", "variable": ""},
                         color_discrete_map={"received_amount": COLORS["received"],
                                             "pending_amount": COLORS["pending"]})
        fig.update_layout(legend=dict(orientation="h", y=1.1), margin=dict(t=30, b=0))
        st.plotly_chart(fig, width="stretch")

    with right:
        st.subheader("Payment method analysis")
        if payments.empty:
            st.info("No payments yet.")
        else:
            by_method = payments.groupby("payment_method")["amount_paid"].sum().reset_index()
            fig = px.pie(by_method, names="payment_method", values="amount_paid", hole=0.55,
                         color="payment_method",
                         color_discrete_map={"UPI": "#264653", "Card": "#2a9d8f", "Cash": "#e9c46a"})
            fig.update_traces(textinfo="label+percent")
            fig.update_layout(showlegend=False, margin=dict(t=30, b=0))
            st.plotly_chart(fig, width="stretch")

    # --- Monthly trend + growth
    st.subheader("Sales trend & growth")
    monthly = (sales.set_index("date").resample("MS")
               .agg(gross_sales=("gross_sales", "sum"), received_amount=("received_amount", "sum"),
                    sales_count=("sale_id", "count"))
               .reset_index())
    monthly["growth_pct"] = monthly["gross_sales"].pct_change().mul(100).round(1)
    monthly["month"] = monthly["date"].dt.strftime("%b %Y")
    fig = px.line(monthly, x="month", y=["gross_sales", "received_amount"], markers=True,
                  labels={"value": "Amount (₹)", "month": "", "variable": ""},
                  color_discrete_map={"gross_sales": COLORS["gross"], "received_amount": COLORS["received"]})
    fig.update_layout(legend=dict(orientation="h", y=1.1), margin=dict(t=30, b=0))
    st.plotly_chart(fig, width="stretch")
    with st.expander("Month-on-month growth table"):
        show_table(monthly[["month", "sales_count", "gross_sales", "received_amount", "growth_pct"]])

    # --- Branch performance summary
    st.subheader("Branch performance summary")
    perf = (sales.groupby("branch_name")
            .agg(total_sales=("sale_id", "count"), total_gross_sales=("gross_sales", "sum"),
                 total_received=("received_amount", "sum"), total_pending=("pending_amount", "sum"),
                 open_sales=("status", lambda s: int((s == "Open").sum())))
            .reset_index())
    perf["collection_pct"] = (perf["total_received"] / perf["total_gross_sales"] * 100).round(1)
    perf["pending_pct"] = (perf["total_pending"] / perf["total_gross_sales"] * 100).round(1)
    perf = perf.sort_values("total_gross_sales", ascending=False)
    show_table(perf)

    # --- Auto-generated insights
    st.subheader("Key insights")
    gross = sales["gross_sales"].sum()
    pending = sales["pending_amount"].sum()
    insights = []
    if branch_id is None and len(perf) > 1:
        top, low = perf.iloc[0], perf.sort_values("collection_pct").iloc[0]
        insights.append(f"**{top.branch_name}** is the top branch with {inr(top.total_gross_sales)} "
                        f"in gross sales ({top.total_gross_sales / gross * 100:.1f}% of the business).")
        insights.append(f"**{low.branch_name}** has the weakest collection rate "
                        f"({low.collection_pct:.1f}%) - prioritise follow-ups there.")
    if not payments.empty:
        m = payments.groupby("payment_method")["amount_paid"].sum().sort_values(ascending=False)
        insights.append(f"**{m.index[0]}** is the most used payment channel "
                        f"({m.iloc[0] / m.sum() * 100:.1f}% of collections).")
    best_prod = sales.groupby("product_name")["gross_sales"].sum().idxmax()
    insights.append(f"**{best_prod}** ({PRODUCTS.get(best_prod, best_prod)}) is the highest-revenue product.")
    big_pending = int((sales["pending_amount"] > 5000).sum())
    insights.append(f"{inr(pending)} ({pending / gross * 100:.1f}%) is still to be collected; "
                    f"{big_pending} sales have more than ₹5,000 pending.")
    if len(monthly) >= 2 and pd.notna(monthly["growth_pct"].iloc[-1]):
        insights.append(f"Latest month ({monthly['month'].iloc[-1]}) changed "
                        f"{monthly['growth_pct'].iloc[-1]:+.1f}% vs the previous month.")
    for line in insights:
        st.markdown(f"- {line}")


def page_add_sale() -> None:
    st.header("Add new sale")
    branches = load_branches()
    with st.form("add_sale", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            if is_super_admin():
                branch_name = st.selectbox("Branch", branches["branch_name"].tolist())
                branch_id = int(branches.loc[branches["branch_name"] == branch_name, "branch_id"].iloc[0])
            else:
                st.text_input("Branch", current_user()["branch_name"], disabled=True)
                branch_id = current_user()["branch_id"]
            name = st.text_input("Customer name")
            mobile = st.text_input("Mobile number", max_chars=15, help="10-15 digits, must be unique")
        with c2:
            sale_date = st.date_input("Sale date", value=date.today(), max_value=date.today())
            product = st.selectbox("Product", list(PRODUCTS), format_func=lambda p: f"{p} - {PRODUCTS[p]}")
            gross = st.number_input("Gross sales (₹)", min_value=0.0, step=500.0, format="%.2f")
        submitted = st.form_submit_button("Save sale", type="primary")

    if submitted:
        errors = []
        if not name.strip():
            errors.append("Customer name is required.")
        if not (mobile.isdigit() and 10 <= len(mobile) <= 15):
            errors.append("Mobile number must be 10-15 digits.")
        if gross <= 0:
            errors.append("Gross sales must be greater than 0.")
        if errors:
            for e in errors:
                st.error(e)
            return
        try:
            sale_id = execute(
                """INSERT INTO customer_sales (branch_id, date, name, mobile_number, product_name, gross_sales)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (branch_id, sale_date, name.strip(), mobile, product, gross),
            )
            st.success(f"Sale #{sale_id} saved for {name.strip()} - {inr(gross)} pending. "
                       "Add a payment from **Add payment** to start collecting.")
        except mysql.connector.IntegrityError as exc:
            if exc.errno == 1062:
                st.error("This mobile number already has a sale recorded (mobile numbers must be unique).")
            else:
                st.error(f"Could not save sale: {exc.msg}")


def page_add_payment() -> None:
    st.header("Add payment split")
    branch_id = scope_branch_id()
    open_sales = run_query(
        """SELECT cs.sale_id, cs.name, cs.product_name, b.branch_name,
                  cs.gross_sales, cs.received_amount, cs.pending_amount, cs.date
           FROM customer_sales cs JOIN branches b ON b.branch_id = cs.branch_id
           WHERE cs.status = 'Open' AND cs.pending_amount > 0
             AND (%(bid)s IS NULL OR cs.branch_id = %(bid)s)
           ORDER BY cs.sale_id DESC""",
        {"bid": branch_id},
    )
    if open_sales.empty:
        st.success("All sales are fully paid - nothing pending.")
        return

    labels = {int(r.sale_id): f"#{r.sale_id} · {r.name} · {r.product_name} · {r.branch_name} · pending {inr(r.pending_amount)}"
              for r in open_sales.itertuples()}
    sale_id = st.selectbox("Sale", list(labels), format_func=labels.get)
    sale = open_sales.loc[open_sales["sale_id"] == sale_id].iloc[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Gross", inr(sale.gross_sales))
    c2.metric("Received so far", inr(sale.received_amount))
    c3.metric("Pending", inr(sale.pending_amount))

    history = run_query("SELECT payment_id, payment_date, amount_paid, payment_method FROM payment_splits "
                        "WHERE sale_id = %s ORDER BY payment_date", (int(sale_id),))
    if not history.empty:
        with st.expander(f"Previous payments ({len(history)})"):
            show_table(history)

    with st.form("add_payment", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        amount = c1.number_input("Amount paid (₹)", min_value=0.0, max_value=float(sale.pending_amount),
                                 step=500.0, format="%.2f")
        pay_date = c2.date_input("Payment date", value=date.today(),
                                 min_value=pd.to_datetime(sale.date).date(), max_value=date.today())
        method = c3.selectbox("Payment method", METHODS)
        submitted = st.form_submit_button("Record payment", type="primary")

    if submitted:
        if amount <= 0:
            st.error("Amount must be greater than 0.")
            return
        try:
            # Only payment_splits is written - the trigger updates received_amount,
            # pending_amount (generated) and status on customer_sales.
            execute("INSERT INTO payment_splits (sale_id, payment_date, amount_paid, payment_method) "
                    "VALUES (%s, %s, %s, %s)", (int(sale_id), pay_date, amount, method))
        except mysql.connector.Error as exc:
            st.error(f"Could not record payment: {exc.msg}")
            return
        updated = run_query("SELECT received_amount, pending_amount, status FROM customer_sales WHERE sale_id = %s",
                            (int(sale_id),)).iloc[0]
        st.success(f"Payment of {inr(amount)} recorded via {method}. Trigger updated sale #{sale_id}: "
                   f"received {inr(updated.received_amount)}, pending {inr(updated.pending_amount)}, "
                   f"status **{updated.status}**.")


def page_sales_report() -> None:
    st.header("Sales report")
    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.6])
    with c1:
        branch_id = branch_filter_widget("report_branch")
    sales = sales_frame(branch_id)
    if sales.empty:
        st.info("No sales recorded yet.")
        return
    status = c2.multiselect("Status", ["Open", "Close"], default=["Open", "Close"])
    products = c3.multiselect("Product", list(PRODUCTS), default=list(PRODUCTS))
    dmin, dmax = sales["date"].min().date(), sales["date"].max().date()
    period = c4.date_input("Date range", value=(dmin, dmax), min_value=dmin, max_value=dmax)
    search = st.text_input("Search customer name or mobile", placeholder="e.g. Kavya or 98765")

    df = sales[sales["status"].isin(status) & sales["product_name"].isin(products)]
    if isinstance(period, tuple) and len(period) == 2:
        df = df[(df["date"].dt.date >= period[0]) & (df["date"].dt.date <= period[1])]
    if search:
        df = df[df["name"].str.contains(search, case=False) | df["mobile_number"].str.contains(search)]

    kpi_row(df)
    show_table(df, height=450)
    st.download_button("Download CSV", df.to_csv(index=False).encode(), "sales_report.csv", "text/csv")


def page_pending() -> None:
    st.header("Pending payments")
    branch_id = branch_filter_widget("pending_branch")
    sales = sales_frame(branch_id)
    pending = sales[sales["pending_amount"] > 0].copy() if not sales.empty else sales
    if pending.empty:
        st.success("No pending payments 🎉")
        return
    pending["days_open"] = (pd.Timestamp(date.today()) - pending["date"]).dt.days
    pending["age_bucket"] = pd.cut(pending["days_open"], [-1, 30, 60, 90, 10_000],
                                   labels=["0-30 days", "31-60 days", "61-90 days", "90+ days"])
    gross_total = sales["gross_sales"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Sales with dues", f"{len(pending):,}")
    c2.metric("Total pending", inr(pending["pending_amount"].sum()))
    c3.metric("Pending collection %", f"{pending['pending_amount'].sum() / gross_total * 100:.1f}%")

    left, right = st.columns(2)
    with left:
        aging = pending.groupby("age_bucket", observed=False)["pending_amount"].sum().reset_index()
        fig = px.bar(aging, x="age_bucket", y="pending_amount", title="Pending by age",
                     labels={"pending_amount": "Pending (₹)", "age_bucket": ""},
                     color_discrete_sequence=[COLORS["pending"]])
        st.plotly_chart(fig, width="stretch")
    with right:
        status_counts = sales["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        fig = px.pie(status_counts, names="status", values="count", hole=0.55, title="Sales status (Open vs Close)",
                     color="status", color_discrete_map={"Open": COLORS["pending"], "Close": COLORS["received"]})
        st.plotly_chart(fig, width="stretch")

    show_table(pending.sort_values("pending_amount", ascending=False)
               [["sale_id", "date", "branch_name", "name", "mobile_number", "product_name",
                 "gross_sales", "received_amount", "pending_amount", "days_open", "status"]], height=420)


def page_payment_summary() -> None:
    st.header("Payment method summary")
    branch_id = branch_filter_widget("pay_branch")
    payments = payments_frame(branch_id)
    if payments.empty:
        st.info("No payments recorded yet.")
        return
    summary = (payments.groupby("payment_method")
               .agg(no_of_payments=("payment_id", "count"), total_collection=("amount_paid", "sum"),
                    average_payment=("amount_paid", "mean"))
               .reindex(METHODS).fillna(0).reset_index())
    summary["share_pct"] = (summary["total_collection"] / summary["total_collection"].sum() * 100).round(1)
    cols = st.columns(3)
    for col, row in zip(cols, summary.itertuples()):
        col.metric(row.payment_method, inr(row.total_collection), f"{row.share_pct}% · {int(row.no_of_payments)} payments",
                   delta_color="off")

    monthly = (payments.assign(month=payments["payment_date"].dt.to_period("M").dt.to_timestamp())
               .groupby(["month", "payment_method"])["amount_paid"].sum().reset_index())
    fig = px.bar(monthly, x="month", y="amount_paid", color="payment_method", title="Monthly collections by method",
                 labels={"amount_paid": "Collected (₹)", "month": "", "payment_method": ""},
                 color_discrete_map={"UPI": "#264653", "Card": "#2a9d8f", "Cash": "#e9c46a"})
    st.plotly_chart(fig, width="stretch")
    show_table(summary.assign(average_payment=summary["average_payment"].round(2)))
    with st.expander("All payment splits"):
        show_table(payments, height=400)


def page_sql_queries() -> None:
    st.header("Predefined SQL queries")
    if not is_super_admin():
        st.caption(f"Results are limited to the **{current_user()['branch_name']}** branch.")
    categories = ["Basic", "Aggregation", "Join", "Financial"]
    category = st.radio("Category", categories, horizontal=True)
    options = [(i, q) for i, q in enumerate(QUERIES, start=1) if q.category == category]
    idx, query = st.selectbox("Question", options, format_func=lambda o: f"Q{o[0]}. {o[1].question}")
    sql, params = render(query, scope_branch_id())
    with st.expander("View SQL", expanded=True):
        st.code(query.sql.format(cs="customer_sales", br="branches", ps="payment_splits"), language="sql")
    try:
        df = run_query(sql, params)
    except mysql.connector.Error as exc:
        st.error(f"Query failed: {exc.msg}")
        return
    st.caption(f"{len(df):,} row(s)")
    show_table(df)


# =====================================================================
# Main
# =====================================================================
PAGES = {
    "📈 Dashboard": page_dashboard,
    "➕ Add sale": page_add_sale,
    "💳 Add payment": page_add_payment,
    "📋 Sales report": page_sales_report,
    "⏳ Pending payments": page_pending,
    "💰 Payment summary": page_payment_summary,
    "🧮 SQL queries": page_sql_queries,
}


def main() -> None:
    user = current_user()
    if not user:
        login_page()
        return

    with st.sidebar:
        st.title("📊 Sales Hub")
        st.markdown(f"**{user['username']}**  \n{user['role']}"
                    + (f" · {user['branch_name']}" if user.get("branch_name") else " · All branches"))
        st.divider()
        page = st.radio("Navigate", list(PAGES), label_visibility="collapsed")
        st.divider()
        if st.button("Log out", width="stretch"):
            logout()

    try:
        PAGES[page]()
    except mysql.connector.Error as exc:
        st.error(f"Database error: {exc.msg}")


main()
