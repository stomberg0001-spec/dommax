"""Notification worker — рассылка уведомлений жителям.

Типы уведомлений (Приказ 856/пр):
- emergency: аварии (немедленно)
- planned_works: плановые работы
- meeting: собрания
- info: информация
"""

import asyncio
import logging

import asyncpg

from src.config import settings
from src.db.queries import mark_notification_sent
from src.services.max_client import max_client

logger = logging.getLogger("dom_max.notifications")

TYPE_EMOJI = {
    "emergency": "🚨",
    "planned_works": "🔧",
    "meeting": "📋",
    "info": "ℹ️",
}

TYPE_LABEL = {
    "emergency": "АВАРИЯ",
    "planned_works": "Плановые работы",
    "meeting": "Собрание",
    "info": "Информация",
}


async def send_notification(
    pool: asyncpg.Pool,
    *,
    notification_id: int,
    type_: str,
    title: str,
    body: str,
    house_ids: list[int],
) -> dict:
    """Разослать уведомление во все чаты домов.

    Returns:
        dict: {"sent": int, "failed": list[int], "missing": list[int]}
    """
    emoji = TYPE_EMOJI.get(type_, "📢")
    label = TYPE_LABEL.get(type_, "Уведомление")
    text = f"{emoji} *{label}*\n\n*{title}*\n\n{body}"

    # Получить chat_id для запрошенных домов
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, chat_id FROM houses WHERE id = ANY($1)", house_ids,
        )

    # Проверить: все ли дома найдены?
    found_ids = {row["id"] for row in rows}
    missing_ids = [hid for hid in house_ids if hid not in found_ids]
    if missing_ids:
        logger.warning(
            "Notification #%d: houses not found: %s", notification_id, missing_ids,
        )

    sent_count = 0
    failed_houses: list[int] = []

    for row in rows:
        try:
            await max_client.send_message(row["chat_id"], text)
            sent_count += 1
        except Exception:
            logger.exception(
                "Failed to send notification #%d to house_id=%d chat_id=%d",
                notification_id, row["id"], row["chat_id"],
            )
            failed_houses.append(row["id"])

        # Rate limiting: не более notify_rps сообщений в секунду
        if settings.notify_rps > 0:
            await asyncio.sleep(1.0 / settings.notify_rps)

    # Помечаем отправленным ТОЛЬКО если все доставлены
    if not failed_houses:
        await mark_notification_sent(pool, notification_id=notification_id)
    else:
        logger.error(
            "Notification #%d: PARTIAL SEND — %d/%d sent, failed houses: %s",
            notification_id, sent_count, len(rows), failed_houses,
        )

    result = {
        "sent": sent_count,
        "failed": failed_houses,
        "missing": missing_ids,
    }
    logger.info("Notification #%d result: %s", notification_id, result)
    return result
