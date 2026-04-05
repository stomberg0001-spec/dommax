"""Конфигурация приложения из .env."""

import logging
import sys
from urllib.parse import quote_plus

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings

logger = logging.getLogger("dom_max.config")


class Settings(BaseSettings):
    # Max Bot
    bot_token: str

    # PostgreSQL
    db_host: str = "localhost"
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = "dom_max"
    db_user: str = "dom_max"
    db_password: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = False

    # Rate limits (BUG-001 fix: ge=1 prevents division by zero)
    notify_rps: int = Field(default=25, ge=1, le=100)

    # Webhook
    webhook_url: str = ""  # https://your-domain.ru/webhook

    @property
    def db_dsn(self) -> str:
        """DSN с URL-encoding пароля (безопасен для спецсимволов)."""
        password = quote_plus(self.db_password)
        user = quote_plus(self.db_user)
        return f"postgresql://{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


try:
    settings = Settings()
except ValidationError as e:
    print(
        "\n❌ Ошибка конфигурации DOM_MAX.\n\n"
        "Проверьте файл .env (см. .env.example для справки).\n\n"
        f"Детали:\n{e}\n",
        file=sys.stderr,
    )
    sys.exit(1)
