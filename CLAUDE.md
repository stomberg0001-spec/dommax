# DOM_MAX — Бот-диспетчер для УК в домовых чатах Max

> Совместная разработка двумя разработчиками через GitHub + Claude Code

## Контекст

ФЗ-529 (29.12.2025) обязывает УК вести домовые чаты в мессенджере Max. Дедлайн — 01.09.2026.
DOM_MAX — первый коммерческий ЖКХ-бот для Max. Работает **внутри обязательного канала**, где уже находятся жители.

## Архитектура

```
Max Messenger → Webhook HTTPS → nginx → FastAPI + Uvicorn (монолит)
                                            ├── bot/        ← Webhook handler, FAQ, заявки, модерация
                                            ├── api/        ← REST API для Mini App (Sprint 3)
                                            ├── services/   ← Rate limiter, notification worker, Max client
                                            └── db/         ← asyncpg + PostgreSQL
                                        Redis ← sessions, rate_limit, notification queue
```

### Стек

| Компонент | Технология |
|-----------|-----------|
| Язык | Python 3.11 |
| Фреймворк | FastAPI + Uvicorn |
| БД | PostgreSQL (asyncpg) |
| Кэш/очередь | Redis (aioredis) |
| AI-matching | rapidfuzz (Stage 1) → sentence-transformers (Stage 2) → GigaChat (Stage 3) |
| Деплой | systemd + nginx, VPS Россия (Timeweb/Selectel) |

### Структура проекта

```
dom-max/
├── CLAUDE.md                  ← Ты читаешь этот файл
├── .claude/rules/             ← Правила качества и стиля
├── src/
│   ├── bot/                   ← Логика бота (webhook, FAQ, заявки, модерация)
│   ├── api/                   ← REST API для Mini App
│   ├── db/                    ← БД: pool, queries, migrations/
│   └── services/              ← Rate limiter, notification worker, Max client
├── tests/
│   ├── unit/                  ← L1: бизнес-логика изолированно
│   ├── integration/           ← L2: API + реальная БД (не моки!)
│   └── regression/            ← Каждый баг = тест
├── auditors/                  ← Скрипты-аудиторы (Фаза 2)
├── docs/specs/                ← L0: OpenAPI, JSON Schema, Pydantic models
├── data/                      ← Выходные данные и отчёты
├── deploy/                    ← systemd unit, nginx conf, backup script
└── audit_reports/             ← Результаты аудитов
```

## Команды

```bash
# Запуск
uvicorn src.main:app --reload

# Тесты
python -m pytest tests/ -v

# Линтинг
ruff check src/ tests/
ruff format src/ tests/

# Синхронизация
git pull origin main
```

## Правила работы

### Для обоих разработчиков
- Перед началом работы: `git pull origin main`
- Коммит-сообщения: `тип: описание` (feat: / fix: / docs: / test: / refactor:)
- НЕ коммитить секреты — они в `.env` (добавлен в .gitignore)
- JSON: UTF-8, отступ 2 пробела, ключи snake_case
- Python: ruff format, type hints на публичных функциях

### Система качества (Layer Trust Architecture)
- **L0** — Pydantic models в `src/api/schemas.py` и `docs/specs/` = источник истины
- **L1** — Код проверяется unit-тестами против L0
- **L2** — Интеграции проверяются integration-тестами с реальной БД
- **L3** — UI (Mini App) проверяется e2e-тестами
- **L4** — Runtime: structured logging, health checks
- Слой **никогда** не верифицирует сам себя

### Контекст для Claude
- Ты работаешь в команде из двух разработчиков
- Второй разработчик тоже использует Claude Code
- Файлы могут быть изменены другим участником — проверяй актуальность
- При генерации данных — не перезаписывай чужие изменения
- Баг найден → grep по всему проекту → исправить ВСЕ вхождения (каскадная верификация)

## MVP-функции (Stage 1)

1. **Диспетчерская / FAQ** — автоответы на типовые вопросы (rapidfuzz matching)
2. **Заявки с фото** — создание тикетов, маршрутизация, статусы
3. **Уведомления** — аварии, плановые работы, собрания (Приказ 856/пр)
4. **Модерация** — антиспам, стоп-слова, мат-фильтр, правила чата

## Ограничения

- Сервер в РФ (152-ФЗ: персональные данные)
- Max Bot API — основной и единственный мессенджер
- Голосования/ОСС исключены из скоупа (ФЗ-463: только через Госуслуги)
