"""Стресс-тесты — граничные значения, edge cases, DoS-векторы.

Проверяем, что система не падает на экстремальных входных данных.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.api.schemas import (
    FAQItem,
    FAQMatch,
    House,
    MessageLog,
    MessageType,
    Notification,
    NotificationCreate,
    NotificationType,
    Ticket,
    TicketCreate,
    TicketStatus,
    UKProfile,
    User,
)
from src.bot.webhook import _extract_photo, _safe_get

NOW = datetime.now(timezone.utc)


# --- Экстремальные строки ---

STRESS_STRINGS = [
    "",                           # Пустая строка
    " " * 10000,                  # Только пробелы
    "a" * 100000,                 # 100KB текст
    "🔥" * 5000,                  # Только эмодзи (multi-byte)
    "\x00" * 100,                 # Null bytes
    "\n\r\t" * 1000,              # Control characters
    "<script>alert('xss')</script>",  # XSS attempt
    "'; DROP TABLE users; --",    # SQL injection attempt
    "Ñ" * 5000,                   # Кириллица
    "\u200b" * 1000,              # Zero-width spaces
    "café" * 500,                 # Mixed ASCII + Unicode
]


class TestSchemasStress:
    """L0 модели не падают на экстремальных данных."""

    def test_ticket_create_boundary_5_chars(self):
        """Ровно 5 символов — минимум."""
        t = TicketCreate(description="12345")
        assert len(t.description) == 5

    def test_ticket_create_boundary_2000_chars(self):
        """Ровно 2000 символов — максимум."""
        t = TicketCreate(description="x" * 2000)
        assert len(t.description) == 2000

    def test_ticket_create_2001_rejects(self):
        with pytest.raises(ValidationError):
            TicketCreate(description="x" * 2001)

    def test_notification_title_boundary_3(self):
        n = NotificationCreate(
            house_ids=[1], type=NotificationType.INFO,
            title="abc", body="body",
        )
        assert len(n.title) == 3

    def test_notification_title_boundary_200(self):
        n = NotificationCreate(
            house_ids=[1], type=NotificationType.INFO,
            title="x" * 200, body="body",
        )
        assert len(n.title) == 200

    def test_notification_title_201_rejects(self):
        with pytest.raises(ValidationError):
            NotificationCreate(
                house_ids=[1], type=NotificationType.INFO,
                title="x" * 201, body="body",
            )

    def test_notification_body_boundary_4000(self):
        n = NotificationCreate(
            house_ids=[1], type=NotificationType.INFO,
            title="test", body="x" * 4000,
        )
        assert len(n.body) == 4000

    def test_notification_body_4001_rejects(self):
        with pytest.raises(ValidationError):
            NotificationCreate(
                house_ids=[1], type=NotificationType.INFO,
                title="test", body="x" * 4001,
            )

    def test_faq_score_boundary_0(self):
        item = FAQItem(id=1, uk_id=1, question="Q", answer="A", created_at=NOW, updated_at=NOW)
        m = FAQMatch(item=item, score=0)
        assert m.score == 0

    def test_faq_score_boundary_100(self):
        item = FAQItem(id=1, uk_id=1, question="Q", answer="A", created_at=NOW, updated_at=NOW)
        m = FAQMatch(item=item, score=100)
        assert m.score == 100

    def test_house_max_apartments(self):
        """Большое количество квартир (высотка)."""
        h = House(
            id=1, uk_id=1, address="addr", chat_id=1,
            apartments_count=10000, created_at=NOW, updated_at=NOW,
        )
        assert h.apartments_count == 10000

    def test_notification_many_houses(self):
        """Рассылка на 1000 домов."""
        n = NotificationCreate(
            house_ids=list(range(1, 1001)),
            type=NotificationType.EMERGENCY,
            title="Авария", body="Срочно",
        )
        assert len(n.house_ids) == 1000

    def test_inn_10_digits(self):
        """ИНН юрлица — 10 знаков."""
        uk = UKProfile(
            id=1, name="УК", inn="1234567890",
            contact_phone="+79001234567", contact_email="a@b.com",
            created_at=NOW, updated_at=NOW,
        )
        assert len(uk.inn) == 10

    def test_inn_12_digits(self):
        """ИНН ИП — 12 знаков."""
        uk = UKProfile(
            id=1, name="ИП", inn="123456789012",
            contact_phone="+79001234567", contact_email="a@b.com",
            created_at=NOW, updated_at=NOW,
        )
        assert len(uk.inn) == 12

    def test_inn_9_digits_rejects(self):
        with pytest.raises(ValidationError):
            UKProfile(
                id=1, name="УК", inn="123456789",
                contact_phone="+79001234567", contact_email="a@b.com",
                created_at=NOW, updated_at=NOW,
            )

    def test_inn_13_digits_rejects(self):
        with pytest.raises(ValidationError):
            UKProfile(
                id=1, name="УК", inn="1234567890123",
                contact_phone="+79001234567", contact_email="a@b.com",
                created_at=NOW, updated_at=NOW,
            )


class TestWebhookStress:
    """Webhook не падает на мусорных данных."""

    def test_extract_photo_empty_body(self):
        assert _extract_photo({}) is None

    def test_extract_photo_none_body(self):
        assert _extract_photo({"body": None}) is None

    def test_extract_photo_numeric_body(self):
        assert _extract_photo({"body": 42}) is None

    def test_safe_get_deeply_nested(self):
        data = {"a": {"b": {"c": {"d": {"e": 42}}}}}
        assert _safe_get(data, "a", "b", "c", "d", "e") == 42

    def test_safe_get_wrong_type_at_root(self):
        assert _safe_get("not a dict", "key", default="safe") == "safe"

    def test_safe_get_list_instead_of_dict(self):
        assert _safe_get({"a": [1, 2, 3]}, "a", "b", default="safe") == "safe"

    @pytest.mark.parametrize("stress_input", STRESS_STRINGS)
    def test_extract_photo_stress_text_in_body(self, stress_input):
        """Экстремальные строки в body.text не крашат extract_photo."""
        msg = {"body": {"text": stress_input, "attachments": []}}
        result = _extract_photo(msg)
        assert result is None


class TestEnumCompleteness:
    """Проверяем, что enum-значения в schemas.py совпадают с SQL."""

    def test_ticket_status_values(self):
        expected = {"new", "accepted", "in_progress", "done", "rejected"}
        actual = {s.value for s in TicketStatus}
        assert actual == expected

    def test_notification_type_values(self):
        expected = {"emergency", "planned_works", "meeting", "info"}
        actual = {t.value for t in NotificationType}
        assert actual == expected

    def test_message_type_values(self):
        expected = {"text", "photo", "command", "callback", "sticker", "other"}
        actual = {t.value for t in MessageType}
        assert actual == expected
