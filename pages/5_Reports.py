"""
Reports & Activity page — system analytics and audit history.
Admin-only full view; blood banks and hospitals see relevant subsets.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

from services.auth_service import require_login, get_current_user
from services.audit_service import get_recent_logs
from database.connection import get_session
from models.organization import Organization
from models.inventory import InventoryLot
from models.emergency_request import EmergencyRequest
from models.reservation import Reservation
from config.settings import BLOOD_GROUPS

require_login()
user = get_current_user()
role = user['role']

st.markdown('<div class="page-header"><h2>📋 Reports & Activity</h2></div>', unsafe_allow_html=True)

db = get_session()
try:
    tab1, tab2, tab3 = st.tabs(["📊 Inventory Report", "🚨 Request Report", "📝 Audit Log"])

    with tab1:
        st.subheader("Inventory Summary by Blood Group")
        if role == "admin":
            lots = db.query(InventoryLot).all()
        else:
            lots = db.query(InventoryLot).filter(
                InventoryLot.blood_bank_id == user['organization_id']
            ).all()

        if lots:
            from datetime import date as today_date
            today = today_date.today()
            summary = {}
            for g in BLOOD_GROUPS:
                group_lots = [l for l in lots if l.blood_group == g]
                summary[g] = {
                    "Total Lots": len(group_lots),
                    "Total Units": sum(l.units_total for l in group_lots),
                    "Reserved": sum(l.units_reserved for l in group_lots),
                    "Available (non-expired)": sum(l.available_units for l in group_lots if l.expiry_date >= today),
                    "Expired Lots": sum(1 for l in group_lots if l.expiry_date < today),
                }
            summary_df = pd.DataFrame(summary).T.reset_index()
            summary_df.columns = ["Blood Group"] + list(summary_df.columns[1:])
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

            # Bar chart
            avail_data = summary_df[["Blood Group", "Available (non-expired)"]].copy()
            fig = px.bar(
                avail_data, x="Blood Group", y="Available (non-expired)",
                title="Available Units by Blood Group",
                color="Blood Group",
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                              font=dict(color="#1a2744"), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # Expiry analysis
            st.subheader("Expiry Analysis")
            expiry_data = []
            for l in lots:
                days_left = (l.expiry_date - today).days
                expiry_data.append({
                    "Lot ID": l.id,
                    "Blood Group": l.blood_group,
                    "Available": l.available_units,
                    "Expiry Date": l.expiry_date,
                    "Days Until Expiry": days_left,
                    "Status": "Expired" if days_left < 0 else ("Critical" if days_left <= 7 else ("Warning" if days_left <= 14 else "OK")),
                })
            expiry_df = pd.DataFrame(expiry_data).sort_values("Days Until Expiry")
            st.dataframe(expiry_df, use_container_width=True, hide_index=True)
        else:
            st.info("No inventory data available.")

    with tab2:
        st.subheader("Emergency Requests Summary")
        if role == "admin":
            requests = db.query(EmergencyRequest).all()
        elif role == "hospital":
            requests = db.query(EmergencyRequest).filter(
                EmergencyRequest.hospital_id == user['organization_id']
            ).all()
        else:
            # Blood bank: show all requests for matching context
            requests = db.query(EmergencyRequest).all()

        if requests:
            # Status breakdown
            status_counts = {}
            urgency_counts = {}
            blood_group_counts = {}
            for r in requests:
                status_counts[r.status] = status_counts.get(r.status, 0) + 1
                urgency_counts[r.urgency] = urgency_counts.get(r.urgency, 0) + 1
                blood_group_counts[r.blood_group] = blood_group_counts.get(r.blood_group, 0) + 1

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**By Status**")
                status_df = pd.DataFrame(
                    list(status_counts.items()),
                    columns=["Status", "Count"]
                )
                fig2 = px.pie(status_df, names="Status", values="Count",
                              color_discrete_sequence=["#c0392b", "#1a5276", "#1e8449", "#717d7e"])
                fig2.update_layout(paper_bgcolor="#ffffff", height=280)
                st.plotly_chart(fig2, use_container_width=True)
            with col2:
                st.markdown("**By Urgency**")
                urg_df = pd.DataFrame(
                    list(urgency_counts.items()),
                    columns=["Urgency", "Count"]
                )
                urg_colors = {"critical": "#c0392b", "urgent": "#e67e22", "routine": "#27ae60"}
                fig3 = go.Figure(go.Bar(
                    x=urg_df["Urgency"], y=urg_df["Count"],
                    marker_color=[urg_colors.get(u, "#95a5a6") for u in urg_df["Urgency"]],
                    text=urg_df["Count"], textposition="outside"
                ))
                fig3.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                                   font=dict(color="#1a2744"), height=280, margin=dict(t=20))
                st.plotly_chart(fig3, use_container_width=True)

            # Detailed request table
            st.subheader("Request Details")
            req_rows = []
            for r in requests:
                req_rows.append({
                    "Reference": r.reference,
                    "Hospital": r.hospital.name if r.hospital else "—",
                    "Blood Group": r.blood_group,
                    "Units": r.units_requested,
                    "Urgency": r.urgency,
                    "Status": r.status,
                    "Created": r.created_at.strftime("%Y-%m-%d") if r.created_at else "—",
                })
            st.dataframe(pd.DataFrame(req_rows), use_container_width=True, hide_index=True)

            # Reservations
            st.subheader("Reservation Summary")
            if role == "admin":
                res_all = db.query(Reservation).all()
            elif role == "blood_bank":
                res_all = db.query(Reservation).join(InventoryLot).filter(
                    InventoryLot.blood_bank_id == user['organization_id']
                ).all()
            else:
                req_ids = [r.id for r in requests]
                res_all = db.query(Reservation).filter(Reservation.request_id.in_(req_ids)).all()

            if res_all:
                res_status = {}
                for r in res_all:
                    res_status[r.status] = res_status.get(r.status, 0) + 1
                st.markdown("**Reservations by Status:**")
                st.write(res_status)
            else:
                st.info("No reservations found.")
        else:
            st.info("No requests found.")

    with tab3:
        st.subheader("System Audit Log")
        if role != "admin":
            st.info("Full audit log is available to administrators only.")
        else:
            logs = get_recent_logs(db, limit=100)
            if logs:
                from models.user import User as UserModel
                log_rows = []
                for l in logs:
                    log_rows.append({
                        "Time": l.created_at.strftime("%Y-%m-%d %H:%M:%S") if l.created_at else "—",
                        "User ID": l.user_id or "—",
                        "Action": l.action,
                        "Entity": f"{l.entity_type}:{l.entity_id}" if l.entity_type else "—",
                        "Details": (l.details or "")[:100],
                    })
                log_df = pd.DataFrame(log_rows)
                # Filter
                action_filter = st.selectbox(
                    "Filter by Action",
                    ["All"] + sorted(list({l.action for l in logs})),
                    key="log_action_filter"
                )
                if action_filter != "All":
                    log_df = log_df[log_df["Action"] == action_filter]
                st.dataframe(log_df, use_container_width=True, hide_index=True)
            else:
                st.info("No audit log entries yet.")

except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Reports page error: {e}", exc_info=True)
    st.error("Failed to load report data.")
finally:
    db.close()
