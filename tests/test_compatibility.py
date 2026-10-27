"""
Tests for ABO/Rh component-aware blood compatibility rules.
Covers red blood cells, plasma, platelets, and scarcity ranking (O- last).
"""
import pytest
from services.compatibility import (
    get_compatible_donor_groups,
    get_donor_groups_in_priority_order,
    get_match_type,
    is_compatible,
)


class TestRedCellCompatibility:
    """ABO/Rh red cell compatibility testing."""

    def test_o_negative_universal_donor(self):
        """O- red cells can be given to all recipient groups."""
        for recipient in ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]:
            assert is_compatible("O-", recipient, component="packed_red_cells")
            assert is_compatible("O-", recipient, component="whole_blood")

    def test_ab_positive_universal_recipient(self):
        """AB+ red cells can receive from all donor groups."""
        for donor in ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]:
            assert is_compatible(donor, "AB+", component="packed_red_cells")

    def test_o_negative_recipient_only_receives_o_negative(self):
        """O- recipient can only receive O- red cells."""
        assert is_compatible("O-", "O-", component="packed_red_cells")
        for donor in ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+"]:
            assert not is_compatible(donor, "O-", component="packed_red_cells")

    def test_rh_negative_cannot_receive_rh_positive(self):
        """A- recipient cannot receive A+ or O+ red cells."""
        assert not is_compatible("A+", "A-", component="packed_red_cells")
        assert not is_compatible("O+", "A-", component="packed_red_cells")

    def test_scarcity_ranking_o_negative_last_for_red_cells(self):
        """
        O- must be the LAST compatible substitute for red cell recipients
        to preserve universal donor stock.
        """
        # For A+ recipient: exact is A+, compatible are O+, A-, O- (O- last!)
        ordered = get_donor_groups_in_priority_order("A+", component="packed_red_cells")
        groups = [g for g, _ in ordered]
        assert groups[0] == "A+"  # exact first
        assert groups[-1] == "O-"  # O- last among compatible substitutes

        # For AB+ recipient: O- must also be last
        ab_ordered = get_donor_groups_in_priority_order("AB+", component="packed_red_cells")
        ab_groups = [g for g, _ in ab_ordered]
        assert ab_groups[0] == "AB+"
        assert ab_groups[-1] == "O-"

    def test_match_type_exact_vs_compatible(self):
        assert get_match_type("A+", "A+", component="packed_red_cells") == "exact"
        assert get_match_type("O+", "A+", component="packed_red_cells") == "compatible"
        assert get_match_type("O-", "A+", component="packed_red_cells") == "compatible"
        assert get_match_type("B+", "A+", component="packed_red_cells") is None


class TestPlasmaCompatibility:
    """Plasma compatibility rules (reversed relative to red cells)."""

    def test_ab_is_universal_plasma_donor(self):
        """AB plasma has no antibodies and can be given to all recipient groups."""
        for recipient in ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]:
            assert is_compatible("AB+", recipient, component="plasma")

    def test_ab_recipient_can_only_receive_ab_plasma(self):
        """AB recipient has both antigens; cannot receive anti-A or anti-B plasma."""
        assert is_compatible("AB+", "AB+", component="plasma")
        assert is_compatible("AB-", "AB+", component="plasma")
        assert not is_compatible("O+", "AB+", component="plasma")
        assert not is_compatible("A+", "AB+", component="plasma")
        assert not is_compatible("B+", "AB+", component="plasma")

    def test_o_recipient_can_receive_all_plasma(self):
        """O recipient red cells have no A or B antigens, so any plasma is compatible."""
        for donor in ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]:
            assert is_compatible(donor, "O+", component="plasma")

    def test_plasma_match_type(self):
        assert get_match_type("A+", "A+", component="plasma") == "exact"
        assert get_match_type("AB+", "A+", component="plasma") == "compatible"
        assert get_match_type("O+", "A+", component="plasma") is None
