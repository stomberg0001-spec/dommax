"""Notification worker — рассылка уведомлений жителям с retry."""

import asyncio
import logging

import asyncpg
import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

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


_send_with_retry = retry(
    retry=retry_if_exception_type(httpx.HTTPError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


@_send_with_retry
async def _send_one(chat_id: int, text: str) -> None:
    await max_client.send_message(chat_id, text)


async def send_notification(
    pool: asyncpg.Pool,
    *,
    notification_id: int,
    type_: str,
    title: str,
    body: str,
    house_ids: list[int],
) -> dict:
    emoji = TYPE_EMOJI.get(type_, "📢")
    label = TYPE_LABEL.get(type_, "Уведомление")
    text = f"{emoji} *{label}*\n\n*{title}*\n\n{body}"

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, chat_id FROM houses WHERE id = ANY($1)", house_ids,
        )

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
            await _send_one(row["chat_id"], text)
            sent_count += 1
        except Exception:
            logger.exception(
                "Failed to send notification #%d to house_id=%d chat_id=%d after retries",
                notification_id, row["id"], row["chat_id"],
            )
            failed_houses.append(row["id"])

        if settings.notify_rps > 0:
            await asyncio.sleep(1.0 / settings.notify_rps)

    if not failed_houses:
        await mark_notification_sent(pool, notification_id=notification_id)
    else:
        logger.error(
            "Notification #%d: PARTIAL SEND — %d/%d sent, failed houses: %s",
            notification_id, sent_count, len(rows), failed_houses,
        )

    result = {"sent": sent_count, "failed": failed_houses, "missing": missing_ids}
    logger.info("Notification #%d result: %s", notification_id, result)
    return result
