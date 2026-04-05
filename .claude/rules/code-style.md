# Code Style — DOM_MAX

## Python
- Python 3.11+
- Форматирование: `ruff format`
- Линтинг: `ruff check`
- Type hints на публичных функциях и Pydantic models
- Docstrings: только на неочевидной логике (не на каждой функции)
- Именование: snake_case (функции, переменные), PascalCase (классы, Pydantic models)

## SQL
- Все запросы параметризованные через asyncpg ($1, $2...)
- НИКОГДА f-строки или format() для SQL
- Миграции: отдельные .sql файлы в src/db/migrations/, нумерация 001_, 002_...

## Async
- Весь I/O — async/await (asyncpg, aioredis, aiohttp)
- Синхронные вызовы в async контексте запрещены

## Коммиты
- Формат: `тип: описание` (на русском)
- Типы: feat: / fix: / docs: / test: / refactor: / deploy:
- Атомарные: один логический блок = один коммит

## Структура импортов
```python
# stdlib
import asyncio
from datetime import datetime

# third-party
from fastapi import FastAPI
from pydantic import BaseModel

# local
from src.db.pool import get_pool
from src.bot.faq_engine import match_faq
```
