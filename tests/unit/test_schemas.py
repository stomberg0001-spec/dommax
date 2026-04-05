"""Unit-тесты L0 (Pydantic models) — проверяют валидацию данных.

Каждый тест верифицирует L1 против L0 (schemas.py).
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

NOW = datetime.now(timezone.utc)


# --- UKProfile ---

class TestUKProfile:
    def test_valid(self):
        uk = UKProfile(
            id=1, name="УК Рога и Копыта",
            inn="1234567890", contact_phone="+79001234567",
            contact_email="uk@example.com",
            created_at=NOW, updated_at=NOW,
        )
        assert uk.name == "УК Рога и Копыта"
        assert uk.inn == "1234567890"

    def test_invalid_inn_letters(self):
        with pytest.raises(ValidationError, match="inn"):
            UKProfile(
                id=1, name="Test", inn="12345ABCDE",
                contact_phone="+79001234567", contact_email="a@b.com",
                created_at=NOW, updated_at=NOW,
            )

    def test_invalid_inn_short(self):
        with pytest.raises(ValidationError, match="inn"):
            UKProfile(
                id=1, name="Test", inn="123",
                contact_phone="+79001234567", contact_email="a@b.com",
                created_at=NOW, updated_at=NOW,
            )

    def test_invalid_phone(self):
        with pytest.raises(ValidationError, match="contact_phone"):
            UKProfile(
                id=1, name="Test", inn="1234567890",
                contact_phone="8-900-123-45-67",  # Не +7...
                contact_email="a@b.com",
                created_at=NOW, updated_at=NOW,
            )

    def test_invalid_email(self):
        with pytest.raises(ValidationError, match="contact_email"):
            UKProfile(
                id=1, name="Test", inn="1234567890",
                contact_phone="+79001234567", contact_email="not-an-email",
                created_at=NOW, updated_at=NOW,
            )

    def test_12_digit_inn(self):
        """ИП имеют 12-значный ИНН."""
        uk = UKProfile(
            id=1, name="ИП Иванов", inn="123456789012",
            contact_phone="+79001234567", contact_email="ip@b.com",
            created_at=NOW, updated_at=NOW,
        )
        assert len(uk.inn) == 12


# --- House ---

class TestHouse:
    def test_valid(self):
        h = House(
            id=1, uk_id=1, address="ул. Ленина, 1",
            chat_id=100500, apartments_count=120,
            created_at=NOW, updated_at=NOW,
        )
        assert h.apartments_count == 120

    def test_negative_apartments(self):
        with pytest.raises(ValidationError, match="apartments_count"):
            House(
                id=1, uk_id=1, address="ул. Ленина, 1",
                chat_id=100500, apartments_count=-1,
                created_at=NOW, updated_at=NOW,
            )

    def test_default_apartments(self):
        h = House(
            id=1, uk_id=1, address="ул. Ленина, 1",
            chat_id=100500, created_at=NOW, updated_at=NOW,
        )
        assert h.apartments_count == 0


# --- User ---

class TestUser:
    def test_valid_resident(self):
        u = User(
            id=1, max_user_id=999, display_name="Иванов И.И.",
            house_id=1, created_at=NOW, updated_at=NOW,
        )
        assert u.is_uk_staff is False

    def test_valid_staff(self):
        u = User(
            id=2, max_user_id=1000, display_name="Диспетчер",
            is_uk_staff=True, created_at=NOW, updated_at=NOW,
        )
        assert u.house_id is None
        assert u.is_uk_staff is True


# --- TicketCreate ---

class TestTicketCreate:
    def test_valid(self):
        t = TicketCreate(description="Течёт кран на кухне")
        assert t.photo_file_id is None

    def test_too_short(self):
        with pytest.raises(ValidationError, match="description"):
            TicketCreate(description="ab")

    def test_too_long(self):
        with pytest.raises(ValidationError, match="description"):
            TicketCreate(description="x" * 2001)

    def test_with_photo(self):
        t = TicketCreate(description="Разбито окно", photo_file_id="abc123")
        assert t.photo_file_id == "abc123"


# --- Ticket ---

class TestTicket:
    def test_default_status(self):
        t = Ticket(
            id=1, house_id=1, user_id=1, description="Течёт кран",
            created_at=NOW, updated_at=NOW,
        )
        assert t.status == TicketStatus.NEW

    def test_all_statuses_valid(self):
        for status in TicketStatus:
            t = Ticket(
                id=1, house_id=1, user_id=1, description="test",
                status=status, created_at=NOW, updated_at=NOW,
            )
            assert t.status == status


# --- NotificationCreate ---

class TestNotificationCreate:
    def test_valid(self):
        n = NotificationCreate(
            house_ids=[1, 2],
            type=NotificationType.EMERGENCY,
            title="Авария на трубопроводе",
            body="Отключение горячей воды до 18:00",
        )
        assert len(n.house_ids) == 2

    def test_empty_house_ids(self):
        with pytest.raises(ValidationError, match="house_ids"):
            NotificationCreate(
                house_ids=[],
                type=NotificationType.INFO,
                title="Тест", body="Тест",
            )

    def test_title_too_short(self):
        with pytest.raises(ValidationError, match="title"):
            NotificationCreate(
                house_ids=[1],
                type=NotificationType.INFO,
                title="ab", body="body",
            )

    def test_body_too_long(self):
        with pytest.raises(ValidationError, match="body"):
            NotificationCreate(
                house_ids=[1],
                type=NotificationType.INFO,
                title="Тест", body="x" * 4001,
            )


# --- Notification ---

class TestNotification:
    def test_unsent(self):
        n = Notification(
            id=1, uk_id=1, type=NotificationType.PLANNED_WORKS,
            title="Замена труб", body="С 10:00 до 16:00",
            house_ids=[1, 2], created_at=NOW, updated_at=NOW,
        )
        assert n.sent_at is None

    def test_all_types_valid(self):
        for ntype in NotificationType:
            n = Notification(
                id=1, uk_id=1, type=ntype,
                title="Тест", body="Тело",
                house_ids=[1], created_at=NOW, updated_at=NOW,
            )
            assert n.type == ntype


# --- FAQItem ---

class TestFAQItem:
    def test_valid(self):
        f = FAQItem(
            id=1, uk_id=1,
            question="Как подать показания?",
            answer="Через личный кабинет на сайте.",
            created_at=NOW, updated_at=NOW,
        )
        assert f.is_active is True
        assert f.category == ""


# --- FAQMatch ---

class TestFAQMatch:
    def test_valid_score(self):
        item = FAQItem(
            id=1, uk_id=1, question="Q", answer="A",
            created_at=NOW, updated_at=NOW,
        )
        m = FAQMatch(item=item, score=85.5)
        assert m.score == 85.5

    def test_score_out_of_range(self):
        item = FAQItem(
            id=1, uk_id=1, question="Q", answer="A",
            created_at=NOW, updated_at=NOW,
        )
        with pytest.raises(ValidationError, match="score"):
            FAQMatch(item=item, score=101)

        with pytest.raises(ValidationError, match="score"):
            FAQMatch(item=item, score=-1)


# --- MessageLog ---

class TestMessageLog:
    def test_valid(self):
        ml = MessageLog(
            id=1, chat_id=100, user_id=1,
            text="Привет", message_type=MessageType.TEXT,
            created_at=NOW,
        )
        assert ml.message_type == MessageType.TEXT

    def test_all_message_types(self):
        for mt in MessageType:
            ml = MessageLog(
                id=1, chat_id=100, user_id=1,
                message_type=mt, created_at=NOW,
            )
            assert ml.message_type == mt

    def test_invalid_message_type(self):
        with pytest.raises(ValidationError, match="message_type"):
            MessageLog(
                id=1, chat_id=100, user_id=1,
                message_type="invalid_type", created_at=NOW,
            )
