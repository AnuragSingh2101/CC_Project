"""
Matching service — find candidate inventory lots for an emergency blood request.

IMPORTANT MEDICAL DISCLAIMER:
NOT FOR CLINICAL USE. This candidate matching engine identifies prospective inventory
using ABO/Rh transfusion rules and component shelf-life data. It does NOT perform
crossmatch testing, antibody screening, or authorize transfusions. All allocations
require clinician sign-off and professional laboratory verification prior to issue.
"""
from datetime import date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from models.inventory import InventoryLot
from models.organization import Organization
from services.compatibility import get_donor_groups_in_priority_order, get_match_type
from services.geo import haversine_km
from config.settings import BLOOD_GROUPS, BLOOD_COMPONENTS
import logging

logger = logging.getLogger(__name__)


def find_matching_lots(
    db: Session,
    blood_group: str,
    units_needed: int,
    component: str = "whole_blood",
    requester_lat: Optional[float] = None,
    requester_lon: Optional[float] = None,
    max_radius_km: Optional[float] = None,
    city_filter: Optional[str] = None,
    max_results: int = 25
) -> List[Dict[str, Any]]:
    """
    Search candidate inventory lots for a blood request.

    Ranking Order:
    1. Exact match first, then compatible groups sorted by scarcity (e.g., O- last for red cells)
    2. Within each group priority, earliest expiry (First-Expiry-First-Out / FEFO)
    3. Distance if location coordinates provided

    Each result carries a 'match_type' field ('exact' or 'compatible').
    Only 'available' lots are returned.
    """
    if blood_group not in BLOOD_GROUPS:
        raise ValueError(f"Invalid blood group: {blood_group!r}")
    if component not in BLOOD_COMPONENTS:
        raise ValueError(f"Invalid component: {component!r}")

    donor_groups_ordered = get_donor_groups_in_priority_order(
        recipient_group=blood_group,
        component=component
    )

    candidates: List[Dict[str, Any]] = []

    for priority_idx, (d_group, match_type) in enumerate(donor_groups_ordered):
        lots = (
            db.query(InventoryLot, Organization)
            .join(Organization, InventoryLot.blood_bank_id == Organization.id)
            .filter(
                InventoryLot.blood_group == d_group,
                InventoryLot.component == component,
                InventoryLot.status == "available",
                InventoryLot.expiry_date >= date.today(),
                InventoryLot.units_total > InventoryLot.units_reserved,
            )
            .all()
        )

        for lot, org in lots:
            available = lot.available_units
            if available <= 0:
                continue

            if city_filter and org.city.lower() != city_filter.strip().lower():
                continue

            distance_km = None
            if (requester_lat is not None and requester_lon is not None
                    and org.latitude is not None and org.longitude is not None):
                distance_km = haversine_km(
                    requester_lat, requester_lon, org.latitude, org.longitude
                )
                if max_radius_km is not None and distance_km > max_radius_km:
                    continue

            candidates.append({
                "lot_id": lot.id,
                "blood_bank_id": org.id,
                "blood_bank_name": org.name,
                "city": org.city,
                "state": org.state,
                "blood_group": lot.blood_group,
                "component": lot.component,
                "requested_blood_group": blood_group,
                "requested_component": component,
                "match_type": match_type,
                "available_units": available,
                "collection_date": lot.collection_date,
                "expiry_date": lot.expiry_date,
                "can_allocate": min(available, units_needed),
                "distance_km": distance_km,
                "group_priority": priority_idx,
                "contact_number": org.contact_number,
                "disclaimer": (
                    "NOT FOR CLINICAL USE — Candidate match only. "
                    "Requires clinician sign-off prior to transfusion."
                ),
            })

    # Sort order:
    # 1. group_priority (0 = exact, 1+ = compatible ordered by scarcity)
    # 2. expiry_date asc (FEFO - first expiry first out)
    # 3. distance_km asc (if available)
    candidates.sort(key=lambda c: (
        c["group_priority"],
        c["expiry_date"],
        c["distance_km"] if c["distance_km"] is not None else 999999,
        -c["available_units"]
    ))

    return candidates[:max_results]
