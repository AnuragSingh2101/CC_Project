"""
Compatibility service — Component-aware ABO/Rh transfusion compatibility rules.

IMPORTANT MEDICAL DISCLAIMER:
This table represents standard academic ABO/Rh compatibility rules for candidate
inventory matching. It is NOT for clinical use and does NOT replace pre-transfusion
cross-matching or clinician sign-off.
"""
from typing import Dict, List, Optional, Tuple
from config.settings import BLOOD_GROUPS, BLOOD_COMPONENTS

# Red Blood Cell (Whole Blood & Packed Red Cells) Compatibility
# Exact match is always preferred. Compatible substitutes are ordered such that
# universal donor O- is last among compatible groups to preserve scarce stock.
RED_CELL_COMPATIBILITY: Dict[str, Dict[str, List[str]]] = {
    "A+": {
        "exact": ["A+"],
        "compatible": ["O+", "A-", "O-"],
    },
    "A-": {
        "exact": ["A-"],
        "compatible": ["O-"],
    },
    "B+": {
        "exact": ["B+"],
        "compatible": ["O+", "B-", "O-"],
    },
    "B-": {
        "exact": ["B-"],
        "compatible": ["O-"],
    },
    "AB+": {
        "exact": ["AB+"],
        "compatible": ["A+", "B+", "O+", "AB-", "A-", "B-", "O-"],
    },
    "AB-": {
        "exact": ["AB-"],
        "compatible": ["A-", "B-", "O-"],
    },
    "O+": {
        "exact": ["O+"],
        "compatible": ["O-"],
    },
    "O-": {
        "exact": ["O-"],
        "compatible": [],
    },
}

# Plasma Compatibility
# In plasma, compatibility is reversed compared to red cells:
# AB plasma has no antibodies (universal plasma donor).
# O recipient can receive plasma from any group.
# AB recipient can only receive AB plasma.
# Scarce universal plasma (AB) is placed last among compatible groups to preserve stock.
PLASMA_COMPATIBILITY: Dict[str, Dict[str, List[str]]] = {
    "AB+": {
        "exact": ["AB+"],
        "compatible": ["AB-"],
    },
    "AB-": {
        "exact": ["AB-"],
        "compatible": ["AB+"],
    },
    "A+": {
        "exact": ["A+"],
        "compatible": ["A-", "AB+", "AB-"],
    },
    "A-": {
        "exact": ["A-"],
        "compatible": ["A+", "AB-", "AB+"],
    },
    "B+": {
        "exact": ["B+"],
        "compatible": ["B-", "AB+", "AB-"],
    },
    "B-": {
        "exact": ["B-"],
        "compatible": ["B+", "AB-", "AB+"],
    },
    "O+": {
        "exact": ["O+"],
        "compatible": ["O-", "A+", "B+", "A-", "B-", "AB+", "AB-"],
    },
    "O-": {
        "exact": ["O-"],
        "compatible": ["O+", "A-", "B-", "A+", "B+", "AB-", "AB+"],
    },
}

# Platelets Compatibility
# Platelets are suspended in plasma; ABO-identical is first choice,
# then compatible plasma/cell groups.
PLATELETS_COMPATIBILITY: Dict[str, Dict[str, List[str]]] = {
    "AB+": {
        "exact": ["AB+"],
        "compatible": ["AB-", "A+", "B+"],
    },
    "AB-": {
        "exact": ["AB-"],
        "compatible": ["AB+", "A-", "B-"],
    },
    "A+": {
        "exact": ["A+"],
        "compatible": ["A-", "AB+", "AB-"],
    },
    "A-": {
        "exact": ["A-"],
        "compatible": ["A+", "AB-", "AB+"],
    },
    "B+": {
        "exact": ["B+"],
        "compatible": ["B-", "AB+", "AB-"],
    },
    "B-": {
        "exact": ["B-"],
        "compatible": ["B+", "AB-", "AB+"],
    },
    "O+": {
        "exact": ["O+"],
        "compatible": ["O-", "A+", "B+"],
    },
    "O-": {
        "exact": ["O-"],
        "compatible": ["O+", "A-", "B-"],
    },
}


def _get_table_for_component(component: str) -> Dict[str, Dict[str, List[str]]]:
    if component == "plasma":
        return PLASMA_COMPATIBILITY
    elif component == "platelets":
        return PLATELETS_COMPATIBILITY
    else:
        # whole_blood and packed_red_cells use red cell compatibility
        return RED_CELL_COMPATIBILITY


def get_compatible_donor_groups(
    recipient_group: str,
    component: str = "whole_blood"
) -> Dict[str, List[str]]:
    """Return dictionary with 'exact' and 'compatible' donor blood groups."""
    table = _get_table_for_component(component)
    if recipient_group not in table:
        raise ValueError(f"Unknown recipient blood group: {recipient_group!r}")
    return table[recipient_group]


def get_donor_groups_in_priority_order(
    recipient_group: str,
    component: str = "whole_blood"
) -> List[Tuple[str, str]]:
    """
    Return ordered list of (donor_group, match_type).
    Exact match first, then compatible groups sorted by scarcity.
    """
    comp = get_compatible_donor_groups(recipient_group, component)
    ordered = [(g, "exact") for g in comp["exact"]]
    ordered.extend([(g, "compatible") for g in comp["compatible"]])
    return ordered


def get_match_type(
    donor_group: str,
    recipient_group: str,
    component: str = "whole_blood"
) -> Optional[str]:
    """
    Check match type: returns 'exact', 'compatible', or None if incompatible.
    """
    comp = get_compatible_donor_groups(recipient_group, component)
    if donor_group in comp["exact"]:
        return "exact"
    if donor_group in comp["compatible"]:
        return "compatible"
    return None


def is_compatible(
    donor_group: str,
    recipient_group: str,
    component: str = "whole_blood"
) -> bool:
    """Return True if donor blood group is compatible for recipient."""
    return get_match_type(donor_group, recipient_group, component) is not None
