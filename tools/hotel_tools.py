from api.mock_api import search_hotels_api, check_availability_api, get_hotel_details_api
from cache.redis_client import cache_get, cache_set


# TODO: maybe move these to a config file at some point
# ttls feel kinda arbitrary right now

def search_hotels(city, checkin, checkout, guests=2):
    key = f"hotel:search:{city.lower().strip()}:{checkin}:{checkout}"

    cached = cache_get(key)
    if cached is not None:
        return cached

    res = search_hotels_api(city, checkin, checkout, guests)
    cache_set(key, res, 600)
    return res


def check_availability(hotel_id, checkin, checkout):
    # key = f"hotel:avail:{hotel_id}:{checkin}:{checkout}"  # old format
    key = f"hotel:availability:{hotel_id}:{checkin}:{checkout}"

    cached = cache_get(key)
    if cached is not None:
        return cached

    res = check_availability_api(hotel_id, checkin, checkout)
    cache_set(key, res, 300)  # 5 min, availability changes fast
    return res

def get_hotel_details(hotel_id):
    if not hotel_id or hotel_id == "":
        return {"error": "no hotel_id provided"}

    key = f"hotel:details:{hotel_id}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    res = get_hotel_details_api(hotel_id)
    cache_set(key, res, 1800)
    return res
