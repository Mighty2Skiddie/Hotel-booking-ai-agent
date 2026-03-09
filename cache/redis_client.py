import json
import os
import redis
from dotenv import load_dotenv

load_dotenv()

_client = None
_available = None

# redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, db=0)


def get_redis_client():
    global _client, _available

    if _available is False:
        return None
    if _client is not None:
        return _client

    try:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _client = redis.from_url(url, decode_responses=True)
        _client.ping()
        _available = True
        print("redis connected")
        return _client
    except Exception:
        print("redis not available, running without cache")
        _available = False
        _client = None
        return None


def cache_get(key):
    try:
        c = get_redis_client()
        if c is None:
            return None

        val = c.get(key)
        # got bitten by empty string from redis once, so checking both
        if val is not None and val != "" and val != b"":
            print(f"  cache hit: {key}")
            return json.loads(val)
        else:
            print(f"  cache miss: {key}")
            return None
    except Exception:
        return None


def cache_set(key, value, ttl):
    try:
        c = get_redis_client()
        if c is None:
            return
        c.setex(key, ttl, json.dumps(value))
    except Exception as e:
        # don't want cache errors to break anything
        print(f"cache set failed for {key}: {e}")
