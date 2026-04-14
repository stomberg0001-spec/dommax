"""Состояния пользователей хранятся в Redis с TTL (не in-memory)."""

from unittest.mock import AsyncMock

import pytest

from src.bot.webhook import (
    USER_STATE_TTL,
    _clear_user_state,
    _get_user_state,
    _set_user_state,
)


@pytest.mark.asyncio
async def test_set_user_state_uses_ttl():
    redis = AsyncMock()
    await _set_user_state(redis, 42, "awaiting_ticket")
    redis.set.assert_awaited_once_with("state:42", "awaiting_ticket", ex=USER_STATE_TTL)


@pytest.mark.asyncio
async def test_get_user_state_returns_value():
    redis = AsyncMock()
    redis.get.return_value = "awaiting_ticket"
    result = await _get_user_state(redis, 42)
    assert result == "awaiting_ticket"
    redis.get.assert_awaited_once_with("state:42")


@pytest.mark.asyncio
async def test_clear_user_state_deletes_key():
    redis = AsyncMock()
    await _clear_user_state(redis, 42)
    redis.delete.assert_awaited_once_with("state:42")
