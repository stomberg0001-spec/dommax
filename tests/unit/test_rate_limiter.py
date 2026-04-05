"""Unit-тесты rate limiter — проверяют логику ограничения без реального Redis.

Используем fakeredis для изоляции.
"""

import pytest
import pytest_asyncio

# Пробуем fakeredis; если нет — пропускаем тесты
fakeredis = pytest.importorskip("fakeredis")

from src.services.rate_limiter import check_rate_limit


@pytest_asyncio.fixture
async def fake_redis():
    """Создать in-memory Redis для тестов."""
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


@pytest.mark.asyncio
async def test_allows_under_limit(fake_redis):
    """Запросы до лимита проходят."""
    for _ in range(5):
        result = await check_rate_limit(fake_redis, user_id=1, limit=5, window=60)
        assert result is True


@pytest.mark.asyncio
async def test_blocks_over_limit(fake_redis):
    """Запрос сверх лимита блокируется."""
    for _ in range(10):
        await check_rate_limit(fake_redis, user_id=2, limit=10, window=60)

    result = await check_rate_limit(fake_redis, user_id=2, limit=10, window=60)
    assert result is False


@pytest.mark.asyncio
async def test_different_users_independent(fake_redis):
    """Лимиты разных пользователей независимы."""
    for _ in range(5):
        await check_rate_limit(fake_redis, user_id=10, limit=5, window=60)

    # user 10 — заблокирован
    assert await check_rate_limit(fake_redis, user_id=10, limit=5, window=60) is False

    # user 20 — ещё может
    assert await check_rate_limit(fake_redis, user_id=20, limit=5, window=60) is True
