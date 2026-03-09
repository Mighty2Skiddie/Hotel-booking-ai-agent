import json
import os
import time
import random
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HOTELS_FILE = os.path.join(DATA_DIR, "hotels.json")

_data = None


def _load():
    global _data
    if _data is None:
        with open(HOTELS_FILE, "r", encoding="utf-8") as f:
            _data = json.load(f)
    return _data


def search_hotels_api(city, checkin, checkout, guests=2):
    """search hotels by city + dates, returns dict with hotels list"""
    time.sleep(random.uniform(0.1, 0.3))

    data = _load()
    key = city.strip().lower()

    city_data = data.get("cities", {}).get(key)
    if not city_data:
        return {"hotels": [], "city": city, "message": f"No hotels found in {city}."}

    out = []
    for h in city_data["hotels"]:
        # filter by guest capacity — at least one room type should fit
        ok = any(r["max_guests"] >= guests for r in h["rooms"])
        if not ok:
            continue

        out.append({
            "hotel_id": h["hotel_id"],
            "name": h["name"],
            "star_rating": h["star_rating"],
            "location": h["location"],
            "base_price": h["base_price"],
            "currency": h["currency"],
            "description": h["description"],
        })

    return {
        "hotels": out,
        "city": city.title(),
        "checkin": checkin,
        "checkout": checkout,
        "guests": guests,
    }


def check_availability_api(hotel_id, checkin, checkout):
    time.sleep(random.uniform(0.1, 0.3))
    data = _load()

    for city_data in data["cities"].values():
        for h in city_data["hotels"]:
            if h["hotel_id"] != hotel_id:
                continue

            rooms = []
            for r in h["rooms"]:
                avail = max(0, r["max_available"] - random.randint(0, 2))
                rooms.append({
                    "room_type": r["room_type"],
                    "available_rooms": avail,
                    "max_guests": r["max_guests"],
                    "bed_type": r["bed_type"],
                    "size_sqft": r["size_sqft"],
                    "pricing": r["pricing"],
                })

            # calc nights
            try:
                d_in = datetime.strptime(checkin, "%Y-%m-%d")
                d_out = datetime.strptime(checkout, "%Y-%m-%d")
                nights = (d_out - d_in).days
            except ValueError:
                nights = 1

            for r in rooms:
                r["total_pricing"] = {
                    tier: price * nights for tier, price in r["pricing"].items()
                }
                r["nights"] = nights

            return {
                "hotel_id": hotel_id,
                "hotel_name": h["name"],
                "checkin": checkin,
                "checkout": checkout,
                "nights": nights,
                "rooms": rooms,
            }

    return {"hotel_id": hotel_id, "error": f"Hotel {hotel_id} not found.", "rooms": []}


def get_hotel_details_api(hotel_id):
    """returns amenities, policies, landmarks etc for a hotel"""
    time.sleep(random.uniform(0.05, 0.15))
    data = _load()

    for city_data in data["cities"].values():
        for h in city_data["hotels"]:
            if h["hotel_id"] == hotel_id:
                out = {
                    "hotel_id": h["hotel_id"],
                    "name": h["name"],
                    "star_rating": h["star_rating"],
                    "location": h["location"],
                    "description": h["description"],
                    "amenities": h["amenities"],
                    "policies": h["policies"],
                    "nearby_landmarks": h["nearby_landmarks"],
                }
                return out

    return {"hotel_id": hotel_id, "error": f"Hotel {hotel_id} not found."}
