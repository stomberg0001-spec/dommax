"""Конфигурация приложения из .env."""

import logging
import sys
from urllib.parse import quote_plus

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings

logger = logging.getLogger("dom_max.config")


class Settings(BaseSettings):
    bot_token: str
    db_host: str = "localhost"
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = "dom_max"
    db_user: str = "dom_max"
    db_password: str

    redis_url: str = "redis://localhost:6379/0"

    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = False

    notify_rps: int = Field(default=25, ge=1, le=30)  # 30 RPS — лимит Max API

    webhook_url: str = ""
    webhook_secret: str = Field(
        default="",
        pattern=r"^$|^[A-Za-z0-9-]{5,256}$",
        description="Передаётся при POST /subscriptions, проверяется в X-Max-Bot-Api-Secret",
    )

    max_api_base_url: str = "https://platform-api.max.ru"

    rate_limiter_fail_open: bool = False

    @property
    def db_dsn(self) -> str:
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
