"""
Blood Bank Search page — find candidate blood banks with available inventory.
Supports distance calculations from user's location/city, radius filtering,
ABO/Rh component compatibility ranking, and interactive map view.
"""
import streamlit as st
import pandas as pd

from services.auth_service import require_login, get_current_user
from services.matching_service import find_matching_lots
from services.geo import INDIAN_CITIES
from database.connection import get_session
from models.organization import Organization
from config.settings import BLOOD_GROUPS, BLOOD_COMPONENTS

require_login()
user = get_current_user()

st.markdown('<div class="page-header"><h2>🔍 Blood Bank & Component Search</h2></div>', unsafe_allow_html=True)

st.markdown("""
<div class="disclaimer">
⚕️ <strong>CLINICAL TRANSFUSION DISCLAIMER:</strong>
Search results are <em>candidate inventory lots only</em>.
Transfusion compatibility must be verified through laboratory crossmatch testing and clinician sign-off.
This platform does NOT perform clinical validation.
</div>
""", unsafe_allow_html=True)

db = get_session()
try:
    # ── Search Form ────────────────────────────────────────────
    st.subheader("Search Parameters")
    with st.form("search_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            search_bg = st.selectbox("Target Blood Group *", BLOOD_GROUPS)
        with col2:
            search_comp = st.selectbox(
                "Blood Component *",
                BLOOD_COMPONENTS,
                format_func=lambda c: c.replace("_", " ").title()
            )
        with col3:
            search_units = st.number_input("Units Needed *", min_value=1, max_value=500, value=2)

        st.markdown("##### 📍 Location & Proximity Filters")
        loc_col1, loc_col2, loc_col3 = st.columns(3)

        # Get list of organizations for "my location" option
        orgs = db.query(Organization).filter(Organization.latitude.isnot(None)).all()
        org_names = {f"{o.name} ({o.city})": o for o in orgs}

        with loc_col1:
            loc_mode = st.radio("Search Center Method", ["My Organization", "Known City", "City Text Fallback"], horizontal=True)

        ref_lat = None
        ref_lon = None
        city_filter_param = None

        with loc_col2:
            if loc_mode == "My Organization":
                # Find current user org if available
                default_idx = 0
                org_keys = list(org_names.keys())
                for idx, k in enumerate(org_keys):
                    if org_names[k].id == user.get('organization_id'):
                        default_idx = idx
                        break
                selected_org_key = st.selectbox("Select Center Org", org_keys, index=default_idx if org_keys else 0)
                if org_keys:
                    sel_o = org_names[selected_org_key]
                    ref_lat, ref_lon = sel_o.latitude, sel_o.longitude
                    st.caption(f"Coordinates: `{ref_lat:.4f}, {ref_lon:.4f}`")
            elif loc_mode == "Known City":
                selected_city = st.selectbox("Select City", list(INDIAN_CITIES.keys()))
                ref_lat, ref_lon = INDIAN_CITIES[selected_city]
                st.caption(f"Coordinates: `{ref_lat:.4f}, {ref_lon:.4f}`")
            else:
                city_filter_param = st.text_input("City Name (Fallback)", placeholder="e.g. Bengaluru, Mumbai, Pune")

        with loc_col3:
            enable_radius = st.checkbox("Filter by Radius (km)", value=False)
            radius_km = st.slider("Maximum Radius (km)", min_value=10, max_value=800, value=150, step=10) if enable_radius else None

        search_submitted = st.form_submit_button("🔍 Search Matching Inventory", type="primary")

    if search_submitted:
        with st.spinner("Searching compatible candidate inventory..."):
            candidates = find_matching_lots(
                db=db,
                blood_group=search_bg,
                units_needed=search_units,
                component=search_comp,
                requester_lat=ref_lat,
                requester_lon=ref_lon,
                max_radius_km=radius_km,
                city_filter=city_filter_param if (loc_mode == "City Text Fallback" and city_filter_param) else None,
                max_results=30
            )

        if candidates:
            st.success(f"Found {len(candidates)} candidate inventory match(es) for {search_units} units of {search_bg} ({search_comp.replace('_', ' ').title()}).")

            # ── Results Table ──
            res_rows = []
            map_data = []

            for c in candidates:
                badge = "🟢 EXACT" if c['match_type'] == "exact" else "🟡 COMPATIBLE"
                dist_str = f"{c['distance_km']} km" if c['distance_km'] is not None else "—"
                res_rows.append({
                    "Match": badge,
                    "Blood Bank": c["blood_bank_name"],
                    "City": c["city"],
                    "Stock Group": c["blood_group"],
                    "Component": c["component"].replace("_", " ").title(),
                    "Available Units": c["available_units"],
                    "Expiry Date": c["expiry_date"],
                    "Distance": dist_str,
                    "Contact": c["contact_number"] or "—",
                    "Lot ID": c["lot_id"]
                })

                # Fetch org coordinates for map
                org_obj = db.get(Organization, c["blood_bank_id"])
                if org_obj and org_obj.latitude and org_obj.longitude:
                    map_data.append({
                        "name": f"{org_obj.name} ({c['blood_group']}, {c['available_units']} avail)",
                        "latitude": org_obj.latitude,
                        "longitude": org_obj.longitude,
                        "lat": org_obj.latitude,
                        "lon": org_obj.longitude,
                    })

            df_display = pd.DataFrame(res_rows)
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # ── Interactive Map View ──
            if map_data:
                st.subheader("🗺️ Geographic Map of Candidate Blood Banks")
                map_df = pd.DataFrame(map_data)
                # Streamlit built-in map
                st.map(map_df, latitude="latitude", longitude="longitude", zoom=6)
        else:
            st.warning(
                f"No candidate inventory found matching {search_bg} ({search_comp}) within the selected criteria."
            )

except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"Search page error: {e}", exc_info=True)
    st.error("An error occurred during search. Please check parameters and try again.")
finally:
    db.close()
