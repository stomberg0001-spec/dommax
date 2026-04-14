"""HTTP-клиент для Max Bot API (platform-api.max.ru).

Документация: https://dev.max.ru/docs-api
Базовый URL и схема авторизации актуальны на 2026-04-13.
"""

import logging
from typing import Any

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings

logger = logging.getLogger("dom_max.max_client")

DEFAULT_BASE_URL = "https://platform-api.max.ru"
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=5.0)
MAX_TEXT_LENGTH = 4000  # Лимит Max Bot API


def _is_retryable_status(status: int) -> bool:
    return 500 <= status < 600


_retry = retry(
    retry=retry_if_exception_type(httpx.HTTPError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class MaxBotClient:
    """Async HTTP-клиент для Max Bot API."""

    def __init__(self, token: str | None = None, base_url: str | None = None):
        self.token = token or settings.bot_token
        self.base_url = base_url or settings.max_api_base_url or DEFAULT_BASE_URL
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": self.token},
                timeout=DEFAULT_TIMEOUT,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        client = await self._get_client()

        @_retry
        async def _do() -> httpx.Response:
            r = await client.request(method, path, **kwargs)
            if _is_retryable_status(r.status_code):
                r.raise_for_status()
            return r

        r = await _do()
        if r.status_code >= 400:
            logger.error(
                "Max API %s %s -> %d %s", method, path, r.status_code, r.text[:500],
            )
            r.raise_for_status()
        return r.json()

    async def get_me(self) -> dict:
        return await self._request("GET", "/me")

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_to: int | None = None,
        format: str | None = None,
    ) -> dict:
        body: dict[str, Any] = {"text": text[:MAX_TEXT_LENGTH]}
        if reply_to:
            body["link"] = {"type": "reply", "mid": reply_to}
        if format:
            body["format"] = format
        return await self._request(
            "POST", "/messages", params={"chat_id": chat_id}, json=body,
        )

    async def send_message_with_keyboard(
        self,
        chat_id: int,
        text: str,
        buttons: list[list[dict]],
    ) -> dict:
        body: dict[str, Any] = {
            "text": text[:MAX_TEXT_LENGTH],
            "attachments": [
                {"type": "inline_keyboard", "payload": {"buttons": buttons}},
            ],
        }
        return await self._request(
            "POST", "/messages", params={"chat_id": chat_id}, json=body,
        )

    async def answer_callback(
        self, callback_id: str, *, notification: str = "",
    ) -> dict:
        body: dict[str, Any] = {"callback_id": callback_id}
        if notification:
            body["notification"] = notification
        return await self._request("POST", "/answers", json=body)

    async def set_webhook(
        self,
        url: str,
        *,
        secret: str | None = None,
        update_types: list[str] | None = None,
    ) -> dict:
        body: dict[str, Any] = {"url": url}
        if secret:
            body["secret"] = secret
        if update_types:
            body["update_types"] = update_types
        return await self._request("POST", "/subscriptions", json=body)

    async def delete_webhook(self, url: str) -> dict:
        return await self._request(
            "DELETE", "/subscriptions", params={"url": url},
        )


max_client = MaxBotClient()
