"""Обработчик входящих событий от Max Bot API.

Основная точка маршрутизации: текст → FAQ / команда → обработчик / callback → action.
"""

import logging
import unicodedata

import asyncpg
import redis.asyncio as aioredis

from src.bot.faq_engine import format_faq_response, match_faq
from src.db.queries import (
    create_ticket,
    get_or_create_user,
    get_uk_by_chat_id,
    log_message,
)
from src.services.max_client import max_client
from src.services.rate_limiter import check_rate_limit

logger = logging.getLogger("dom_max.webhook")

# Максимальная длина текста, которую обрабатываем
MAX_TEXT_LENGTH = 5000

# Состояния пользователей (ожидание ввода описания заявки)
# В проде — Redis, для MVP — in-memory
_user_states: dict[int, str] = {}


async def handle_update(
    payload: dict,
    db_pool: asyncpg.Pool,
    redis: aioredis.Redis,
) -> str:
    """Главный диспетчер входящих событий."""
    if not isinstance(payload, dict):
        logger.warning("Invalid payload type: %s", type(payload))
        return "invalid_payload"

    update_type = payload.get("update_type")

    if update_type == "message_created":
        return await _handle_message(payload, db_pool, redis)
    elif update_type == "message_callback":
        return await _handle_callback(payload, db_pool, redis)
    else:
        logger.debug("Unknown update_type: %s", update_type)
        return "ignored"


def _safe_get(data: dict | None, *keys, default=None):
    """Безопасное извлечение вложенных ключей из dict."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


async def _handle_message(
    payload: dict,
    db_pool: asyncpg.Pool,
    redis: aioredis.Redis,
) -> str:
    """Обработка входящего сообщения."""
    message = payload.get("message")
    if not isinstance(message, dict):
        return "invalid_message"

    chat_id = _safe_get(message, "recipient", "chat_id")
    sender = message.get("sender")
    if not isinstance(sender, dict):
        # MAX-001: системные сообщения без sender
        return "no_sender"

    max_user_id = sender.get("user_id")
    if not chat_id or not max_user_id:
        return "missing_ids"

    # Извлечь и нормализовать текст
    raw_text = _safe_get(message, "body", "text", default="")
    if not isinstance(raw_text, str):
        raw_text = ""
    text = unicodedata.normalize("NFC", raw_text[:MAX_TEXT_LENGTH].strip())

    # Rate limit
    allowed = await check_rate_limit(redis, user_id=max_user_id, limit=10, window=60)
    if not allowed:
        return "rate_limited"

    # Зарегистрировать пользователя
    display_name = sender.get("name", "Житель")
    if not isinstance(display_name, str):
        display_name = "Житель"

    user = await get_or_create_user(
        db_pool,
        max_user_id=max_user_id,
        display_name=display_name[:200],
        chat_id=chat_id,
    )

    # Определить тип сообщения
    has_photo = bool(_safe_get(message, "body", "attachments"))
    msg_type = "photo" if has_photo else "text"
    if text.startswith("/"):
        msg_type = "command"

    # Логировать
    await log_message(
        db_pool,
        chat_id=chat_id,
        user_id=user["id"],
        text=text[:500] if text else None,
        message_type=msg_type,
    )

    # Проверить состояние пользователя (ожидает ввода заявки?)
    state = _user_states.get(max_user_id)
    if state == "awaiting_ticket":
        return await _create_ticket_from_message(
            db_pool, user=user, chat_id=chat_id, text=text,
            photo_file_id=_extract_photo(message),
        )

    # Команды
    if text.startswith("/"):
        return await _handle_command(text, chat_id, max_user_id, user, db_pool)

    # FAQ matching (только если текст достаточно длинный)
    if len(text) >= 3:
        uk = await get_uk_by_chat_id(db_pool, chat_id=chat_id)
        if uk:
            faq_result = await match_faq(db_pool, uk_id=uk["id"], user_text=text)
            if faq_result:
                response = format_faq_response(faq_result)
                await max_client.send_message(chat_id, response)
                return "faq_answered"

    return "no_match"


async def _handle_command(
    text: str,
    chat_id: int,
    max_user_id: int,
    user: dict,
    db_pool: asyncpg.Pool,
) -> str:
    """Обработка команд бота."""
    cmd = text.split()[0].lower()

    if cmd in ("/start", "/help"):
        await max_client.send_message(
            chat_id,
            "Привет! Я бот-диспетчер вашей УК.\n\n"
            "Задайте вопрос текстом — я поищу ответ в базе знаний.\n\n"
            "Команды:\n"
            "/ticket — создать заявку\n"
            "/status — проверить статус заявки\n"
            "/help — эта справка",
        )
        return "help_sent"

    elif cmd == "/ticket":
        _user_states[max_user_id] = "awaiting_ticket"
        await max_client.send_message(
            chat_id,
            "Опишите проблему (можно приложить фото). "
            "Я создам заявку и передам в УК.",
        )
        return "ticket_prompt"

    elif cmd == "/status":
        from src.db.queries import get_tickets_by_house
        if not user.get("house_id"):
            await max_client.send_message(chat_id, "Дом не определён.")
            return "no_house"

        tickets = await get_tickets_by_house(db_pool, house_id=user["house_id"])
        if not tickets:
            await max_client.send_message(chat_id, "Активных заявок нет.")
            return "no_tickets"

        lines = []
        for t in tickets[:5]:
            status_emoji = {
                "new": "🆕", "accepted": "✅", "in_progress": "🔧",
                "done": "✅", "rejected": "❌",
            }.get(t["status"], "❓")
            desc = t["description"][:60]
            lines.append(f"{status_emoji} #{t['id']}: {desc}... — {t['status']}")

        await max_client.send_message(chat_id, "Ваши заявки:\n\n" + "\n".join(lines))
        return "status_sent"

    return "unknown_command"


async def _create_ticket_from_message(
    db_pool: asyncpg.Pool,
    *,
    user: dict,
    chat_id: int,
    text: str,
    photo_file_id: str | None,
) -> str:
    """Создать заявку из сообщения пользователя."""
    _user_states.pop(user["max_user_id"], None)

    if not user.get("house_id"):
        await max_client.send_message(chat_id, "Ошибка: дом не определён.")
        return "ticket_no_house"

    if len(text) < 5:
        await max_client.send_message(
            chat_id, "Описание слишком короткое (минимум 5 символов). Попробуйте ещё раз: /ticket",
        )
        return "ticket_too_short"

    ticket = await create_ticket(
        db_pool,
        house_id=user["house_id"],
        user_id=user["id"],
        description=text[:2000],
        photo_file_id=photo_file_id,
    )

    await max_client.send_message(
        chat_id,
        f"Заявка #{ticket['id']} создана!\n"
        f"Описание: {text[:100]}...\n"
        f"Статус: 🆕 Новая\n\n"
        f"Проверить статус: /status",
    )
    return "ticket_created"


def _extract_photo(message: dict) -> str | None:
    """Извлечь file_id фото из сообщения Max (с type-checking)."""
    attachments = _safe_get(message, "body", "attachments", default=[])
    if not isinstance(attachments, list):
        return None
    for att in attachments:
        if not isinstance(att, dict):
            continue
        if att.get("type") == "image":
            token = _safe_get(att, "payload", "token")
            if token:
                return str(token)
    return None


async def _handle_callback(
    payload: dict,
    db_pool: asyncpg.Pool,
    redis: aioredis.Redis,
) -> str:
    """Обработка callback-нажатий (inline-кнопки)."""
    callback = payload.get("callback")
    if not isinstance(callback, dict):
        return "invalid_callback"

    callback_id = callback.get("callback_id")
    if not callback_id:
        return "missing_callback_id"

    # MAX-002: callback_id может быть числом — приводим к строке
    await max_client.answer_callback(str(callback_id), notification="Обработано")
    logger.info("Callback: %s", callback.get("payload", ""))
    return "callback_handled"
