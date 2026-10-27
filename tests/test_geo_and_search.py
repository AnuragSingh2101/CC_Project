"""
Tests for geographic calculations, haversine distance, and distance-sorted matching.
"""
import pytest
from datetime import date, timedelta
from services.geo import haversine_km, get_city_coordinates
from services.inventory_service import create_lot
from services.matching_service import find_matching_lots
from models.organization import Organization


class TestGeographicCalculations:
    """Haversine distance and city coordinates."""

    def test_haversine_same_point(self):
        """Distance between identical coordinates is 0.0 km."""
        assert haversine_km(12.9716, 77.5946, 12.9716, 77.5946) == 0.0

    def test_haversine_bengaluru_to_tumakuru(self):
        """Distance between Bengaluru and Tumakuru is approx 68-75 km."""
        d = haversine_km(12.9716, 77.5946, 13.3392, 77.1017)
        assert 65 < d < 75

    def test_haversine_bengaluru_to_mysuru(self):
        """Distance between Bengaluru and Mysuru is approx 130-150 km."""
        d = haversine_km(12.9716, 77.5946, 12.2958, 76.6394)
        assert 120 < d < 155

    def test_city_coordinates_lookup(self):
        coords = get_city_coordinates("Bengaluru")
        assert coords is not None
        assert abs(coords[0] - 12.9716) < 0.01

        # Case-insensitive
        assert get_city_coordinates("mumbai") is not None
        assert get_city_coordinates("NonExistentCity") is None


class TestDistanceSortedMatching:
    """Testing distance sorting in find_matching_lots."""

    def test_nearest_blood_bank_ranked_first(self, db, future_date):
        # Create 2 blood banks: one close (Tumakuru), one farther (Mangaluru)
        bb_near = Organization(
            name="Near Bank Tumakuru", type="blood_bank",
            city="Tumakuru", state="Karnataka",
            latitude=13.3392, longitude=77.1017, contact_number="111"
        )
        bb_far = Organization(
            name="Far Bank Mangaluru", type="blood_bank",
            city="Mangaluru", state="Karnataka",
            latitude=12.9141, longitude=74.8560, contact_number="222"
        )
        db.add_all([bb_near, bb_far])
        db.flush()

        # Both have exact A+ stock
        create_lot(db=db, blood_bank_id=bb_near.id, blood_group="A+", units_total=10, expiry_date=future_date)
        create_lot(db=db, blood_bank_id=bb_far.id, blood_group="A+", units_total=10, expiry_date=future_date)
        db.flush()

        # Query from Bengaluru coordinates
        bengaluru_lat, bengaluru_lon = 12.9716, 77.5946
        results = find_matching_lots(
            db=db,
            blood_group="A+",
            units_needed=2,
            component="whole_blood",
            requester_lat=bengaluru_lat,
            requester_lon=bengaluru_lon
        )

        assert len(results) >= 2
        # Nearest (Tumakuru ~70km) must appear before Far (Mangaluru ~300km)
        assert results[0]["blood_bank_id"] == bb_near.id
        assert results[0]["distance_km"] < results[1]["distance_km"]

    def test_radius_filter(self, db, future_date):
        # Blood bank 100km away should be excluded with radius 50km
        bb_near = Organization(
            name="Near Bank", type="blood_bank",
            city="Bengaluru", state="Karnataka",
            latitude=12.9750, longitude=77.6000, contact_number="111"
        )
        bb_far = Organization(
            name="Far Bank", type="blood_bank",
            city="Tumakuru", state="Karnataka",
            latitude=13.3392, longitude=77.1017, contact_number="222"
        )
        db.add_all([bb_near, bb_far])
        db.flush()

        create_lot(db=db, blood_bank_id=bb_near.id, blood_group="B+", units_total=5, expiry_date=future_date)
        create_lot(db=db, blood_bank_id=bb_far.id, blood_group="B+", units_total=5, expiry_date=future_date)
        db.flush()

        # With 10km radius from central Bengaluru, only Near Bank should be returned
        results = find_matching_lots(
            db=db,
            blood_group="B+",
            units_needed=2,
            component="whole_blood",
            requester_lat=12.9716,
            requester_lon=77.5946,
            max_radius_km=10.0
        )
        assert len(results) == 1
        assert results[0]["blood_bank_id"] == bb_near.id
