"""
Admin Dashboard — system-wide metrics, charts, and alerts.
Accessible only to admin role.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

from services.auth_service import require_role, get_current_user
from database.connection import get_session
from models.organization import Organization
from models.inventory import InventoryLot
from models.emergency_request import EmergencyRequest
from services.inventory_service import get_low_stock_lots, get_near_expiry_lots, get_available_units_by_group
from services.audit_service import get_recent_logs
from config.settings import BLOOD_GROUPS

require_role("admin")

st.markdown('<div class="page-header"><h2>📊 Admin Dashboard</h2></div>', unsafe_allow_html=True)

db = get_session()
try:
    # ── Key Metrics ──────────────────────────────────────────────
    hospitals = db.query(Organization).filter(Organization.type == "hospital").count()
    blood_banks = db.query(Organization).filter(Organization.type == "blood_bank").count()

    lots = db.query(InventoryLot).filter(InventoryLot.expiry_date >= date.today()).all()
    total_available = sum(l.available_units for l in lots)

    pending = db.query(EmergencyRequest).filter(EmergencyRequest.status == "pending").count()
    matched = db.query(EmergencyRequest).filter(EmergencyRequest.status == "matched").count()
    critical = db.query(EmergencyRequest).filter(
        EmergencyRequest.urgency == "critical",
        EmergencyRequest.status.in_(["pending", "matched"])
    ).count()

    low_stock = get_low_stock_lots(db)
    near_expiry = get_near_expiry_lots(db)

    # ── Metrics Row ────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Hospitals", hospitals)
    c2.metric("Blood Banks", blood_banks)
    c3.metric("Available Units", f"{total_available:,}")
    c4.metric("Pending Requests", pending)
    c5.metric("Critical Active", critical, delta_color="inverse")
    c6.metric("Near Expiry Lots", len(near_expiry), delta_color="inverse")

    st.divider()

    # ── Alerts ─────────────────────────────────────────────────
    alert_col1, alert_col2 = st.columns(2)

    with alert_col1:
        st.subheader("⚠️ Low Stock Alerts (Per Component)")
        if low_stock:
            low_df = pd.DataFrame([{
                "Lot ID": l.id,
                "Blood Group": l.blood_group,
                "Component": l.component.replace("_", " ").title(),
                "Available": l.available_units,
                "Blood Bank": l.blood_bank.name if l.blood_bank else "—",
                "Expiry": l.expiry_date,
            } for l in low_stock])
            st.dataframe(low_df, use_container_width=True, hide_index=True)
        else:
            st.success("No low stock lots detected.")

    with alert_col2:
        st.subheader("📅 Near-Expiry Lots (≤ 7 days)")
        if near_expiry:
            exp_df = pd.DataFrame([{
                "Lot ID": l.id,
                "Blood Group": l.blood_group,
                "Component": l.component.replace("_", " ").title(),
                "Available": l.available_units,
                "Expiry": l.expiry_date,
                "Blood Bank": l.blood_bank.name if l.blood_bank else "—",
            } for l in near_expiry])
            st.dataframe(exp_df, use_container_width=True, hide_index=True)
        else:
            st.success("No lots expiring within 7 days.")

    st.divider()

    # ── Charts ─────────────────────────────────────────────────
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("🩸 Available Units by Blood Group")
        units_by_group = get_available_units_by_group(db)
        groups = list(units_by_group.keys())
        values = [units_by_group[g] for g in groups]
        colors = ["#c0392b" if v > 0 else "#e0e3ed" for v in values]
        fig1 = go.Figure(go.Bar(
            x=groups, y=values,
            marker_color=colors,
            text=values, textposition="outside"
        ))
        fig1.update_layout(
            xaxis_title="Blood Group", yaxis_title="Units",
            plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
            font=dict(color="#1a2744"),
            height=300, margin=dict(t=20, b=20)
        )
        st.plotly_chart(fig1, use_container_width=True)

    with chart_col2:
        st.subheader("📋 Requests by Status")
        all_requests = db.query(EmergencyRequest).all()
        if all_requests:
            status_counts = {}
            for r in all_requests:
                status_counts[r.status] = status_counts.get(r.status, 0) + 1
            fig2 = px.pie(
                names=list(status_counts.keys()),
                values=list(status_counts.values()),
                color_discrete_sequence=["#c0392b", "#1a5276", "#1e8449", "#717d7e"]
            )
            fig2.update_layout(height=300, margin=dict(t=20, b=20), paper_bgcolor="#ffffff")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No request data yet.")

    chart_col3, chart_col4 = st.columns(2)

    with chart_col3:
        st.subheader("🚨 Requests by Urgency")
        if all_requests:
            urgency_counts = {}
            for r in all_requests:
                urgency_counts[r.urgency] = urgency_counts.get(r.urgency, 0) + 1
            urgency_colors = {"critical": "#c0392b", "urgent": "#e67e22", "routine": "#27ae60"}
            fig3 = go.Figure(go.Bar(
                x=list(urgency_counts.keys()),
                y=list(urgency_counts.values()),
                marker_color=[urgency_colors.get(k, "#95a5a6") for k in urgency_counts.keys()],
                text=list(urgency_counts.values()), textposition="outside"
            ))
            fig3.update_layout(
                xaxis_title="Urgency", yaxis_title="Count",
                plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                font=dict(color="#1a2744"), height=300, margin=dict(t=20, b=20)
            )
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No request data yet.")

    with chart_col4:
        st.subheader("📅 Expiry Timeline (next 30 days)")
        if near_expiry or lots:
            from datetime import timedelta
            cutoff = date.today() + timedelta(days=30)
            exp_lots = [l for l in lots if l.expiry_date <= cutoff]
            if exp_lots:
                exp_df2 = pd.DataFrame([{
                    "Blood Group": l.blood_group,
                    "Expiry Date": l.expiry_date,
                    "Available": l.available_units,
                } for l in exp_lots])
                fig4 = px.bar(
                    exp_df2, x="Expiry Date", y="Available", color="Blood Group",
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                fig4.update_layout(
                    plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                    font=dict(color="#1a2744"), height=300, margin=dict(t=20, b=20)
                )
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info("No lots expiring in next 30 days.")
        else:
            st.info("No inventory data.")

    st.divider()

    # ── Recent Audit Log ────────────────────────────────────────
    st.subheader("📝 Recent System Activity")
    logs = get_recent_logs(db, limit=20)
    if logs:
        log_df = pd.DataFrame([{
            "Time": l.created_at.strftime("%Y-%m-%d %H:%M") if l.created_at else "—",
            "Action": l.action,
            "Entity": f"{l.entity_type}:{l.entity_id}" if l.entity_type else "—",
            "Details": (l.details or "")[:80],
        } for l in logs])
        st.dataframe(log_df, use_container_width=True, hide_index=True)
    else:
        st.info("No audit activity recorded yet.")

except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Admin dashboard error: {e}", exc_info=True)
    st.error(f"Failed to load dashboard data. Please try refreshing.")
finally:
    db.close()
