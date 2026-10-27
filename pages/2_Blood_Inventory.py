"""
Blood Inventory page — view, add, and update inventory lots.
Includes component tracking, shelf-life auto-calculation, and lot status workflow.
Blood bank users: manage their own organization's inventory and lot status.
Admin: view all inventory across organizations.
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from services.auth_service import require_login, get_current_user
from services.inventory_service import (
    create_lot, get_lots_for_bank, get_all_lots, update_lot_quantity, update_lot_status
)
from database.connection import get_session
from models.organization import Organization
from config.settings import BLOOD_GROUPS, BLOOD_COMPONENTS, COMPONENT_SHELF_LIFE, LOT_STATUSES

require_login()
user = get_current_user()
role = user['role']

if role not in ("admin", "blood_bank"):
    st.error("Access denied. This page is for Blood Bank and Admin users.")
    st.stop()

st.markdown('<div class="page-header"><h2>🩸 Blood Inventory Management</h2></div>', unsafe_allow_html=True)

db = get_session()
try:
    # ── Filters ────────────────────────────────────────────────
    with st.expander("🔍 Filters & Search Options", expanded=True):
        fcol1, fcol2, fcol3, fcol4 = st.columns(4)
        with fcol1:
            filter_bg = st.selectbox("Blood Group", ["All"] + BLOOD_GROUPS, key="inv_bg_filter")
        with fcol2:
            filter_comp = st.selectbox("Component", ["All"] + BLOOD_COMPONENTS, key="inv_comp_filter")
        with fcol3:
            filter_status = st.selectbox("Lot Status", ["All"] + LOT_STATUSES, key="inv_status_filter")
        with fcol4:
            filter_expired = st.checkbox("Include Expired Lots", value=False, key="inv_expired")

        if role == "admin":
            banks = db.query(Organization).filter(Organization.type == "blood_bank").all()
            bank_options = {"All Blood Banks": None}
            bank_options.update({b.name: b.id for b in banks})
            filter_bank_name = st.selectbox("Select Blood Bank (Admin)", list(bank_options.keys()), key="inv_bank_filter")
            filter_bank_id = bank_options[filter_bank_name]
        else:
            filter_bank_id = user['organization_id']
            st.info(f"🏢 **Managing Inventory for:** {user['organization_name']}")

    # ── Inventory Query ────────────────────────────────────────
    bg_filter = None if filter_bg == "All" else filter_bg
    comp_filter = None if filter_comp == "All" else filter_comp
    status_filter = None if filter_status == "All" else filter_status

    if role == "admin":
        lots = get_all_lots(
            db,
            include_expired=filter_expired,
            blood_group=bg_filter,
            blood_bank_id=filter_bank_id,
            component=comp_filter,
            status=status_filter
        )
    else:
        lots = get_lots_for_bank(
            db,
            blood_bank_id=filter_bank_id,
            include_expired=filter_expired,
            blood_group=bg_filter,
            component=comp_filter,
            status=status_filter
        )

    st.subheader(f"Inventory Lots ({len(lots)} records)")
    if lots:
        rows = []
        for l in lots:
            cond = "Expired" if l.is_expired else ("Low Stock" if l.available_units < 10 else "Normal")
            rows.append({
                "Lot ID": l.id,
                "Blood Group": l.blood_group,
                "Component": l.component.replace("_", " ").title(),
                "Status": l.status.title(),
                "Total Units": l.units_total,
                "Reserved": l.units_reserved,
                "Available": l.available_units,
                "Collection Date": l.collection_date,
                "Expiry Date": l.expiry_date,
                "Condition": cond,
                "Blood Bank": l.blood_bank.name if l.blood_bank else "—",
            })
        inv_df = pd.DataFrame(rows)

        def highlight_status(row):
            if row["Condition"] == "Expired" or row["Status"] == "Discarded":
                return ["background-color: #fdecea"] * len(row)
            elif row["Status"] == "Quarantine":
                return ["background-color: #fcf3cf"] * len(row)
            elif row["Condition"] == "Low Stock":
                return ["background-color: #fef9e7"] * len(row)
            return [""] * len(row)

        styled_df = inv_df.style.apply(highlight_status, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.info("No inventory lots found matching the selected filters.")

    st.divider()

    # ── Tabs for Actions (Blood Bank and Admin) ─────────────────
    tab_add, tab_status, tab_qty = st.tabs(["➕ Add New Lot", "🔄 Update Lot Status Workflow", "✏️ Adjust Lot Units"])

    with tab_add:
        if role in ("blood_bank", "admin"):
            st.markdown("#### Register New Blood Component Lot")
            with st.form("add_lot_form"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    new_bg = st.selectbox("Blood Group *", BLOOD_GROUPS)
                with col2:
                    new_comp = st.selectbox(
                        "Component *",
                        BLOOD_COMPONENTS,
                        format_func=lambda c: f"{c.replace('_', ' ').title()} ({COMPONENT_SHELF_LIFE[c]} days shelf life)"
                    )
                with col3:
                    new_units = st.number_input("Total Units *", min_value=1, max_value=10000, value=10, step=1)
                with col4:
                    new_coll_date = st.date_input("Collection Date *", value=date.today())

                col5, col6 = st.columns(2)
                with col5:
                    new_status = st.selectbox("Initial Status *", ["quarantine", "tested", "available"])
                with col6:
                    computed_shelf = COMPONENT_SHELF_LIFE.get(new_comp, 35)
                    auto_expiry = new_coll_date + timedelta(days=computed_shelf)
                    st.info(f"📅 **Computed Expiry Date:** {auto_expiry} ({computed_shelf} days from collection)")

                submitted = st.form_submit_button("Add Inventory Lot", type="primary")

            if submitted:
                db_action = get_session()
                try:
                    target_bank_id = user['organization_id'] if role == "blood_bank" else (filter_bank_id or lots[0].blood_bank_id if lots else 1)
                    lot = create_lot(
                        db=db_action,
                        blood_bank_id=target_bank_id,
                        blood_group=new_bg,
                        units_total=new_units,
                        component=new_comp,
                        collection_date=new_coll_date,
                        status=new_status,
                        user_id=user['id']
                    )
                    db_action.commit()
                    st.success(
                        f"✅ Created lot #{lot.id}: {new_bg} {new_comp} ({new_units} units) — Status: {new_status}, Expires: {lot.expiry_date}"
                    )
                    st.rerun()
                except Exception as e:
                    db_action.rollback()
                    st.error(f"Failed to create lot: {e}")
                finally:
                    db_action.close()

    with tab_status:
        st.markdown("#### Lot Status Workflow")
        st.markdown("""
        **Allowed transitions:**
        - `quarantine` ➔ `tested`
        - `tested` ➔ `available`
        - *Any status* ➔ `discarded`
        *(Only 'available' lots are eligible for reservations and search).*
        """)
        manageable_lots = [l for l in lots if (role == "admin" or l.blood_bank_id == user['organization_id']) and l.status != "discarded"]
        if manageable_lots:
            lot_status_map = {
                f"Lot #{l.id}: {l.blood_group} {l.component} | Current Status: {l.status} | Units: {l.units_total}": l
                for l in manageable_lots
            }
            with st.form("status_workflow_form"):
                selected_label = st.selectbox("Select Lot to Transition", list(lot_status_map.keys()))
                target_lot = lot_status_map[selected_label]

                # Determine next valid choices
                if target_lot.status == "quarantine":
                    next_choices = ["tested", "discarded"]
                elif target_lot.status == "tested":
                    next_choices = ["available", "discarded"]
                elif target_lot.status == "available":
                    next_choices = ["discarded"]
                else:
                    next_choices = []

                if next_choices:
                    next_status = st.selectbox("New Status", next_choices)
                    submit_status = st.form_submit_button("Update Status", type="primary")
                else:
                    st.info("Lot is in terminal state.")
                    submit_status = False

            if submit_status:
                db_action = get_session()
                try:
                    update_lot_status(
                        db=db_action,
                        lot_id=target_lot.id,
                        new_status=next_status,
                        user_id=user['id'],
                        requesting_org_id=user['organization_id'] if role != "admin" else None,
                        user_role=role
                    )
                    db_action.commit()
                    st.success(f"✅ Lot #{target_lot.id} status transitioned to '{next_status}'.")
                    st.rerun()
                except Exception as e:
                    db_action.rollback()
                    st.error(f"Status transition failed: {e}")
                finally:
                    db_action.close()
        else:
            st.info("No active lots available for status transition.")

    with tab_qty:
        st.markdown("#### Adjust Total Units")
        if lots:
            active_lots = [l for l in lots if (role == "admin" or l.blood_bank_id == user['organization_id']) and not l.is_expired and l.status != "discarded"]
            if active_lots:
                qty_lot_map = {
                    f"Lot #{l.id} — {l.blood_group} {l.component} (total: {l.units_total}, reserved: {l.units_reserved})": l
                    for l in active_lots
                }
                with st.form("update_qty_form"):
                    sel_qty_label = st.selectbox("Select Lot", list(qty_lot_map.keys()))
                    sel_lot = qty_lot_map[sel_qty_label]
                    new_total_qty = st.number_input("New Total Units", min_value=sel_lot.units_reserved, max_value=10000, value=sel_lot.units_total)
                    upd_qty_btn = st.form_submit_button("Update Quantity", type="primary")

                if upd_qty_btn:
                    db_action = get_session()
                    try:
                        update_lot_quantity(
                            db=db_action,
                            lot_id=sel_lot.id,
                            new_total=new_total_qty,
                            user_id=user['id'],
                            requesting_org_id=user['organization_id'] if role != "admin" else None
                        )
                        db_action.commit()
                        st.success(f"✅ Lot #{sel_lot.id} updated to {new_total_qty} units.")
                        st.rerun()
                    except Exception as e:
                        db_action.rollback()
                        st.error(f"Failed to update quantity: {e}")
                    finally:
                        db_action.close()
            else:
                st.info("No active lots eligible for quantity update.")

except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Inventory page error: {e}", exc_info=True)
    st.error("Failed to load inventory data.")
finally:
    db.close()
