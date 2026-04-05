"""Rate limiter на Redis — атомарный через Lua-скрипт.

Защита от спама и DDoS на уровне пользователя.
"""

import logging

import redis.asyncio as aioredis

logger = logging.getLogger("dom_max.rate_limiter")

# Lua-скрипт: атомарный incr + expire (без race condition)
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
    """Проверить rate limit пользователя (атомарная операция).

    Args:
        user_id: ID пользователя в Max
        limit: максимум запросов за окно
        window: размер окна в секундах

    Returns:
        True — разрешено, False — превышен лимит.
    """
    key = f"rl:{user_id}"

    try:
        count = await redis.eval(_RATE_LIMIT_SCRIPT, 1, key, str(window))
    except aioredis.RedisError:
        logger.exception("Redis error in rate limiter, allowing request")
        return True  # Fail-open: при ошибке Redis — пропускаем

    if count > limit:
        logger.warning("Rate limit exceeded: user_id=%d count=%d", user_id, count)
        return False

    return True
