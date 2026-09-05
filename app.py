import hashlib
import time
from datetime import date

import pandas as pd
import streamlit as st

import auth
from config import (
    CATEGORIES,
    ENTERED_BY_OPTIONS,
    EXPENSE_FOR_OPTIONS,
    EXPENSE_TYPE_OPTIONS,
    PAID_BY_OPTIONS,
    PURCHASED_FOR_OPTIONS,
    ROLE_ADMIN,
    ROLE_BRIDE,
    ROLE_GROOM,
    ROLE_LABELS,
    SETTING_BRIDE_SEES_GROOM,
    SETTING_GROOM_SEES_BRIDE,
    STATUSES,
    WEDDING_DATE,
    WEDDING_LOCATION,
    WEDDING_TITLE,
)
from database import (
    add_expense,
    delete_expense,
    get_bool_setting,
    get_expenses,
    init_db,
    set_setting,
    update_expense,
)
from permissions import (
    allowed_entered_by_for_role,
    available_views,
    entered_by_filter_for_view,
)

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Wedding Expense Tracker",
    page_icon="💍",
    layout="wide",
)


# ============================================================
# GENERIC HELPERS
# ============================================================

def money(value):
    if value is None or pd.isna(value):
        value = 0

    return f"₹{value:,.0f}"


def make_signature(*parts):
    """A stable hash of a set of field values, used to detect an
    accidental duplicate form submission (e.g. a double click)."""

    joined = "|".join(str(p) for p in parts)
    return hashlib.sha256(joined.encode()).hexdigest()


def is_duplicate_submission(state_key, signature, cooldown_seconds=5):
    """
    Returns True if this exact signature was already submitted
    within the cooldown window — meaning this submission is very
    likely an accidental double-click / resubmit rather than a
    deliberate second entry.
    """

    last_signature = st.session_state.get(f"{state_key}_signature")
    last_time = st.session_state.get(f"{state_key}_time", 0)

    is_dup = (
        last_signature == signature
        and (time.time() - last_time) < cooldown_seconds
    )

    if not is_dup:
        st.session_state[f"{state_key}_signature"] = signature
        st.session_state[f"{state_key}_time"] = time.time()

    return is_dup


def load_dataframe(allowed_entered_by):
    rows = get_expenses(allowed_entered_by)

    columns = [
        "ID",
        "Date",
        "Entered By",
        "Expense For",
        "Purchased For",
        "Category",
        "Expense Type",
        "Description",
        "Vendor",
        "Qty",
        "Planned",
        "Actual",
        "Paid",
        "Pending",
        "Paid By",
        "Status",
        "Due Date",
        "Notes",
    ]

    if not rows:
        return pd.DataFrame(columns=columns)

    data = []

    for row in rows:
        actual = row["actual_amount"] or 0
        paid = row["paid_amount"] or 0

        data.append(
            {
                "ID": row["id"],
                "Date": row["expense_date"],
                "Entered By": row["entered_by"] or "",
                "Expense For": row["expense_for"] or "",
                "Purchased For": row["purchased_for"] or "",
                "Category": row["category"],
                "Expense Type": row["expense_type"] or "",
                "Description": row["description"],
                "Vendor": row["vendor"] or "",
                "Qty": row["quantity"] or 1,
                "Planned": row["planned_amount"] or 0,
                "Actual": actual,
                "Paid": paid,
                "Pending": max(actual - paid, 0),
                "Paid By": row["paid_by"] or "",
                "Status": row["status"],
                "Due Date": row["due_date"] or "",
                "Notes": row["notes"] or "",
            }
        )

    return pd.DataFrame(data)


# ============================================================
# SHARED WIDGETS
# ============================================================

def render_metrics_row(df):
    total_planned = df["Planned"].sum()
    total_actual = df["Actual"].sum()
    total_paid = df["Paid"].sum()
    total_pending = df["Pending"].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Planned", money(total_planned))
    col2.metric("Actual Expense", money(total_actual))
    col3.metric("Already Paid", money(total_paid))
    col4.metric("Pending", money(total_pending))


def render_settlement_summary(df):
    st.subheader("🤝 Settlement / Contribution Summary")

    if df.empty:
        st.caption("No data available for settlement summary.")
        return

    def paid_for(paid_by, expense_for):
        mask = (df["Paid By"] == paid_by) & (df["Expense For"] == expense_for)
        return df.loc[mask, "Paid"].sum()

    groom_for_groom = paid_for("Groom", "Groom")
    groom_for_bride = paid_for("Groom", "Bride")
    groom_for_shared = paid_for("Groom", "Shared")

    bride_for_bride = paid_for("Bride", "Bride")
    bride_for_groom = paid_for("Bride", "Groom")
    bride_for_shared = paid_for("Bride", "Shared")

    shared_paid = df.loc[df["Paid By"] == "Shared", "Paid"].sum()
    other_paid = df.loc[df["Paid By"] == "Other", "Paid"].sum()

    total_groom_contribution = groom_for_groom + groom_for_bride + groom_for_shared
    total_bride_contribution = bride_for_bride + bride_for_groom + bride_for_shared

    summary_table = pd.DataFrame(
        [
            {"Paid By": "Groom", "For": "Groom", "Amount": groom_for_groom},
            {"Paid By": "Groom", "For": "Bride", "Amount": groom_for_bride},
            {"Paid By": "Groom", "For": "Shared", "Amount": groom_for_shared},
            {"Paid By": "Bride", "For": "Bride", "Amount": bride_for_bride},
            {"Paid By": "Bride", "For": "Groom", "Amount": bride_for_groom},
            {"Paid By": "Bride", "For": "Shared", "Amount": bride_for_shared},
        ]
    )
    summary_table["Amount"] = summary_table["Amount"].apply(money)

    col1, col2 = st.columns(2)

    with col1:
        st.dataframe(summary_table, use_container_width=True, hide_index=True)

    with col2:
        st.metric("Total Groom Contribution", money(total_groom_contribution))
        st.metric("Total Bride Contribution", money(total_bride_contribution))
        if shared_paid:
            st.metric("Paid Directly as 'Shared'", money(shared_paid))
        if other_paid:
            st.metric("Paid by 'Other'", money(other_paid))

    st.caption(
        "Cross-payments highlight: "
        f"Bride paid for Groom: {money(bride_for_groom)} · "
        f"Groom paid for Bride: {money(groom_for_bride)}"
    )


# ============================================================
# ADD EXPENSE
# ============================================================

def add_expense_page(role):

    st.header("➕ Add Expense")

    is_admin = role == ROLE_ADMIN
    fixed_side = ROLE_LABELS[role].split(" ", 1)[1] if not is_admin else None

    with st.form("add_expense_form"):

        col1, col2, col3 = st.columns(3)

        with col1:
            expense_date = st.date_input("Expense Date", value=date.today())

            if is_admin:
                entered_by = st.selectbox(
                    "Entered By",
                    ENTERED_BY_OPTIONS,
                    help="Which side is recording this expense.",
                )
            else:
                entered_by = fixed_side
                st.text_input(
                    "Entered By",
                    value=f"{entered_by} (you)",
                    disabled=True,
                    help="This is fixed to the side you logged in as.",
                )

            expense_for = st.selectbox(
                "Expense For",
                EXPENSE_FOR_OPTIONS,
                help="Whose expense this is (may differ from who's paying or entering it).",
            )

        with col2:
            purchased_for = st.selectbox(
                "Purchased For",
                PURCHASED_FOR_OPTIONS,
                help="Who the item/service was actually purchased for.",
            )

            category = st.selectbox("Category", CATEGORIES)

            expense_type = st.selectbox(
                "Expense Type",
                EXPENSE_TYPE_OPTIONS,
                help="The specific item or service, e.g. Hotel, Photography.",
            )

        with col3:
            description = st.text_input(
                "Expense Description",
                placeholder="e.g. Mumbai → Indore Sleeper Train",
            )

            vendor = st.text_input(
                "Vendor / Provider",
                placeholder="e.g. IRCTC",
            )

            quantity = st.number_input(
                "Quantity", min_value=1.0, value=1.0, step=1.0
            )

        col1, col2, col3 = st.columns(3)

        with col1:
            planned_amount = st.number_input(
                "Planned Amount (₹)", min_value=0.0, step=500.0
            )

        with col2:
            actual_amount = st.number_input(
                "Actual Amount (₹)", min_value=0.0, step=500.0
            )

        with col3:
            paid_amount = st.number_input(
                "Paid Amount (₹)", min_value=0.0, step=500.0
            )

        col1, col2, col3 = st.columns(3)

        with col1:
            paid_by = st.selectbox("Paid By", PAID_BY_OPTIONS)

        with col2:
            status = st.selectbox("Status", STATUSES)

        with col3:
            due_date = st.date_input("Due Date", value=None)

        notes = st.text_area("Notes", placeholder="Any additional information...")

        submitted = st.form_submit_button(
            "💾 Save Expense", type="primary", use_container_width=True
        )

    if not submitted:
        return

    if not description.strip():
        st.error("Expense description is required.")
        return

    if actual_amount < paid_amount:
        st.error("Paid amount cannot be greater than actual amount.")
        return

    signature = make_signature(
        expense_date, entered_by, expense_for, purchased_for, category,
        expense_type, description.strip(), vendor.strip(), quantity,
        planned_amount, actual_amount, paid_amount, paid_by, status,
        due_date, notes.strip(),
    )

    if is_duplicate_submission("add_expense", signature):
        st.warning("This looks like a duplicate submission — it was not saved again.")
        return

    with st.spinner("💾 Saving expense..."):
        try:
            add_expense(
                expense_date=str(expense_date),
                entered_by=entered_by,
                expense_for=expense_for,
                purchased_for=purchased_for,
                category=category,
                expense_type=expense_type,
                description=description.strip(),
                vendor=vendor.strip(),
                quantity=quantity,
                planned_amount=planned_amount,
                actual_amount=actual_amount,
                paid_amount=paid_amount,
                paid_by=paid_by,
                status=status,
                due_date=str(due_date) if due_date else "",
                notes=notes.strip(),
            )
        except Exception as exc:
            st.error(f"Could not save the expense due to a database error: {exc}")
            return

    st.success("Expense added successfully.")
    st.rerun()


# ============================================================
# DASHBOARD
# ============================================================

def dashboard_page(df, view):

    st.header(f"📊 Wedding Expense Dashboard — {view}")

    if df.empty:
        st.info("No expenses to show for this view yet.")
        return

    render_metrics_row(df)

    st.divider()

    st.subheader("👰 Bride vs 🤵 Groom (by Expense For)")

    groom_total = df.loc[df["Expense For"] == "Groom", "Actual"].sum()
    bride_total = df.loc[df["Expense For"] == "Bride", "Actual"].sum()
    shared_total = df.loc[df["Expense For"] == "Shared", "Actual"].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("🤵 For Groom", money(groom_total))
    col2.metric("👰 For Bride", money(bride_total))
    col3.metric("🤝 Shared", money(shared_total))

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Expenses by Category")
        category_summary = (
            df.groupby("Category")["Actual"].sum().sort_values(ascending=False)
        )
        st.bar_chart(category_summary)

    with col2:
        st.subheader("Expense For — breakdown")
        for_summary = df.groupby("Expense For")["Actual"].sum()
        st.bar_chart(for_summary)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💳 Paid By — breakdown")
        payment_summary = (
            df.groupby("Paid By")["Paid"].sum().sort_values(ascending=False)
        )
        st.dataframe(
            payment_summary.reset_index(), use_container_width=True, hide_index=True
        )

    with col2:
        st.subheader("✍️ Entered By — breakdown")
        entered_summary = (
            df.groupby("Entered By")["Actual"].sum().sort_values(ascending=False)
        )
        st.dataframe(
            entered_summary.reset_index(), use_container_width=True, hide_index=True
        )

    st.divider()

    render_settlement_summary(df)


# ============================================================
# EXPENSE LIST
# ============================================================

def expense_list_page(df, role):

    st.header("📋 All Expenses")

    if df.empty:
        st.info("No expenses found for what you're permitted to see.")
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        entered_by_filter = st.multiselect(
            "Entered By",
            sorted(df["Entered By"].unique()),
            default=sorted(df["Entered By"].unique()),
        )

    with col2:
        expense_for_filter = st.multiselect(
            "Expense For",
            sorted(df["Expense For"].unique()),
            default=sorted(df["Expense For"].unique()),
        )

    with col3:
        category_filter = st.multiselect(
            "Category",
            sorted(df["Category"].unique()),
            default=sorted(df["Category"].unique()),
        )

    with col4:
        status_filter = st.multiselect(
            "Status",
            sorted(df["Status"].unique()),
            default=sorted(df["Status"].unique()),
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        purchased_for_filter = st.multiselect(
            "Purchased For",
            sorted(df["Purchased For"].unique()),
            default=sorted(df["Purchased For"].unique()),
        )

    with col2:
        paid_by_filter = st.multiselect(
            "Paid By",
            sorted(df["Paid By"].unique()),
            default=sorted(df["Paid By"].unique()),
        )

    with col3:
        expense_type_filter = st.multiselect(
            "Expense Type",
            sorted([t for t in df["Expense Type"].unique() if t]),
            default=sorted([t for t in df["Expense Type"].unique() if t]),
        )

    parsed_dates = pd.to_datetime(df["Date"], errors="coerce")
    min_date = parsed_dates.min()
    max_date = parsed_dates.max()

    date_range = None
    if pd.notna(min_date) and pd.notna(max_date):
        date_range = st.date_input(
            "Date range",
            value=(min_date.date(), max_date.date()),
        )

    filtered_df = df[
        df["Entered By"].isin(entered_by_filter)
        & df["Expense For"].isin(expense_for_filter)
        & df["Purchased For"].isin(purchased_for_filter)
        & df["Category"].isin(category_filter)
        & df["Status"].isin(status_filter)
        & df["Paid By"].isin(paid_by_filter)
        & (df["Expense Type"].isin(expense_type_filter) | (df["Expense Type"] == ""))
    ]

    if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
        row_dates = pd.to_datetime(filtered_df["Date"], errors="coerce")
        filtered_df = filtered_df[
            (row_dates.dt.date >= start) & (row_dates.dt.date <= end)
        ]

    st.metric("Filtered Expenses (Actual)", money(filtered_df["Actual"].sum()))

    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    csv = filtered_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇️ Download CSV (only what you can see)",
        data=csv,
        file_name=f"wedding_expenses_{role}.csv",
        mime="text/csv",
    )


# ============================================================
# EDIT / DELETE
# ============================================================

def manage_expenses_page(role):

    st.header("✏️ Manage Expenses")

    is_admin = role == ROLE_ADMIN

    if is_admin:
        editable_allowed = None
        st.caption("As Admin, you can edit or delete any expense.")
    else:
        own_side = ROLE_LABELS[role].split(" ", 1)[1]
        editable_allowed = [own_side]
        st.caption(
            f"You can edit or delete expenses entered by **{own_side}** only. "
            "This is independent of visibility settings — those only control "
            "what you can *view*, not what you can edit."
        )

    rows = get_expenses(editable_allowed)

    if not rows:
        st.info("No editable expenses found.")
        return

    row_by_id = {row["id"]: row for row in rows}

    expense_options = {
        f'{row["id"]} — {row["description"]} — {money(row["actual_amount"] or 0)}': row["id"]
        for row in rows
    }

    selected_label = st.selectbox("Select Expense", list(expense_options.keys()))
    expense_id = expense_options[selected_label]
    selected = row_by_id[expense_id]

    st.divider()

    with st.form("edit_expense_form"):

        col1, col2, col3 = st.columns(3)

        with col1:
            expense_date = st.date_input(
                "Expense Date",
                value=date.fromisoformat(selected["expense_date"]),
            )

            if is_admin:
                entered_by = st.selectbox(
                    "Entered By",
                    ENTERED_BY_OPTIONS,
                    index=ENTERED_BY_OPTIONS.index(selected["entered_by"])
                    if selected["entered_by"] in ENTERED_BY_OPTIONS
                    else 0,
                )
            else:
                entered_by = selected["entered_by"]
                st.text_input("Entered By", value=entered_by, disabled=True)

            expense_for = st.selectbox(
                "Expense For",
                EXPENSE_FOR_OPTIONS,
                index=EXPENSE_FOR_OPTIONS.index(selected["expense_for"])
                if selected["expense_for"] in EXPENSE_FOR_OPTIONS
                else 0,
            )

        with col2:
            purchased_for = st.selectbox(
                "Purchased For",
                PURCHASED_FOR_OPTIONS,
                index=PURCHASED_FOR_OPTIONS.index(selected["purchased_for"])
                if selected["purchased_for"] in PURCHASED_FOR_OPTIONS
                else 0,
            )

            category = st.selectbox(
                "Category",
                CATEGORIES,
                index=CATEGORIES.index(selected["category"])
                if selected["category"] in CATEGORIES
                else 0,
            )

            expense_type_value = selected["expense_type"] or EXPENSE_TYPE_OPTIONS[0]
            expense_type = st.selectbox(
                "Expense Type",
                EXPENSE_TYPE_OPTIONS,
                index=EXPENSE_TYPE_OPTIONS.index(expense_type_value)
                if expense_type_value in EXPENSE_TYPE_OPTIONS
                else 0,
            )

        with col3:
            description = st.text_input("Description", value=selected["description"])
            vendor = st.text_input("Vendor", value=selected["vendor"] or "")
            quantity = st.number_input(
                "Quantity", min_value=1.0, value=float(selected["quantity"] or 1)
            )

        col1, col2, col3 = st.columns(3)

        with col1:
            planned_amount = st.number_input(
                "Planned Amount",
                min_value=0.0,
                value=float(selected["planned_amount"] or 0),
                step=500.0,
            )

        with col2:
            actual_amount = st.number_input(
                "Actual Amount",
                min_value=0.0,
                value=float(selected["actual_amount"] or 0),
                step=500.0,
            )

        with col3:
            paid_amount = st.number_input(
                "Paid Amount",
                min_value=0.0,
                value=float(selected["paid_amount"] or 0),
                step=500.0,
            )

        col1, col2, col3 = st.columns(3)

        with col1:
            paid_by = st.selectbox(
                "Paid By",
                PAID_BY_OPTIONS,
                index=PAID_BY_OPTIONS.index(selected["paid_by"])
                if selected["paid_by"] in PAID_BY_OPTIONS
                else 0,
            )

        with col2:
            status = st.selectbox(
                "Status",
                STATUSES,
                index=STATUSES.index(selected["status"]),
            )

        with col3:
            due_date_value = (
                date.fromisoformat(selected["due_date"]) if selected["due_date"] else None
            )
            due_date = st.date_input("Due Date", value=due_date_value)

        notes = st.text_area("Notes", value=selected["notes"] or "")

        submitted = st.form_submit_button(
            "💾 Update Expense", type="primary", use_container_width=True
        )

    if submitted:
        if actual_amount < paid_amount:
            st.error("Paid amount cannot be greater than actual amount.")
            return

        signature = make_signature(
            "update", expense_id, expense_date, entered_by, expense_for,
            purchased_for, category, expense_type, description, vendor,
            quantity, planned_amount, actual_amount, paid_amount, paid_by,
            status, due_date, notes,
        )

        if is_duplicate_submission("update_expense", signature):
            st.warning("This looks like a duplicate submission — it was not saved again.")
            return

        with st.spinner("💾 Updating expense..."):
            try:
                update_expense(
                    expense_id=expense_id,
                    expense_date=str(expense_date),
                    entered_by=entered_by,
                    expense_for=expense_for,
                    purchased_for=purchased_for,
                    category=category,
                    expense_type=expense_type,
                    description=description,
                    vendor=vendor,
                    quantity=quantity,
                    planned_amount=planned_amount,
                    actual_amount=actual_amount,
                    paid_amount=paid_amount,
                    paid_by=paid_by,
                    status=status,
                    due_date=str(due_date) if due_date else "",
                    notes=notes,
                )
            except Exception as exc:
                st.error(f"Could not update the expense due to a database error: {exc}")
                return

        st.success("Expense updated.")
        st.rerun()

    st.divider()

    if st.session_state.get("confirm_delete_id") != expense_id:
        if st.button("🗑️ Delete This Expense", type="secondary"):
            st.session_state.confirm_delete_id = expense_id
            st.rerun()
    else:
        st.warning("Are you sure you want to delete this expense? This cannot be undone.")
        col_a, col_b = st.columns(2)

        with col_a:
            if st.button("✅ Yes, delete it", type="primary", use_container_width=True):
                with st.spinner("🗑️ Deleting..."):
                    try:
                        delete_expense(expense_id)
                    except Exception as exc:
                        st.error(f"Could not delete the expense: {exc}")
                        return

                st.session_state.confirm_delete_id = None
                st.success("Expense deleted.")
                st.rerun()

        with col_b:
            if st.button("✖️ Cancel", use_container_width=True):
                st.session_state.confirm_delete_id = None
                st.rerun()


# ============================================================
# SUMMARY
# ============================================================

def category_summary_page(df):

    st.header("📈 Expense Summary")

    if df.empty:
        st.info("No expenses found.")
        return

    summary = df.groupby(
        ["Expense For", "Category"], as_index=False
    ).agg(
        Planned=("Planned", "sum"),
        Actual=("Actual", "sum"),
        Paid=("Paid", "sum"),
        Pending=("Pending", "sum"),
    )

    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Category-wise Expense")

    category_chart = (
        df.groupby("Category")["Actual"].sum().sort_values(ascending=False)
    )
    st.bar_chart(category_chart)

    st.divider()

    st.subheader("Entered By vs Expense For")

    cross_tab = pd.pivot_table(
        df,
        index="Entered By",
        columns="Expense For",
        values="Actual",
        aggfunc="sum",
        fill_value=0,
    )
    st.dataframe(cross_tab, use_container_width=True)


# ============================================================
# ADMIN PANEL
# ============================================================

def admin_panel_page():

    st.header("⚙️ Admin Panel")

    st.subheader("👁️ Visibility Settings")

    st.caption(
        "By default, Groom and Bride can each only see expenses their own "
        "side entered. Enable the toggles below to let one side see the "
        "other's entries."
    )

    current_groom_sees_bride = get_bool_setting(SETTING_GROOM_SEES_BRIDE)
    current_bride_sees_groom = get_bool_setting(SETTING_BRIDE_SEES_GROOM)

    with st.form("visibility_settings_form"):
        groom_sees_bride = st.checkbox(
            "Groom can see Bride expenses",
            value=current_groom_sees_bride,
        )
        bride_sees_groom = st.checkbox(
            "Bride can see Groom expenses",
            value=current_bride_sees_groom,
        )

        save_settings = st.form_submit_button(
            "💾 Save Settings", type="primary", use_container_width=True
        )

    if save_settings:
        with st.spinner("💾 Saving settings..."):
            set_setting(SETTING_GROOM_SEES_BRIDE, "1" if groom_sees_bride else "0")
            set_setting(SETTING_BRIDE_SEES_GROOM, "1" if bride_sees_groom else "0")
        st.success("Visibility settings saved.")
        st.rerun()

    st.info(
        f"**Current status**\n\n"
        f"- Groom → Bride: {'ENABLED ✅' if current_groom_sees_bride else 'DISABLED ⛔'}\n"
        f"- Bride → Groom: {'ENABLED ✅' if current_bride_sees_groom else 'DISABLED ⛔'}"
    )

    st.divider()

    st.subheader("📊 Full Dataset (Admin view — unrestricted)")

    df = load_dataframe(allowed_entered_by=None)

    if df.empty:
        st.info("No expenses recorded yet.")
        return

    render_metrics_row(df)

    col1, col2, col3 = st.columns(3)
    col1.metric("For Groom", money(df.loc[df["Expense For"] == "Groom", "Actual"].sum()))
    col2.metric("For Bride", money(df.loc[df["Expense For"] == "Bride", "Actual"].sum()))
    col3.metric("Shared", money(df.loc[df["Expense For"] == "Shared", "Actual"].sum()))

    col1, col2 = st.columns(2)
    col1.metric(
        "Entered by Groom", money(df.loc[df["Entered By"] == "Groom", "Actual"].sum())
    )
    col2.metric(
        "Entered by Bride", money(df.loc[df["Entered By"] == "Bride", "Actual"].sum())
    )

    st.divider()

    st.subheader("All Expenses")
    st.dataframe(df, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Export Complete Dataset (CSV)",
        data=csv,
        file_name="wedding_expenses_full_export.csv",
        mime="text/csv",
        type="primary",
    )


# ============================================================
# NAVIGATION STATE HELPERS
# ============================================================

PAGE_OPTIONS = [
    "📊 Dashboard",
    "➕ Add Expense",
    "📋 All Expenses",
    "✏️ Manage Expenses",
    "📈 Summary",
]
ADMIN_PAGE = "⚙️ Admin Panel"


def _set_page():
    st.session_state.current_page = st.session_state["_page_radio"]


def _set_admin_page():
    st.session_state.current_page = ADMIN_PAGE


# ============================================================
# MAIN APPLICATION
# ============================================================

init_db()

if not auth.login():
    st.stop()

role = auth.current_role()

if "current_page" not in st.session_state:
    st.session_state.current_page = PAGE_OPTIONS[0]

if "current_view" not in st.session_state:
    st.session_state.current_view = "Overall"

# Sidebar
with st.sidebar:
    st.title("💍 Wedding Tracker")
    st.caption(f"{WEDDING_TITLE}\n\nWedding: {WEDDING_DATE}\n\nLocation: {WEDDING_LOCATION}")
    st.caption(f"Logged in as: **{ROLE_LABELS[role]}**")

    st.divider()

    views = available_views(role)
    if st.session_state.current_view not in views:
        st.session_state.current_view = views[0]

    st.subheader("View")
    view = st.radio(
        "View",
        views,
        key="current_view",
        label_visibility="collapsed",
    )

    st.divider()

    st.subheader("Pages")
    default_index = (
        PAGE_OPTIONS.index(st.session_state.current_page)
        if st.session_state.current_page in PAGE_OPTIONS
        else 0
    )
    st.radio(
        "Pages",
        PAGE_OPTIONS,
        index=default_index,
        key="_page_radio",
        label_visibility="collapsed",
        on_change=_set_page,
    )

    if role == ROLE_ADMIN:
        st.divider()
        st.subheader("Admin")
        st.button(
            ADMIN_PAGE,
            use_container_width=True,
            type="primary" if st.session_state.current_page == ADMIN_PAGE else "secondary",
            on_click=_set_admin_page,
        )

    st.divider()

    if st.button("🔒 Lock Application", use_container_width=True):
        auth.logout()
        st.rerun()


# Resolve current page (radio takes priority once user interacts with it,
# admin button can override — both write into the same session_state key).
page = st.session_state.current_page

# Data scoped to the role's visibility permissions + the selected view.
allowed_for_view = entered_by_filter_for_view(role, view)
view_df = load_dataframe(allowed_for_view)

# Page routing
if page == ADMIN_PAGE and role == ROLE_ADMIN:
    admin_panel_page()
elif page == "📊 Dashboard":
    dashboard_page(view_df, view)
elif page == "➕ Add Expense":
    add_expense_page(role)
elif page == "📋 All Expenses":
    expense_list_page(view_df, role)
elif page == "✏️ Manage Expenses":
    manage_expenses_page(role)
elif page == "📈 Summary":
    category_summary_page(view_df)
else:
    # Fallback: a non-admin somehow landed on the admin page (e.g. role
    # changed mid-session) — never render admin content for them.
    st.session_state.current_page = PAGE_OPTIONS[0]
    st.rerun()
