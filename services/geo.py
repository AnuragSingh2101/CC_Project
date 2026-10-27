"""
Geographic service — Haversine distance calculations and location coordinates.
"""
import math
from typing import Dict, List, Optional, Tuple, Any

# Reference coordinates for Indian cities
INDIAN_CITIES: Dict[str, Tuple[float, float]] = {
    "Bengaluru": (12.9716, 77.5946),
    "Tumakuru": (13.3392, 77.1017),
    "Mysuru": (12.2958, 76.6394),
    "Mangaluru": (12.9141, 74.8560),
    "Hubballi": (15.3647, 75.1240),
    "Belagavi": (15.8497, 74.4977),
    "Mumbai": (19.0760, 72.8777),
    "Pune": (18.5204, 73.8567),
    "Delhi": (28.6139, 77.2090),
    "Chennai": (13.0827, 80.2707),
    "Hyderabad": (17.3850, 78.4867),
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on the Earth (in km)
    using the Haversine formula.
    """
    R = 6371.0  # Earth's radius in kilometers
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


def get_city_coordinates(city_name: str) -> Optional[Tuple[float, float]]:
    """Get (lat, lon) coordinates for a known city name (case-insensitive)."""
    for city, coords in INDIAN_CITIES.items():
        if city.lower() == city_name.strip().lower():
            return coords
    return None
