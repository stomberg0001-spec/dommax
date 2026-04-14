"""Rate limiter на Redis — атомарный через Lua-скрипт."""

import logging

import redis.asyncio as aioredis

from src.config import settings

logger = logging.getLogger("dom_max.rate_limiter")

_RATE_LIMIT_SCRIPT = """
local current = redis.call('incr', KEYS[1])
if current == 1 then
    redis.call('expire', KEYS[1], ARGV[1])
end
return current
"""


async def check_rate_limit(
    redis: aioredis.Redis,
    *,
    user_id: int,
    limit: int = 10,
    window: int = 60,
) -> bool:
    """Проверить rate limit. По умолчанию fail-closed (Redis недоступен → отказ)."""
    key = f"rl:{user_id}"

    try:
        count = await redis.eval(_RATE_LIMIT_SCRIPT, 1, key, str(window))
    except aioredis.RedisError:
        logger.error(
            "Redis error in rate limiter — fail_open=%s",
            settings.rate_limiter_fail_open,
        )
        return settings.rate_limiter_fail_open

    if count > limit:
        logger.warning("Rate limit exceeded: user_id=%d count=%d", user_id, count)
        return False

    return True
