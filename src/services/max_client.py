"""HTTP-клиент для Max Bot API (platform-api.max.ru).

Max Bot API не имеет стабильного PyPI-пакета, поэтому используем httpx напрямую.
Документация: https://dev.max.ru/docs
"""

import logging
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger("dom_max.max_client")

BASE_URL = "https://botapi.max.ru"


class MaxBotClient:
    """Async HTTP-клиент для Max Bot API."""

    def __init__(self, token: str | None = None):
        self.token = token or settings.bot_token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                params={"access_token": self.token},
                timeout=httpx.Timeout(30.0),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # --- API методы ---

    async def get_me(self) -> dict:
        """Получить информацию о боте."""
        client = await self._get_client()
        r = await client.get("/me")
        r.raise_for_status()
        return r.json()

    async def send_message(
        self, chat_id: int, text: str, *, reply_to: int | None = None,
    ) -> dict:
        """Отправить текстовое сообщение в чат."""
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_to:
            payload["reply_to"] = reply_to

        client = await self._get_client()
        r = await client.post("/messages", json=payload)
        r.raise_for_status()
        return r.json()

    async def send_message_with_keyboard(
        self,
        chat_id: int,
        text: str,
        buttons: list[list[dict]],
    ) -> dict:
        """Отправить сообщение с inline-кнопками."""
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "attachments": [
                {
                    "type": "inline_keyboard",
                    "payload": {"buttons": buttons},
                }
            ],
        }
        client = await self._get_client()
        r = await client.post("/messages", json=payload)
        r.raise_for_status()
        return r.json()

    async def answer_callback(self, callback_id: str, *, notification: str = "") -> dict:
        """Ответить на callback-запрос (нажатие inline-кнопки)."""
        payload: dict[str, Any] = {"callback_id": callback_id}
        if notification:
            payload["notification"] = notification

        client = await self._get_client()
        r = await client.post("/answers", json=payload)
        r.raise_for_status()
        return r.json()

    async def get_file_url(self, file_id: str) -> str:
        """Получить URL файла (фото) по file_id."""
        client = await self._get_client()
        r = await client.get("/uploads", params={"url": file_id})
        r.raise_for_status()
        data = r.json()
        return data.get("url", "")

    async def set_webhook(self, url: str) -> dict:
        """Установить webhook URL."""
        client = await self._get_client()
        r = await client.post("/subscriptions", json={"url": url})
        r.raise_for_status()
        return r.json()

    async def delete_webhook(self) -> dict:
        """Удалить webhook."""
        client = await self._get_client()
        r = await client.delete("/subscriptions")
        r.raise_for_status()
        return r.json()


# Синглтон для использования во всём проекте
max_client = MaxBotClient()
