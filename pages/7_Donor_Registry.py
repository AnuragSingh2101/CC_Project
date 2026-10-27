"""
Donor Registry page — voluntary donor management, 56-day eligibility engine,
appointment scheduling, and low-stock recruitment.
All donor records are synthetic demonstration data.
"""
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, timezone

from services.auth_service import require_login, get_current_user
from services.donor_service import (
    create_donor,
    get_donors_for_bank,
    get_donor_display_dict,
    book_appointment,
    get_appointments_for_bank,
    update_appointment_status,
    get_donors_needed,
)
from database.connection import get_session
from models.organization import Organization
from models.donor import Donor
from config.settings import BLOOD_GROUPS, DONOR_ELIGIBILITY_DAYS

require_login()
user = get_current_user()
role = user['role']

if role not in ("admin", "blood_bank"):
    st.error("Access denied. The Donor Registry is restricted to Blood Bank and Admin staff.")
    st.stop()

st.markdown('<div class="page-header"><h2>👥 Blood Donor Registry & Recruitment</h2></div>', unsafe_allow_html=True)

st.markdown("""
<div class="disclaimer">
📋 <strong>SYNTHETIC DATA NOTICE:</strong>
All donor records, contact numbers, and appointment logs are synthetic demonstration data.
Whole-blood donor eligibility strictly enforces the clinical <strong>56-day inter-donation interval</strong>.
</div>
""", unsafe_allow_html=True)

db = get_session()
try:
    current_org_id = user.get('organization_id')

    if role == "admin":
        banks = db.query(Organization).filter(Organization.type == "blood_bank").all()
        bank_map = {b.name: b.id for b in banks}
        sel_bank_name = st.selectbox("Select Blood Bank (Admin View)", list(bank_map.keys()))
        view_bank_id = bank_map[sel_bank_name]
    else:
        view_bank_id = current_org_id
        st.info(f"🏢 **Managing Donors for:** {user['organization_name']}")

    # ── Tabs: Donors Needed, Registered Donors, Register Donor, Appointments ──
    tab_needed, tab_list, tab_add, tab_appts = st.tabs(
        ["🚨 Donors Needed (Low Stock Alerts)", "📋 Registered Donors", "➕ Register Donor", "📅 Donation Appointments"]
    )

    with tab_needed:
        st.subheader("⚠️ Low-Stock Emergency Recruitment Panel")
        st.markdown(
            "Identifies blood groups below reserve threshold and lists **eligible donors (≥ 56 days)** in the same city."
        )
        needed_list = get_donors_needed(db, blood_bank_id=view_bank_id)
        if needed_list:
            for item in needed_list:
                with st.expander(
                    f"🔴 {item['blood_group']} DEFICIT: {item['current_stock']} units on hand ({item['deficit']} units needed in {item['city']}) — {item['eligible_donors_count']} Eligible Donors Found",
                    expanded=True
                ):
                    st.write(f"**Current Stock:** {item['current_stock']} units | **Required Threshold:** 10 units")
                    if item["donors"]:
                        d_rows = []
                        for d in item["donors"]:
                            d_rows.append({
                                "Name": d["name"],
                                "Blood Group": d["blood_group"],
                                "Phone": d["phone"],
                                "City": d["city"],
                                "Last Donation": d["last_donation_date"] or "First-Time Donor",
                                "Eligibility": d["eligibility_reason"],
                            })
                        st.dataframe(pd.DataFrame(d_rows), use_container_width=True, hide_index=True)
                    else:
                        st.warning(f"No eligible {item['blood_group']} donors found in {item['city']}.")
        else:
            st.success("✅ All blood group inventories meet or exceed safe reserve thresholds!")

    with tab_list:
        st.subheader("Registered Blood Donors")
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            filt_bg = st.selectbox("Filter Blood Group", ["All"] + BLOOD_GROUPS, key="donor_filter_bg")
        with col_filter2:
            filt_active = st.checkbox("Active Donors Only", value=True)

        donors = get_donors_for_bank(
            db,
            blood_bank_id=view_bank_id,
            blood_group=None if filt_bg == "All" else filt_bg,
            active_only=filt_active
        )

        if donors:
            d_display = [
                get_donor_display_dict(d, requesting_org_id=view_bank_id, user_role=role)
                for d in donors
            ]
            df_donors = pd.DataFrame([
                {
                    "ID": d["id"],
                    "Name": d["name"],
                    "Blood Group": d["blood_group"],
                    "Phone (Masked)": d["phone"],
                    "City": d["city"],
                    "Last Donation": d["last_donation_date"] or "Never",
                    "Status": "Active" if d["active"] else "Inactive",
                    "Consent": "Yes" if d["consent"] else "No",
                    "Eligible (56 Days)": "🟢 Eligible" if d["is_eligible"] else "🔴 Ineligible",
                    "Eligibility Details": d["eligibility_reason"],
                }
                for d in d_display
            ])
            st.dataframe(df_donors, use_container_width=True, hide_index=True)
        else:
            st.info("No donors registered for this blood bank.")

    with tab_add:
        st.subheader("➕ Register New Voluntary Donor")
        with st.form("add_donor_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                donor_name = st.text_input("Full Name *", placeholder="e.g. Ramesh Kumar")
            with col2:
                donor_bg = st.selectbox("Blood Group *", BLOOD_GROUPS, key="new_donor_bg")
            with col3:
                donor_phone = st.text_input("Contact Phone *", placeholder="+91-98450-12345")

            col4, col5 = st.columns(2)
            with col4:
                donor_city = st.text_input("City *", placeholder="e.g. Bengaluru, Tumakuru")
            with col5:
                has_donated = st.checkbox("Has previously donated whole blood?")
                last_don_date = st.date_input("Last Donation Date", value=date.today() - timedelta(days=60)) if has_donated else None

            consent_check = st.checkbox("Donor has signed digital voluntary consent agreement", value=True)
            active_check = st.checkbox("Profile is active", value=True)

            submit_donor = st.form_submit_button("Register Donor", type="primary")

        if submit_donor:
            db_act = get_session()
            try:
                new_d = create_donor(
                    db=db_act,
                    organization_id=view_bank_id,
                    name=donor_name,
                    blood_group=donor_bg,
                    phone=donor_phone,
                    city=donor_city,
                    last_donation_date=last_don_date,
                    consent=consent_check,
                    active=active_check,
                    user_id=user['id']
                )
                db_act.commit()
                st.success(f"✅ Registered donor {new_d.name} ({new_d.blood_group}) for this blood bank.")
                st.rerun()
            except Exception as e:
                db_act.rollback()
                st.error(f"Failed to register donor: {e}")
            finally:
                db_act.close()

    with tab_appts:
        st.subheader("📅 Donation Appointments & Booking")
        col_b1, col_b2 = st.columns([1, 1])

        with col_b1:
            st.markdown("##### Book New Appointment")
            eligible_donors = [d for d in get_donors_for_bank(db, view_bank_id) if get_donor_display_dict(d, requesting_org_id=view_bank_id, user_role=role)["is_eligible"]]
            if eligible_donors:
                donor_opts = {f"{d.name} ({d.blood_group}) - {d.city}": d.id for d in eligible_donors}
                with st.form("book_appt_form"):
                    sel_donor_label = st.selectbox("Select Eligible Donor", list(donor_opts.keys()))
                    sel_donor_id = donor_opts[sel_donor_label]
                    appt_date_val = st.date_input("Appointment Date", value=date.today() + timedelta(days=1))
                    appt_notes = st.text_input("Notes", placeholder="Morning slot, fasting not required")
                    submit_appt = st.form_submit_button("Book Appointment", type="primary")

                if submit_appt:
                    db_act = get_session()
                    try:
                        appt_dt = datetime.combine(appt_date_val, datetime.min.time(), tzinfo=timezone.utc)
                        appt_obj = book_appointment(
                            db=db_act,
                            donor_id=sel_donor_id,
                            blood_bank_id=view_bank_id,
                            appointment_date=appt_dt,
                            notes=appt_notes,
                            user_id=user['id']
                        )
                        db_act.commit()
                        st.success(f"✅ Appointment scheduled for {appt_date_val.isoformat()}!")
                        st.rerun()
                    except Exception as e:
                        db_act.rollback()
                        st.error(f"Booking failed: {e}")
                    finally:
                        db_act.close()
            else:
                st.warning("No eligible donors currently available to schedule.")

        with col_b2:
            st.markdown("##### Existing Appointments")
            appts = get_appointments_for_bank(db, view_bank_id)
            if appts:
                for ap in appts:
                    with st.expander(f"Appointment #{ap.id}: {ap.donor.name if ap.donor else '—'} ({ap.status.title()})"):
                        st.write(f"**Date:** {ap.appointment_date.strftime('%Y-%m-%d')}")
                        st.write(f"**Blood Group:** {ap.donor.blood_group if ap.donor else '—'}")
                        st.write(f"**Notes:** {ap.notes or 'None'}")
                        if ap.status == "scheduled":
                            if st.button("Mark Completed (Updates Last Donation Date)", key=f"comp_{ap.id}", type="primary"):
                                db_act = get_session()
                                try:
                                    update_appointment_status(
                                        db=db_act, appointment_id=ap.id, new_status="completed",
                                        user_id=user['id'], requesting_org_id=view_bank_id, user_role=role
                                    )
                                    db_act.commit()
                                    st.success("Appointment completed and donor record updated.")
                                    st.rerun()
                                except Exception as e:
                                    db_act.rollback()
                                    st.error(str(e))
                                finally:
                                    db_act.close()
            else:
                st.info("No scheduled appointments found.")

except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Donor Registry error: {e}", exc_info=True)
    st.error("Failed to load donor registry.")
finally:
    db.close()
