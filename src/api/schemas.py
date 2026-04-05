"""
L0 — Источник истины. Pydantic models для всего проекта.

Изменение модели = обновление тестов + миграция БД.
Все слои (L1-L4) верифицируются относительно этих моделей.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field


# --- Enums ---

class TicketStatus(StrEnum):
    NEW = "new"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    REJECTED = "rejected"


class NotificationType(StrEnum):
    EMERGENCY = "emergency"        # Авария
    PLANNED_WORKS = "planned_works" # Плановые работы
    MEETING = "meeting"            # Собрание
    INFO = "info"                  # Информация


class MessageType(StrEnum):
    TEXT = "text"
    PHOTO = "photo"
    COMMAND = "command"
    CALLBACK = "callback"
    STICKER = "sticker"
    OTHER = "other"


# --- УК и дома ---

class UKProfile(BaseModel):
    """Управляющая компания."""
    id: int
    name: str
    inn: str = Field(pattern=r"^\d{10,12}$")
    contact_phone: str = Field(pattern=r"^\+7\d{10}$")
    contact_email: EmailStr
    created_at: datetime
    updated_at: datetime


class House(BaseModel):
    """Многоквартирный дом, привязанный к УК."""
    id: int
    uk_id: int
    address: str
    chat_id: int  # ID группового чата в Max
    apartments_count: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime


# --- Пользователи ---

class User(BaseModel):
    """Житель или сотрудник УК."""
    id: int
    max_user_id: int  # ID пользователя в Max
    house_id: int | None = None
    display_name: str
    is_uk_staff: bool = False
    created_at: datetime
    updated_at: datetime


# --- FAQ ---

class FAQItem(BaseModel):
    """Элемент базы знаний УК."""
    id: int
    uk_id: int
    question: str
    answer: str
    category: str = ""
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class FAQMatch(BaseModel):
    """Результат нечёткого поиска FAQ."""
    item: FAQItem
    score: float = Field(ge=0, le=100)


# --- Заявки ---

class TicketCreate(BaseModel):
    """Создание заявки жителем."""
    description: str = Field(min_length=5, max_length=2000)
    photo_file_id: str | None = None


class Ticket(BaseModel):
    """Заявка на обслуживание."""
    id: int
    house_id: int
    user_id: int
    description: str
    photo_file_id: str | None = None
    status: TicketStatus = TicketStatus.NEW
    assigned_to: int | None = None  # user_id сотрудника УК
    created_at: datetime
    updated_at: datetime


# --- Уведомления ---

class NotificationCreate(BaseModel):
    """Создание уведомления сотрудником УК."""
    house_ids: list[int] = Field(min_length=1)
    type: NotificationType
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(max_length=4000)


class Notification(BaseModel):
    """Уведомление для жителей."""
    id: int
    uk_id: int
    type: NotificationType
    title: str
    body: str
    house_ids: list[int]
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# --- Лог сообщений ---

class MessageLog(BaseModel):
    """Лог входящих сообщений для аналитики."""
    id: int
    chat_id: int
    user_id: int
    text: str | None = None
    message_type: MessageType
    created_at: datetime
