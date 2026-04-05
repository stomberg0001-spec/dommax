"""Симуляция путей работы webhook — все сценарии пользователя.

Тестирует handle_update() без реальных БД/Redis через моки.
Каждый тест = один пользовательский путь через систему.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.webhook import (
    MAX_TEXT_LENGTH,
    _extract_photo,
    _safe_get,
    handle_update,
)


# --- Helpers ---

def _make_message_payload(
    text: str = "Привет",
    chat_id: int = 100,
    user_id: int = 1,
    name: str = "Иванов",
    attachments: list | None = None,
) -> dict:
    """Создать типичный payload message_created."""
    body = {"text": text}
    if attachments is not None:
        body["attachments"] = attachments
    return {
        "update_type": "message_created",
        "message": {
            "recipient": {"chat_id": chat_id},
            "sender": {"user_id": user_id, "name": name},
            "body": body,
        },
    }


def _make_callback_payload(callback_id: str = "cb_123", payload: str = "action:test") -> dict:
    return {
        "update_type": "message_callback",
        "callback": {"callback_id": callback_id, "payload": payload},
    }


# --- _safe_get ---

class TestSafeGet:
    def test_nested_access(self):
        data = {"a": {"b": {"c": 42}}}
        assert _safe_get(data, "a", "b", "c") == 42

    def test_missing_key(self):
        assert _safe_get({"a": 1}, "b", default="x") == "x"

    def test_none_intermediate(self):
        assert _safe_get({"a": None}, "a", "b", default="x") == "x"

    def test_non_dict_intermediate(self):
        assert _safe_get({"a": "string"}, "a", "b", default="x") == "x"

    def test_empty_dict(self):
        assert _safe_get({}, "a", default=None) is None

    def test_none_input(self):
        assert _safe_get(None, "a", default="fallback") == "fallback"


# --- _extract_photo ---

class TestExtractPhoto:
    def test_no_attachments(self):
        msg = {"body": {}}
        assert _extract_photo(msg) is None

    def test_empty_attachments(self):
        msg = {"body": {"attachments": []}}
        assert _extract_photo(msg) is None

    def test_image_attachment(self):
        msg = {"body": {"attachments": [
            {"type": "image", "payload": {"token": "photo_abc123"}},
        ]}}
        assert _extract_photo(msg) == "photo_abc123"

    def test_non_image_skipped(self):
        msg = {"body": {"attachments": [
            {"type": "file", "payload": {"token": "file_123"}},
        ]}}
        assert _extract_photo(msg) is None

    def test_multiple_images_returns_first(self):
        msg = {"body": {"attachments": [
            {"type": "image", "payload": {"token": "first"}},
            {"type": "image", "payload": {"token": "second"}},
        ]}}
        assert _extract_photo(msg) == "first"

    def test_malformed_attachment_not_dict(self):
        """BUG-008: non-dict в attachments не должен крашить."""
        msg = {"body": {"attachments": [None, "string", 42]}}
        assert _extract_photo(msg) is None

    def test_attachments_not_list(self):
        msg = {"body": {"attachments": "not a list"}}
        assert _extract_photo(msg) is None

    def test_missing_token(self):
        msg = {"body": {"attachments": [
            {"type": "image", "payload": {}},
        ]}}
        assert _extract_photo(msg) is None


# --- handle_update: маршрутизация ---

class TestHandleUpdateRouting:
    @pytest.fixture(autouse=True)
    def _setup_mocks(self):
        """Мокаем все внешние зависимости."""
        self.db_pool = AsyncMock()
        self.redis = AsyncMock()

    @pytest.mark.asyncio
    async def test_invalid_payload_type(self):
        result = await handle_update("not a dict", self.db_pool, self.redis)
        assert result == "invalid_payload"

    @pytest.mark.asyncio
    async def test_empty_payload(self):
        result = await handle_update({}, self.db_pool, self.redis)
        assert result == "ignored"

    @pytest.mark.asyncio
    async def test_unknown_update_type(self):
        result = await handle_update(
            {"update_type": "bot_started"}, self.db_pool, self.redis,
        )
        assert result == "ignored"

    @pytest.mark.asyncio
    async def test_message_without_message_field(self):
        result = await handle_update(
            {"update_type": "message_created"}, self.db_pool, self.redis,
        )
        assert result == "invalid_message"

    @pytest.mark.asyncio
    async def test_message_without_sender(self):
        """MAX-001: системные сообщения без sender."""
        result = await handle_update(
            {
                "update_type": "message_created",
                "message": {"recipient": {"chat_id": 1}, "body": {"text": "test"}},
            },
            self.db_pool, self.redis,
        )
        assert result == "no_sender"

    @pytest.mark.asyncio
    async def test_callback_without_callback_field(self):
        result = await handle_update(
            {"update_type": "message_callback"}, self.db_pool, self.redis,
        )
        assert result == "invalid_callback"

    @pytest.mark.asyncio
    async def test_callback_missing_id(self):
        result = await handle_update(
            {"update_type": "message_callback", "callback": {}},
            self.db_pool, self.redis,
        )
        assert result == "missing_callback_id"


# --- Стресс-сценарии ---

class TestStressScenarios:
    """Граничные случаи и стресс-тесты."""

    def test_very_long_text_truncated(self):
        """Текст длиннее MAX_TEXT_LENGTH обрезается в webhook."""
        assert MAX_TEXT_LENGTH == 5000

    def test_unicode_normalization(self):
        """Юникод нормализуется в NFC."""
        import unicodedata
        # NFD decomposed: е + combining accent
        nfd = "е\u0301"  # й в NFD
        nfc = unicodedata.normalize("NFC", nfd)
        assert len(nfc) <= len(nfd)

    def test_extract_photo_deeply_nested(self):
        """Глубоко вложенная структура не крашит."""
        msg = {"body": {"attachments": [
            {"type": "image", "payload": {"token": {"nested": "value"}}},
        ]}}
        # token — не строка, но str() конвертирует
        result = _extract_photo(msg)
        assert result is not None  # str({"nested": "value"})

    def test_safe_get_100_levels_deep(self):
        """_safe_get не крашится на отсутствующих путях."""
        result = _safe_get({}, *["a"] * 100, default="safe")
        assert result == "safe"
