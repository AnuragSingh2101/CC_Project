"""
Emergency Registry page — create, view, cancel blood requests and manage reservations.
Hospitals: create, view, cancel their own requests and reserve matching units.
Admin/Blood bank: view all requests, manage fulfillment.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from services.auth_service import require_login, get_current_user
from services.request_service import (
    create_request, get_requests_for_hospital, get_all_requests,
    cancel_request, update_request_status
)
from services.reservation_service import (
    make_reservation, release_reservation, fulfill_reservation,
    get_reservations_for_request
)
from services.matching_service import find_matching_lots
from database.connection import get_session
from models.emergency_request import EmergencyRequest
from models.organization import Organization
from config.settings import BLOOD_GROUPS, BLOOD_COMPONENTS, URGENCY_LEVELS, REQUEST_STATUSES

require_login()
user = get_current_user()
role = user['role']

st.markdown('<div class="page-header"><h2>🚨 Emergency Blood Registry</h2></div>', unsafe_allow_html=True)

st.markdown("""
<div class="disclaimer">
⚕️ <strong>CLINICAL TRANSFUSION DISCLAIMER:</strong>
This platform coordinates candidate inventory for emergency logistics. It is <strong>NOT for clinical use</strong>
and does not replace ABO/Rh typing, crossmatching, antibody testing, or bedside clinician sign-off.
</div>
""", unsafe_allow_html=True)

db = get_session()
try:
    # ── Hospital: Create Request ────────────────────────────────
    if role == "hospital":
        st.subheader("📝 Submit New Emergency Blood Request")
        with st.form("create_request_form"):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                req_bg = st.selectbox("Blood Group *", BLOOD_GROUPS)
            with col2:
                req_comp = st.selectbox(
                    "Component *",
                    BLOOD_COMPONENTS,
                    format_func=lambda c: c.replace("_", " ").title()
                )
            with col3:
                req_units = st.number_input("Units Required *", min_value=1, max_value=500, value=1)
            with col4:
                req_urgency = st.selectbox("Urgency *", URGENCY_LEVELS)

            col5, col6 = st.columns(2)
            with col5:
                use_deadline = st.checkbox("Set Required-By Deadline")
            with col6:
                req_deadline = st.date_input("Required By Date") if use_deadline else None

            req_notes = st.text_area(
                "Clinical Notes (optional)", max_chars=500,
                placeholder="Trauma details, surgery timing, ward contact..."
            )
            submit_req = st.form_submit_button("🚨 Submit Request", type="primary")

        if submit_req:
            db_act = get_session()
            try:
                deadline_dt = (
                    datetime.combine(req_deadline, datetime.min.time(), tzinfo=timezone.utc)
                    if req_deadline else None
                )
                new_req = create_request(
                    db=db_act,
                    hospital_id=user['organization_id'],
                    blood_group=req_bg,
                    units_requested=req_units,
                    urgency=req_urgency,
                    component=req_comp,
                    required_by=deadline_dt,
                    notes=req_notes,
                    user_id=user['id']
                )
                db_act.commit()
                st.success(f"✅ Emergency request created: Ref {new_req.reference} ({req_units} units of {req_bg} {req_comp})")
                st.rerun()
            except Exception as e:
                db_act.rollback()
                st.error(f"Failed to submit request: {e}")
            finally:
                db_act.close()

    # ── Requests Table ─────────────────────────────────────────
    st.subheader("Active & Past Blood Requests")

    with st.expander("Filter Requests", expanded=False):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            filter_status = st.selectbox("Status", ["All"] + REQUEST_STATUSES)
        with fc2:
            filter_urgency = st.selectbox("Urgency", ["All"] + URGENCY_LEVELS)
        with fc3:
            filter_bg_req = st.selectbox("Blood Group", ["All"] + BLOOD_GROUPS)

    status_filter = None if filter_status == "All" else filter_status
    urgency_filter = None if filter_urgency == "All" else filter_urgency
    bg_filter = None if filter_bg_req == "All" else filter_bg_req

    if role == "hospital":
        requests = get_requests_for_hospital(
            db,
            hospital_id=user['organization_id'],
            status=status_filter,
            urgency=urgency_filter
        )
    else:
        requests = get_all_requests(
            db,
            status=status_filter,
            urgency=urgency_filter,
            blood_group=bg_filter
        )

    if requests:
        req_rows = []
        for r in requests:
            req_rows.append({
                "Ref": r.reference,
                "Hospital": r.hospital.name if r.hospital else "—",
                "Blood Group": r.blood_group,
                "Component": r.component.replace("_", " ").title(),
                "Units Needed": r.units_requested,
                "Urgency": r.urgency.title(),
                "Status": r.status.title(),
                "Created At": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "—",
                "ID": r.id
            })
        req_df = pd.DataFrame(req_rows)
        st.dataframe(req_df.drop(columns=["ID"]), use_container_width=True, hide_index=True)

        st.divider()

        # ── Request Actions & Candidate Search ────────────────────
        st.subheader("🎯 Manage Request & Allocate Stock")
        req_map = {f"{r.reference} — {r.blood_group} {r.component.replace('_', ' ').title()} ({r.units_requested} units, {r.urgency}) [{r.status}]": r for r in requests}
        selected_label = st.selectbox("Select Request", list(req_map.keys()))
        selected_req = req_map[selected_label]

        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown(f"**Hospital:** {selected_req.hospital.name if selected_req.hospital else '—'}")
            st.markdown(f"**Blood Group:** `{selected_req.blood_group}` | **Component:** `{selected_req.component.replace('_', ' ').title()}`")
            st.markdown(f"**Units:** `{selected_req.units_requested}` | **Status:** `{selected_req.status}`")
            if selected_req.notes:
                st.markdown(f"**Notes:** {selected_req.notes}")

            # Cancel button (hospital for own request, or admin)
            can_cancel = (role == "admin") or (role == "hospital" and selected_req.hospital_id == user['organization_id'])
            if can_cancel and selected_req.status in ("pending", "matched"):
                if st.button("❌ Cancel Request & Release Stock", type="secondary"):
                    db_cancel = get_session()
                    try:
                        cancel_request(
                            db=db_cancel,
                            request_id=selected_req.id,
                            user_id=user['id'],
                            hospital_id=user['organization_id'] if role == "hospital" else None
                        )
                        db_cancel.commit()
                        st.success(f"Request {selected_req.reference} cancelled.")
                        st.rerun()
                    except Exception as e:
                        db_cancel.rollback()
                        st.error(f"Cancellation failed: {e}")
                    finally:
                        db_cancel.close()

        with col_right:
            # Active Reservations on this request
            reservations = get_reservations_for_request(db, selected_req.id)
            active_res = [res for res in reservations if res.status == "active"]
            total_reserved = sum(res.units_reserved for res in active_res)

            st.markdown(f"**Reserved Units:** `{total_reserved} / {selected_req.units_requested}`")
            for res in reservations:
                st.write(f"- Reservation #{res.id}: {res.units_reserved} units from Lot #{res.inventory_lot_id} [{res.status}]")
                if res.status == "active" and (role in ("admin", "blood_bank")):
                    if st.button(f"Fulfill Res #{res.id}", key=f"ful_{res.id}"):
                        db_ful = get_session()
                        try:
                            fulfill_reservation(db=db_ful, reservation_id=res.id, user_id=user['id'])
                            db_ful.commit()
                            st.success(f"Reservation #{res.id} marked as fulfilled.")
                            st.rerun()
                        except Exception as e:
                            db_ful.rollback()
                            st.error(str(e))
                        finally:
                            db_ful.close()

        # ── Candidate Inventory Lots (Compatibility Matching Engine) ──
        if selected_req.status in ("pending", "matched"):
            st.markdown("#### Candidate Matches (FEFO & Compatibility Ranked)")
            req_hosp = selected_req.hospital
            candidates = find_matching_lots(
                db=db,
                blood_group=selected_req.blood_group,
                component=selected_req.component,
                units_needed=selected_req.units_requested - total_reserved,
                requester_lat=req_hosp.latitude if req_hosp else None,
                requester_lon=req_hosp.longitude if req_hosp else None,
            )

            if candidates:
                cand_rows = []
                for c in candidates:
                    dist_str = f"{c['distance_km']} km" if c['distance_km'] is not None else "—"
                    match_badge = "🟢 EXACT" if c['match_type'] == "exact" else "🟡 COMPATIBLE"
                    cand_rows.append({
                        "Match Type": match_badge,
                        "Blood Bank": c["blood_bank_name"],
                        "City": c["city"],
                        "Blood Group": c["blood_group"],
                        "Available": c["available_units"],
                        "Expiry Date": c["expiry_date"],
                        "Distance": dist_str,
                        "Lot ID": c["lot_id"]
                    })
                c_df = pd.DataFrame(cand_rows)
                st.dataframe(c_df, use_container_width=True, hide_index=True)

                # Reservation action
                if role in ("hospital", "admin"):
                    st.markdown("##### Reserve Units from Candidate Lot")
                    with st.form("reserve_form"):
                        cand_options = {
                            f"Lot #{c['lot_id']} at {c['blood_bank_name']} ({c['blood_group']}, {c['available_units']} avail, expires {c['expiry_date']}) [{c['match_type'].upper()}]": c
                            for c in candidates if c['available_units'] > 0
                        }
                        if cand_options:
                            sel_cand_label = st.selectbox("Choose Lot to Reserve", list(cand_options.keys()))
                            sel_cand = cand_options[sel_cand_label]
                            max_can_res = min(sel_cand['available_units'], selected_req.units_requested - total_reserved)
                            units_to_res = st.number_input(
                                "Units to Reserve",
                                min_value=1,
                                max_value=max(1, max_can_res),
                                value=max(1, max_can_res)
                            )
                            submit_res = st.form_submit_button("🔒 Reserve Units (Oversell-Safe)", type="primary")

                            if submit_res:
                                db_res = get_session()
                                try:
                                    res_obj = make_reservation(
                                        db=db_res,
                                        request_id=selected_req.id,
                                        inventory_lot_id=sel_cand['lot_id'],
                                        units_to_reserve=units_to_res,
                                        user_id=user['id']
                                    )
                                    db_res.commit()
                                    st.success(f"✅ Reserved {units_to_res} units from Lot #{sel_cand['lot_id']}!")
                                    st.rerun()
                                except Exception as e:
                                    db_res.rollback()
                                    st.error(f"Reservation failed: {e}")
                                finally:
                                    db_res.close()
            else:
                st.warning("No candidate inventory lots currently match this request.")
    else:
        st.info("No blood requests found.")

except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Emergency Registry error: {e}", exc_info=True)
    st.error("Failed to load emergency registry.")
finally:
    db.close()
