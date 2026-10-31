"""
Reports & Activity page — system analytics and audit history.
Admin-only full view; blood banks and hospitals see relevant subsets.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta, datetime
from io import StringIO

from services.auth_service import require_login, get_current_user
from services.audit_service import get_recent_logs
from database.connection import get_session
from models.organization import Organization
from models.inventory import InventoryLot
from models.emergency_request import EmergencyRequest
from models.reservation import Reservation
from models.audit_log import AuditLog
from config.settings import BLOOD_GROUPS

require_login()
user = get_current_user()
role = user['role']

st.markdown('<div class="page-header"><h2>📋 Reports & Activity</h2></div>', unsafe_allow_html=True)

db = get_session()
try:
    # Helper: convert df to CSV bytes for download
    def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
        return df.to_csv(index=False).encode("utf-8")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Inventory Report", "🚨 Request Report",
        "📝 Audit Log", "📈 Demand Forecast"
    ])

    with tab1:
        st.subheader("Inventory Summary by Blood Group")
        if role == "admin":
            lots = db.query(InventoryLot).all()
        else:
            lots = db.query(InventoryLot).filter(
                InventoryLot.blood_bank_id == user['organization_id']
            ).all()

        if lots:
            today = date.today()
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

            # CSV Export
            st.download_button(
                "⬇️ Download Inventory CSV",
                data=df_to_csv_bytes(summary_df),
                file_name=f"inventory_report_{date.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True
            )

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
                    "Component": l.component,
                    "Available": l.available_units,
                    "Expiry Date": l.expiry_date,
                    "Days Until Expiry": days_left,
                    "Status": "Expired" if days_left < 0 else ("Critical" if days_left <= 7 else ("Warning" if days_left <= 14 else "OK")),
                })
            expiry_df = pd.DataFrame(expiry_data).sort_values("Days Until Expiry")
            st.dataframe(expiry_df, use_container_width=True, hide_index=True)

            st.download_button(
                "⬇️ Download Expiry CSV",
                data=df_to_csv_bytes(expiry_df),
                file_name=f"expiry_report_{date.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True
            )
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
                    "Component": r.component,
                    "Units": r.units_requested,
                    "Urgency": r.urgency,
                    "Status": r.status,
                    "Created": r.created_at.strftime("%Y-%m-%d") if r.created_at else "—",
                })
            req_df = pd.DataFrame(req_rows)
            st.dataframe(req_df, use_container_width=True, hide_index=True)

            st.download_button(
                "⬇️ Download Requests CSV",
                data=df_to_csv_bytes(req_df),
                file_name=f"requests_report_{date.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True
            )

            # HTML Print View
            with st.expander("🖨️ HTML Print View (for PDF via browser Print)"):
                html = req_df.to_html(index=False, border=0, classes="print-table")
                st.markdown(f"""
                <html>
                <head>
                <style>
                .print-table {{ width: 100%; border-collapse: collapse; font-family: Arial, sans-serif; }}
                .print-table th, .print-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .print-table th {{ background-color: #c0392b; color: white; }}
                @media print {{ .stButton, .stDownloadButton, .stExpander {{ display: none; }} }}
                </style>
                </head>
                <body>
                <h2>Emergency Requests Report — {date.today().strftime('%Y-%m-%d')}</h2>
                <p>Generated by {user['username']} ({user['role']})</p>
                {html}
                </body>
                </html>
                """, unsafe_allow_html=True)
                st.info("Use browser Print (Ctrl+P) to save as PDF. Hide sidebar for best results.")

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
            logs = get_recent_logs(db, limit=500)
            if logs:
                log_rows = []
                for l in logs:
                    log_rows.append({
                        "Time": l.created_at.strftime("%Y-%m-%d %H:%M:%S") if l.created_at else "—",
                        "User ID": l.user_id or "—",
                        "Action": l.action,
                        "Entity": f"{l.entity_type}:{l.entity_id}" if l.entity_type else "—",
                        "Details": (l.details or "")[:200],
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

                st.download_button(
                    "⬇️ Download Audit Log CSV",
                    data=df_to_csv_bytes(log_df),
                    file_name=f"audit_log_{date.today().isoformat()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("No audit log entries yet.")

    with tab4:
        st.subheader("Weekly Demand Trend & 4-Week Forecast")
        st.markdown("""
        <div class="disclaimer">
        ⚕️ <strong>FORECASTING DISCLAIMER:</strong>
        This is a simple statistical forecast based on historical request volumes.
        It does NOT account for seasonal variations, epidemics, policy changes, or clinical factors.
        Use for planning assistance only — not for clinical or procurement decisions.
        </div>
        """, unsafe_allow_html=True)

        # Get request history (last 26 weeks for better MA calculation)
        if role == "admin":
            hist_requests = db.query(EmergencyRequest).all()
        elif role == "hospital":
            hist_requests = db.query(EmergencyRequest).filter(
                EmergencyRequest.hospital_id == user['organization_id']
            ).all()
        else:
            # Blood bank: all requests
            hist_requests = db.query(EmergencyRequest).all()

        if hist_requests:
            # Build weekly time series per blood group
            today = date.today()
            cutoff = today - timedelta(weeks=26)
            hist_requests = [r for r in hist_requests if r.created_at and r.created_at.date() >= cutoff]

            if hist_requests:
                # Create weekly buckets
                weeks = []
                current = today
                for _ in range(26):
                    week_start = current - timedelta(days=current.weekday())
                    week_end = week_start + timedelta(days=6)
                    weeks.append((week_start, week_end))
                    current = week_start - timedelta(days=1)
                weeks.reverse()

                # Aggregate per blood group per week
                trend_data = {g: [] for g in BLOOD_GROUPS}
                for week_start, week_end in weeks:
                    for g in BLOOD_GROUPS:
                        count = sum(
                            1 for r in hist_requests
                            if r.blood_group == g
                            and r.created_at
                            and week_start <= r.created_at.date() <= week_end
                        )
                        trend_data[g].append({
                            "week_start": week_start,
                            "week_end": week_end,
                            "requests": count
                        })

                # Plot
                fig = go.Figure()
                colors = px.colors.qualitative.Set2

                for idx, g in enumerate(BLOOD_GROUPS):
                    if not any(d["requests"] > 0 for d in trend_data[g]):
                        continue
                    df = pd.DataFrame(trend_data[g])
                    df["week_label"] = df["week_start"].apply(lambda d: d.strftime("%Y-%m-%d"))

                    # Actual
                    fig.add_trace(go.Scatter(
                        x=df["week_label"],
                        y=df["requests"],
                        mode="lines+markers",
                        name=f"{g} (Actual)",
                        line=dict(color=colors[idx % len(colors)], width=2),
                        marker=dict(size=6),
                        opacity=0.8
                    ))

                    # 4-week moving average forecast
                    if len(df) >= 4:
                        df["ma4"] = df["requests"].rolling(window=4, min_periods=1).mean()
                        # Forecast next 4 weeks as the last MA value (naive forecast)
                        last_ma = df["ma4"].iloc[-1]
                        forecast_weeks = []
                        last_week = df["week_start"].iloc[-1]
                        for i in range(1, 5):
                            next_week = last_week + timedelta(weeks=i)
                            forecast_weeks.append(next_week.strftime("%Y-%m-%d"))

                        fig.add_trace(go.Scatter(
                            x=forecast_weeks,
                            y=[last_ma] * 4,
                            mode="lines+markers",
                            name=f"{g} (4-wk MA Forecast)",
                            line=dict(color=colors[idx % len(colors)], width=2, dash="dash"),
                            marker=dict(size=6, symbol="diamond"),
                            opacity=0.6
                        ))

                fig.update_layout(
                    title="Weekly Request Count by Blood Group (with 4-week MA Forecast)",
                    xaxis_title="Week Starting",
                    yaxis_title="Number of Requests",
                    hovermode="x unified",
                    plot_bgcolor="#ffffff",
                    paper_bgcolor="#ffffff",
                    font=dict(color="#1a2744"),
                    height=500,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

                # Summary table
                st.subheader("Weekly Summary & Forecast")
                summary_rows = []
                for g in BLOOD_GROUPS:
                    df = pd.DataFrame(trend_data[g])
                    if df["requests"].sum() == 0:
                        continue
                    recent_avg = df["requests"].tail(4).mean()
                    total_26w = df["requests"].sum()
                    ma4_val = df["requests"].rolling(4, min_periods=1).mean().iloc[-1] if len(df) >= 1 else 0
                    summary_rows.append({
                        "Blood Group": g,
                        "Total (26 wk)": int(total_26w),
                        "Avg Last 4 Wk": round(recent_avg, 1),
                        "4-Wk MA Forecast (next wk)": round(ma4_val, 1),
                    })
                if summary_rows:
                    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
            else:
                st.info("Insufficient request history for forecasting (need at least some requests in last 26 weeks).")
        else:
            st.info("No request data available for forecasting.")

except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Reports page error: {e}", exc_info=True)
    st.error("Failed to load report data.")
finally:
    db.close()