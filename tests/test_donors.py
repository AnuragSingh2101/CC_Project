"""
Tests for donor registry, 56-day whole-blood eligibility, phone masking, and appointments.
Covers: day 55, 56, 57 edge cases, inactive donors, consent, and permissions.
"""
import pytest
from datetime import date, timedelta, datetime, timezone
from services.donor_service import (
    create_donor,
    is_donor_eligible,
    update_donor,
    get_donor_display_dict,
    book_appointment,
    update_appointment_status,
    get_donors_needed,
)
from models.donor import Donor


class TestDonorEligibility:
    """Testing 56-day eligibility threshold and edge cases."""

    def test_day_55_ineligible(self, db, seed_org):
        """At 55 days since last donation, donor is NOT eligible."""
        today = date.today()
        d = create_donor(
            db=db,
            organization_id=seed_org["blood_bank"].id,
            name="Donor 55",
            blood_group="O+",
            phone="9876543210",
            city="Bengaluru",
            last_donation_date=today - timedelta(days=55)
        )
        eligible, reason = is_donor_eligible(d, check_date=today)
        assert eligible is False
        assert "55 days" in reason
        assert "Eligible in 1 day(s)" in reason

    def test_day_56_eligible(self, db, seed_org):
        """At exactly 56 days, donor is eligible."""
        today = date.today()
        d = create_donor(
            db=db,
            organization_id=seed_org["blood_bank"].id,
            name="Donor 56",
            blood_group="O+",
            phone="9876543210",
            city="Bengaluru",
            last_donation_date=today - timedelta(days=56)
        )
        eligible, reason = is_donor_eligible(d, check_date=today)
        assert eligible is True
        assert "Eligible" in reason

    def test_day_57_eligible(self, db, seed_org):
        """At 57 days, donor is eligible."""
        today = date.today()
        d = create_donor(
            db=db,
            organization_id=seed_org["blood_bank"].id,
            name="Donor 57",
            blood_group="O+",
            phone="9876543210",
            city="Bengaluru",
            last_donation_date=today - timedelta(days=57)
        )
        eligible, reason = is_donor_eligible(d, check_date=today)
        assert eligible is True

    def test_first_time_donor_eligible(self, db, seed_org):
        """First-time donor with last_donation_date=None is eligible."""
        d = create_donor(
            db=db,
            organization_id=seed_org["blood_bank"].id,
            name="New Donor",
            blood_group="A+",
            phone="9876543210",
            city="Bengaluru",
            last_donation_date=None
        )
        eligible, reason = is_donor_eligible(d)
        assert eligible is True
        assert "first-time" in reason.lower()

    def test_inactive_or_no_consent_ineligible(self, db, seed_org):
        """Inactive donor or donor without consent is ineligible even if days > 56."""
        today = date.today()
        d1 = create_donor(
            db=db, organization_id=seed_org["blood_bank"].id,
            name="Inactive", blood_group="B+", phone="9876543210", city="Bengaluru",
            last_donation_date=today - timedelta(days=100), active=False
        )
        assert is_donor_eligible(d1)[0] is False

        d2 = create_donor(
            db=db, organization_id=seed_org["blood_bank"].id,
            name="No Consent", blood_group="B+", phone="9876543210", city="Bengaluru",
            last_donation_date=today - timedelta(days=100), consent=False
        )
        assert is_donor_eligible(d2)[0] is False


class TestDonorPrivacyAndManagement:
    """Phone masking and cross-organization access controls."""

    def test_phone_masked_for_other_orgs(self, db, seed_org):
        d = create_donor(
            db=db,
            organization_id=seed_org["blood_bank"].id,
            name="John Doe",
            blood_group="A+",
            phone="9845123456",
            city="Bengaluru"
        )
        # Other bank viewing -> masked phone
        view = get_donor_display_dict(d, requesting_org_id=9999, user_role="blood_bank")
        assert view["phone"] == "******3456"

        # Owning bank viewing -> plain phone
        view_owner = get_donor_display_dict(d, requesting_org_id=seed_org["blood_bank"].id, user_role="blood_bank")
        assert view_owner["phone"] == "9845123456"

        # Admin viewing -> plain phone
        view_admin = get_donor_display_dict(d, user_role="admin")
        assert view_admin["phone"] == "9845123456"

    def test_cross_org_donor_update_denied(self, db, seed_org):
        d = create_donor(
            db=db,
            organization_id=seed_org["blood_bank"].id,
            name="Original",
            blood_group="A+",
            phone="9845123456",
            city="Bengaluru"
        )
        with pytest.raises(PermissionError, match="only modify donors belonging to your blood bank"):
            update_donor(db=db, donor_id=d.id, requesting_org_id=8888, user_role="blood_bank", name="Hacked")


class TestDonorAppointments:
    """Booking donation appointments and updating completion."""

    def test_book_appointment_for_eligible_donor(self, db, seed_org):
        d = create_donor(
            db=db,
            organization_id=seed_org["blood_bank"].id,
            name="Eligible Donor",
            blood_group="O-",
            phone="9845123456",
            city="Bengaluru",
            last_donation_date=date.today() - timedelta(days=70)
        )
        appt_time = datetime.now(timezone.utc) + timedelta(days=1)
        appt = book_appointment(
            db=db,
            donor_id=d.id,
            blood_bank_id=seed_org["blood_bank"].id,
            appointment_date=appt_time
        )
        assert appt.id is not None
        assert appt.status == "scheduled"

        # Complete appointment -> updates donor's last_donation_date
        update_appointment_status(
            db=db,
            appointment_id=appt.id,
            new_status="completed",
            requesting_org_id=seed_org["blood_bank"].id
        )
        assert appt.status == "completed"
        assert d.last_donation_date == appt_time.date()

    def test_cannot_book_appointment_for_ineligible_donor(self, db, seed_org):
        d = create_donor(
            db=db,
            organization_id=seed_org["blood_bank"].id,
            name="Recent Donor",
            blood_group="O+",
            phone="9845123456",
            city="Bengaluru",
            last_donation_date=date.today() - timedelta(days=20)
        )
        appt_time = datetime.now(timezone.utc) + timedelta(days=1)
        with pytest.raises(ValueError, match="Donor is not eligible"):
            book_appointment(
                db=db,
                donor_id=d.id,
                blood_bank_id=seed_org["blood_bank"].id,
                appointment_date=appt_time
            )
