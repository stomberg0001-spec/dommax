"""Проверки HTTP-контракта Max Bot API клиента (без реальной сети)."""

import httpx
import pytest
import respx

from src.services.max_client import MaxBotClient


@pytest.mark.asyncio
@respx.mock
async def test_send_message_uses_query_chat_id_and_header_auth():
    route = respx.post("https://platform-api.max.ru/messages").mock(
        return_value=httpx.Response(200, json={"message": {"mid": "m1"}}),
    )
    client = MaxBotClient(token="t-test")
    await client.send_message(chat_id=42, text="hi")

    assert route.called
    request = route.calls.last.request
    assert request.headers.get("Authorization") == "t-test"
    assert request.url.params.get("chat_id") == "42"
    assert b'"text":"hi"' in request.content
    assert b"chat_id" not in request.content
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_send_message_truncates_to_4000_chars():
    route = respx.post("https://platform-api.max.ru/messages").mock(
        return_value=httpx.Response(200, json={}),
    )
    client = MaxBotClient(token="t")
    await client.send_message(chat_id=1, text="x" * 5000)

    sent_body = route.calls.last.request.content.decode()
    # "text":"xxx..." — 1 'x' в ключе "text" + 4000 в значении = 4001
    assert sent_body.count("x") == 4001
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_set_webhook_passes_secret_and_update_types():
    route = respx.post("https://platform-api.max.ru/subscriptions").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    client = MaxBotClient(token="t")
    await client.set_webhook(
        "https://example.com/webhook",
        secret="abc-DEF-123",
        update_types=["message_created", "message_callback"],
    )

    body = route.calls.last.request.content.decode()
    assert '"secret":"abc-DEF-123"' in body
    assert '"message_created"' in body
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_send_message_retries_on_503():
    route = respx.post("https://platform-api.max.ru/messages").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json={"ok": True}),
        ],
    )
    client = MaxBotClient(token="t")
    result = await client.send_message(chat_id=1, text="ok")

    assert result == {"ok": True}
    assert route.call_count == 3
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_send_message_does_not_retry_on_400():
    route = respx.post("https://platform-api.max.ru/messages").mock(
        return_value=httpx.Response(400, json={"error": "bad chat"}),
    )
    client = MaxBotClient(token="t")
    with pytest.raises(httpx.HTTPStatusError):
        await client.send_message(chat_id=1, text="ok")

    assert route.call_count == 1
    await client.close()
