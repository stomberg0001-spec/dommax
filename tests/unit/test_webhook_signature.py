"""Webhook принимает только запросы с валидной X-Max-Bot-Api-Secret."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src import config as _config_module
from src.main import app


@pytest.fixture
def client(monkeypatch):
    # settings — модульный синглтон; подменяем атрибут на время теста
    monkeypatch.setattr(_config_module.settings, "webhook_secret", "secret-abc-123")
    with patch("src.bot.webhook.handle_update", new=AsyncMock(return_value="ok")):
        yield TestClient(app)


def test_webhook_rejects_missing_secret(client):
    r = client.post("/webhook", json={"update_type": "message_created"})
    assert r.status_code == 401


def test_webhook_rejects_wrong_secret(client):
    r = client.post(
        "/webhook",
        json={"update_type": "message_created"},
        headers={"X-Max-Bot-Api-Secret": "wrong"},
    )
    assert r.status_code == 401


def test_webhook_accepts_correct_secret(client):
    r = client.post(
        "/webhook",
        json={"update_type": "message_created"},
        headers={"X-Max-Bot-Api-Secret": "secret-abc-123"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "result": "ok"}
