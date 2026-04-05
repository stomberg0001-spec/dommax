---
date: 2026-04-05
author: Claude Code Auditor
round: 1
---

# Audit Report: DOM_MAX — Первичный аудит проекта

Дата: 2026-04-05
Метод: manual review (полная проверка всех файлов)
Раунд: 1

---

## Сводка

| Проверено | Pass | Warning | Error |
|-----------|------|---------|-------|
| 18        | 6    | 7       | 5     |

**Общая оценка:** Проект находится в стадии фундамента — архитектура и документация продуманы отлично (Layer Trust Architecture, quality gates, code style). L0 (Pydantic models) определён качественно. Однако реализация кода (L1), тестов (L1-L2), интеграций (L2), деплоя (L3) и мониторинга (L4) — **отсутствуют полностью**. Разрыв между документацией и реальным кодом — критический.

---

## Находки

### AUD-0001 — ERROR: Отсутствует `src/main.py` (точка входа)

- **Файл:** `src/main.py` — не существует
- **Сейчас:** CLAUDE.md указывает команду `uvicorn src.main:app --reload`, но файл `src/main.py` отсутствует. Приложение не запускается.
- **Ожидается:** FastAPI app instance, webhook endpoint, lifespan handler (L0: CLAUDE.md → архитектура)
- **Каскад:** Без `main.py` неработоспособны: bot/, api/, services/, db/ — весь проект
- **Действие:** Создать `src/main.py` с FastAPI app, lifespan (init DB pool + Redis), webhook route для Max Bot API

---

### AUD-0002 — ERROR: Отсутствуют миграции БД

- **Файл:** `src/db/migrations/` — пустая директория
- **Сейчас:** L0 (schemas.py) определяет 8 моделей данных (UKProfile, House, User, FAQItem, Ticket, Notification, MessageLog + enums), но ни одной SQL-миграции не существует
- **Ожидается:** SQL-миграции `001_init.sql` создающие таблицы, соответствующие Pydantic models (L0)
- **Каскад:** Без БД-схемы невозможны integration-тесты (L2), невозможен деплой (L3)
- **Действие:** Создать `src/db/migrations/001_init.sql` — таблицы uk_profiles, houses, users, faq_items, tickets, notifications, message_logs с типами, соответствующими L0

---

### AUD-0003 — ERROR: Нулевое покрытие тестами (L1-L2 = 0%)

- **Файл:** `tests/unit/`, `tests/integration/`, `tests/regression/` — все пустые (только .gitkeep)
- **Сейчас:** Ни одного тестового файла. Quality-gates.md требует unit-тесты (L1 vs L0), integration-тесты (L2 vs L1)
- **Ожидается:** Минимум unit-тесты на Pydantic validation (L0), тесты FAQ-matching, тесты создания заявок
- **Каскад:** Нарушены все 5 паттернов качества из quality-gates.md. Невозможна каскадная верификация (паттерн A)
- **Действие:** Приоритет 1 — создать `tests/unit/test_schemas.py` (валидация L0 моделей). Приоритет 2 — тесты бизнес-логики по мере написания кода

---

### AUD-0004 — ERROR: Реализация бизнес-логики отсутствует (L1 = 0%)

- **Файлы:** `src/bot/__init__.py`, `src/db/__init__.py`, `src/services/__init__.py` — все пустые
- **Сейчас:** Определены 4 MVP-функции (FAQ, заявки, уведомления, модерация), но код не написан
- **Ожидается:** Минимум webhook handler, FAQ engine (rapidfuzz), ticket CRUD, DB query layer
- **Каскад:** L0 (schemas) существует, но L1 (код) = пустота. Вся цепочка L1→L4 не работает
- **Действие:** Начать реализацию с `src/bot/webhook.py` (обработчик входящих сообщений Max) и `src/db/queries.py` (CRUD-операции)

---

### AUD-0005 — ERROR: Max Bot API клиент не определён

- **Файл:** `requirements.txt:8` — `# maxapi  # TODO: уточнить актуальный пакет`
- **Сейчас:** Основная зависимость проекта (Max Bot API SDK) не установлена и не определена. Закомментирована с TODO
- **Ожидается:** Рабочий HTTP-клиент для Max Bot API (отправка сообщений, получение вебхуков)
- **Каскад:** Без Max API клиента невозможны: отправка ответов, модерация, уведомления — все 4 MVP-функции
- **Действие:** Исследовать актуальный пакет Max Bot API (проверить pypi: `max-bot-api`, `maxapi`, или использовать HTTP-клиент `httpx` напрямую через platform-api.max.ru). Зафиксировать в requirements.txt

---

### AUD-0006 — WARNING: `pydantic-settings` не в requirements.txt

- **Файл:** `src/config.py:3` — `from pydantic_settings import BaseSettings`
- **Сейчас:** config.py импортирует `pydantic_settings`, но в requirements.txt указан только `pydantic>=2.6.0`. Начиная с Pydantic v2, `pydantic-settings` — отдельный пакет
- **Ожидается:** `pydantic-settings>=2.2.0` в requirements.txt
- **Каскад:** `pip install -r requirements.txt` → ImportError при запуске → проект не стартует
- **Действие:** Добавить `pydantic-settings>=2.2.0` в requirements.txt

---

### AUD-0007 — WARNING: DSN строится через f-string (потенциальная SQL-инъекция в DSN)

- **Файл:** `src/config.py:29-30`
- **Сейчас:** `f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"`
- **Ожидается:** URL-encoding пароля, т.к. спецсимволы в пароле (`@`, `:`, `/`, `%`) сломают DSN
- **Каскад:** При пароле с символом `@` — подключение к БД невозможно
- **Действие:** Использовать `urllib.parse.quote_plus(self.db_password)` или `asyncpg.connect()` с параметрами вместо DSN

---

### AUD-0008 — WARNING: Отсутствует валидация `contact_phone` и `contact_email`

- **Файл:** `src/api/schemas.py:37-38`
- **Сейчас:** `contact_phone: str` и `contact_email: str` — без валидации формата
- **Ожидается:** Pydantic `EmailStr` для email, regex-паттерн для телефона (L0 должен быть строгим)
- **Каскад:** Невалидные данные попадут в БД, невозможно будет отправить уведомление на email/телефон
- **Действие:** `contact_email: EmailStr`, `contact_phone: str = Field(pattern=r"^\+7\d{10}$")`

---

### AUD-0009 — WARNING: `message_type` — свободная строка вместо enum

- **Файл:** `src/api/schemas.py:134` — `message_type: str  # text, photo, command, callback`
- **Сейчас:** Типы сообщений указаны в комментарии, но не ограничены enum
- **Ожидается:** `MessageType(StrEnum)` по аналогии с `TicketStatus` и `NotificationType`
- **Каскад:** В MessageLog могут попасть произвольные строки → аналитика по типам сообщений будет грязной
- **Действие:** Создать `class MessageType(StrEnum)` с значениями: text, photo, command, callback, sticker, other

---

### AUD-0010 — WARNING: Нет `updated_at` в Notification и FAQItem

- **Файл:** `src/api/schemas.py:114-123, 67-74`
- **Сейчас:** `Notification` имеет `created_at` и `sent_at`, но нет `updated_at`. `FAQItem` — только `created_at` отсутствует вовсе
- **Ожидается:** Для аудируемых сущностей — `created_at` + `updated_at` (отслеживание изменений)
- **Каскад:** Невозможно определить, когда FAQ-ответ был актуализирован. Для Notification — нельзя отследить правки до отправки
- **Действие:** Добавить `created_at: datetime` и `updated_at: datetime` в FAQItem. Добавить `updated_at: datetime` в Notification

---

### AUD-0011 — WARNING: `docs/specs/` пуста — нет OpenAPI/JSON Schema

- **Файл:** `docs/specs/` — пустая директория
- **Сейчас:** CLAUDE.md и quality-gates.md ссылаются на `docs/specs/` как часть L0 (источник истины), но директория пуста
- **Ожидается:** OpenAPI spec для REST API, JSON Schema для Max Bot webhook payload
- **Каскад:** Dual-Source verification (паттерн B) невозможна — нет второго источника для сверки с Pydantic models
- **Действие:** Сгенерировать OpenAPI spec из FastAPI app (автоматически) после создания эндпоинтов. Добавить JSON Schema для Max webhook payload

---

### AUD-0012 — WARNING: Нет `auditors/known_exceptions.yaml`

- **Файл:** `auditors/known_exceptions.yaml` — не существует
- **Сейчас:** quality-gates.md (паттерн D) ссылается на `auditors/known_exceptions.yaml`, но файл отсутствует
- **Ожидается:** YAML-файл с описанием известных quirks Max API и допустимых отклонений
- **Каскад:** Будущие аудиты будут генерировать ложные срабатывания на известных ограничениях Max API
- **Действие:** Создать `auditors/known_exceptions.yaml` с базовой структурой. Заполнять по мере обнаружения quirks

---

## Положительные моменты (PASS)

| # | Что проверено | Результат |
|---|---------------|-----------|
| P1 | L0 Pydantic models — структура | ✅ 8 моделей, чёткие типы, StrEnum для статусов |
| P2 | CLAUDE.md — полнота | ✅ Архитектура, стек, команды, правила — всё описано |
| P3 | Quality gates — методология | ✅ Layer Trust Architecture, 5 паттернов, чек-листы |
| P4 | Code style rules | ✅ Ruff, type hints, SQL injection prevention, async-first |
| P5 | .env.example — безопасность | ✅ Секреты вынесены из кода, .gitignore настроен |
| P6 | Структура проекта | ✅ Грамотное разделение: src/bot, api, db, services + tests по слоям |

---

## Приоритеты исправлений

### Критические (блокируют запуск):
1. **AUD-0001** — Создать `src/main.py`
2. **AUD-0005** — Определить Max Bot API клиент
3. **AUD-0006** — Добавить `pydantic-settings` в requirements.txt
4. **AUD-0002** — Создать SQL-миграцию `001_init.sql`

### Высокие (блокируют качество):
5. **AUD-0004** — Начать реализацию бизнес-логики
6. **AUD-0003** — Написать первые unit-тесты
7. **AUD-0007** — Исправить DSN-конструктор (спецсимволы в пароле)

### Средние (L0 улучшения):
8. **AUD-0008** — Валидация phone/email
9. **AUD-0009** — MessageType enum
10. **AUD-0010** — Добавить updated_at/created_at
11. **AUD-0011** — OpenAPI spec
12. **AUD-0012** — known_exceptions.yaml
