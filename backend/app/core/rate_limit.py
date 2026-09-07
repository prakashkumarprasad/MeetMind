# Redis-backed rate limiting helper used by auth, chat, and upload routes.

import time

import redis

from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

def is_rate_limited(key, max_attempts=5, window_seconds=900):
    """
    Returns True if this key (e.g. 'login:<ip>' or 'login:<email>')
    has hit max_attempts within the last window_seconds (default 15 min).
    """
    now = time.time()
    redis_key = f"ratelimit:{key}"

    redis_client.zremrangebyscore(redis_key, 0, now - window_seconds)
    attempt_count = redis_client.zcard(redis_key)

    if attempt_count >= max_attempts:
        return True

    redis_client.zadd(redis_key, {str(now): now})
    redis_client.expire(redis_key, window_seconds)
    return False

def get_rate_limit_info(key, max_attempts=5, window_seconds=900):
    """
    Returns (is_limited, retry_after_seconds, current_count)
    """
    now = time.time()
    redis_key = f"ratelimit:{key}"

    redis_client.zremrangebyscore(redis_key, 0, now - window_seconds)
    attempt_count = redis_client.zcard(redis_key)

    if attempt_count >= max_attempts:

        oldest = redis_client.zrange(redis_key, 0, 0, withscores=True)
        if oldest:
            oldest_time = oldest[0][1]
            retry_after = int(oldest_time + window_seconds - now) + 1
            return True, retry_after, attempt_count
        return True, window_seconds, attempt_count

    return False, 0, attempt_count

def increment_rate_limit(key, max_attempts=5, window_seconds=900):
    """
    Increments the rate limit counter and returns (is_limited, retry_after_seconds)
    """
    now = time.time()
    redis_key = f"ratelimit:{key}"

    redis_client.zremrangebyscore(redis_key, 0, now - window_seconds)
    attempt_count = redis_client.zcard(redis_key)

    if attempt_count >= max_attempts:

        oldest = redis_client.zrange(redis_key, 0, 0, withscores=True)
        if oldest:
            oldest_time = oldest[0][1]
            retry_after = int(oldest_time + window_seconds - now) + 1
            return True, retry_after
        return True, window_seconds

    redis_client.zadd(redis_key, {str(now): now})
    redis_client.expire(redis_key, window_seconds)
    return False, 0
