import json
from typing import Any, Optional

import redis

from app.config import get_settings

_redis: Optional[redis.Redis] = None


def get_redis() -> Optional[redis.Redis]:
    global _redis
    settings = get_settings()
    if not settings.redis_url:
        return None
    if _redis is None:
        try:
            _redis = redis.from_url(settings.redis_url, decode_responses=True)
            _redis.ping()
        except Exception:
            _redis = None
    return _redis


def cache_get(key: str) -> Optional[Any]:
    r = get_redis()
    if not r:
        return None
    try:
        val = r.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl: int = 3600) -> None:
    r = get_redis()
    if not r:
        return
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def cache_delete(key: str) -> None:
    r = get_redis()
    if r:
        try:
            r.delete(key)
        except Exception:
            pass


def rate_limit_check(key: str, limit: int = 60, window: int = 60) -> bool:
    """Returns True if request is allowed."""
    r = get_redis()
    if not r:
        return True
    try:
        current = r.incr(key)
        if current == 1:
            r.expire(key, window)
        return current <= limit
    except Exception:
        return True
