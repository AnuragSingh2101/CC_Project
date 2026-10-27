"""
Transfers page — inter-bank blood stock transfers.
Blood bank users: request stock from other blood banks, approve/dispatch incoming transfers, and confirm receipt.
Admin users: monitor and manage all transfers across organizations.
"""
import streamlit as st
import pandas as pd

from services.auth_service import require_login, get_current_user
from services.transfer_service import (
    create_transfer_request,
    approve_transfer_request,
    reject_transfer_request,
    dispatch_transfer_request,
    receive_transfer_request,
    get_transfers_for_bank,
    get_all_transfers,
)
from database.connection import get_session
from models.organization import Organization
from config.settings import BLOOD_GROUPS, BLOOD_COMPONENTS, TRANSFER_STATUSES

require_login()
user = get_current_user()
role = user['role']

if role not in ("admin", "blood_bank"):
    st.error("Access denied. Inter-bank transfers are restricted to Blood Bank and Admin staff.")
    st.stop()

st.markdown('<div class="page-header"><h2>🔄 Inter-Bank Transfer Management</h2></div>', unsafe_allow_html=True)

db = get_session()
try:
    current_org_id = user.get('organization_id')

    # ── Tabs: Overview, Request Transfer, Manage Incoming, Manage Outgoing ──
    tab_overview, tab_new, tab_incoming, tab_outgoing = st.tabs(
        ["📋 Transfer Directory", "➕ Request Stock from Bank", "📥 Incoming Requests (Supplier)", "📤 Outgoing Requests (Requester)"]
    )

    with tab_overview:
        st.subheader("All Inter-Bank Transfers")
        if role == "admin":
            transfers = get_all_transfers(db)
        else:
            t_data = get_transfers_for_bank(db, current_org_id)
            transfers = t_data["incoming"] + t_data["outgoing"]

        if transfers:
            rows = []
            for t in transfers:
                rows.append({
                    "Ref": t.reference,
                    "Requesting Bank": t.requesting_org.name if t.requesting_org else "—",
                    "Supplying Bank": t.supplying_org.name if t.supplying_org else "—",
                    "Blood Group": t.blood_group,
                    "Component": t.component.replace("_", " ").title(),
                    "Units": t.units,
                    "Status": t.status.title(),
                    "Created At": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "—",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No transfer records found.")

    with tab_new:
        if role == "blood_bank":
            st.subheader("Request Blood Stock from Another Blood Bank")
            other_banks = db.query(Organization).filter(
                Organization.type == "blood_bank",
                Organization.id != current_org_id
            ).all()

            if other_banks:
                bank_map = {f"{b.name} ({b.city})": b.id for b in other_banks}
                with st.form("new_transfer_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        target_bank_label = st.selectbox("Supplying Blood Bank *", list(bank_map.keys()))
                        target_bank_id = bank_map[target_bank_label]
                        trf_bg = st.selectbox("Blood Group *", BLOOD_GROUPS)
                    with col2:
                        trf_comp = st.selectbox("Component *", BLOOD_COMPONENTS, format_func=lambda c: c.replace("_", " ").title())
                        trf_units = st.number_input("Units Needed *", min_value=1, max_value=100, value=2)

                    trf_notes = st.text_input("Transfer Justification / Notes", placeholder="e.g. Critical stock deficit replenishment")
                    submit_trf = st.form_submit_button("Submit Transfer Request", type="primary")

                if submit_trf:
                    db_act = get_session()
                    try:
                        trf_obj = create_transfer_request(
                            db=db_act,
                            requesting_org_id=current_org_id,
                            supplying_org_id=target_bank_id,
                            blood_group=trf_bg,
                            component=trf_comp,
                            units=trf_units,
                            notes=trf_notes,
                            user_id=user['id']
                        )
                        db_act.commit()
                        st.success(f"✅ Created transfer request {trf_obj.reference} for {trf_units} units of {trf_bg} {trf_comp}.")
                        st.rerun()
                    except Exception as e:
                        db_act.rollback()
                        st.error(f"Transfer creation failed: {e}")
                    finally:
                        db_act.close()
            else:
                st.warning("No other blood banks registered in the network.")
        else:
            st.info("Administrator oversight mode — blood bank staff initiate transfer requests.")

    with tab_incoming:
        st.subheader("Incoming Transfer Requests (Your Bank is Supplier)")
        if role == "blood_bank":
            incoming = get_transfers_for_bank(db, current_org_id)["incoming"]
        else:
            incoming = db.query(Organization).all() and get_all_transfers(db)

        pending_or_approved = [t for t in incoming if t.status in ("pending", "approved")]
        if pending_or_approved:
            for trf in pending_or_approved:
                with st.expander(f"Transfer {trf.reference} — {trf.units} units of {trf.blood_group} ({trf.component}) [{trf.status.upper()}]"):
                    st.write(f"**Requester:** {trf.requesting_org.name} ({trf.requesting_org.city})")
                    st.write(f"**Units:** {trf.units} | **Notes:** {trf.notes or 'None'}")

                    if trf.status == "pending":
                        act_col1, act_col2 = st.columns(2)
                        with act_col1:
                            if st.button("✅ Approve Transfer (Atomically Reserves Units)", key=f"app_{trf.id}", type="primary"):
                                db_act = get_session()
                                try:
                                    approve_transfer_request(
                                        db=db_act, transfer_id=trf.id,
                                        user_id=user['id'], user_org_id=current_org_id, user_role=role
                                    )
                                    db_act.commit()
                                    st.success(f"Transfer {trf.reference} approved and stock reserved.")
                                    st.rerun()
                                except Exception as e:
                                    db_act.rollback()
                                    st.error(f"Approval failed: {e}")
                                finally:
                                    db_act.close()
                        with act_col2:
                            if st.button("❌ Reject Transfer", key=f"rej_{trf.id}"):
                                db_act = get_session()
                                try:
                                    reject_transfer_request(
                                        db=db_act, transfer_id=trf.id,
                                        user_id=user['id'], user_org_id=current_org_id, user_role=role
                                    )
                                    db_act.commit()
                                    st.warning(f"Transfer {trf.reference} rejected.")
                                    st.rerun()
                                except Exception as e:
                                    db_act.rollback()
                                    st.error(f"Rejection failed: {e}")
                                finally:
                                    db_act.close()
                    elif trf.status == "approved":
                        if st.button("🚚 Dispatch Shipment (Mark In Transit)", key=f"disp_{trf.id}", type="primary"):
                            db_act = get_session()
                            try:
                                dispatch_transfer_request(
                                    db=db_act, transfer_id=trf.id,
                                    user_id=user['id'], user_org_id=current_org_id, user_role=role
                                )
                                db_act.commit()
                                st.success(f"Transfer {trf.reference} marked as In Transit.")
                                st.rerun()
                            except Exception as e:
                                db_act.rollback()
                                st.error(str(e))
                            finally:
                                db_act.close()
        else:
            st.info("No incoming transfer requests require action.")

    with tab_outgoing:
        st.subheader("Outgoing Transfer Requests (Your Bank is Requester)")
        if role == "blood_bank":
            outgoing = get_transfers_for_bank(db, current_org_id)["outgoing"]
        else:
            outgoing = get_all_transfers(db)

        if outgoing:
            for trf in outgoing:
                with st.expander(f"{trf.reference}: {trf.units} units of {trf.blood_group} from {trf.supplying_org.name} [{trf.status.upper()}]"):
                    st.write(f"**Supplier:** {trf.supplying_org.name} ({trf.supplying_org.city})")
                    st.write(f"**Status:** {trf.status.title()} | **Notes:** {trf.notes or 'None'}")

                    if trf.status in ("approved", "in_transit"):
                        if st.button("📦 Confirm Physical Receipt (Adds to Inventory)", key=f"rec_{trf.id}", type="primary"):
                            db_act = get_session()
                            try:
                                receive_transfer_request(
                                    db=db_act, transfer_id=trf.id,
                                    user_id=user['id'], user_org_id=current_org_id, user_role=role
                                )
                                db_act.commit()
                                st.success(f"Receipt confirmed for {trf.reference}! {trf.units} units added to your inventory.")
                                st.rerun()
                            except Exception as e:
                                db_act.rollback()
                                st.error(f"Receipt failed: {e}")
                            finally:
                                db_act.close()
        else:
            st.info("No outgoing transfer requests.")

except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Transfers page error: {e}", exc_info=True)
    st.error("Failed to load transfers.")
finally:
    db.close()
