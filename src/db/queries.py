"""CRUD-операции для всех сущностей. Параметризованные запросы (asyncpg $1, $2...)."""

import logging

import asyncpg

logger = logging.getLogger("dom_max.db")


# --- Users ---

async def get_or_create_user(
    pool: asyncpg.Pool, *, max_user_id: int, display_name: str, chat_id: int,
) -> dict:
    """Найти пользователя по max_user_id или создать нового."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE max_user_id = $1", max_user_id,
        )
        if row:
            return dict(row)

        # Найти дом по chat_id
        house = await conn.fetchrow(
            "SELECT id FROM houses WHERE chat_id = $1", chat_id,
        )
        house_id = house["id"] if house else None

        row = await conn.fetchrow(
            """INSERT INTO users (max_user_id, house_id, display_name)
               VALUES ($1, $2, $3)
               RETURNING *""",
            max_user_id, house_id, display_name,
        )
        return dict(row)


# --- FAQ ---

async def get_active_faq(pool: asyncpg.Pool, *, uk_id: int) -> list[dict]:
    """Получить все активные FAQ-записи для УК."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM faq_items WHERE uk_id = $1 AND is_active = true",
            uk_id,
        )
        return [dict(r) for r in rows]


async def get_uk_by_chat_id(pool: asyncpg.Pool, *, chat_id: int) -> dict | None:
    """Найти УК по chat_id дома."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT u.* FROM uk_profiles u
               JOIN houses h ON h.uk_id = u.id
               WHERE h.chat_id = $1""",
            chat_id,
        )
        return dict(row) if row else None


# --- Tickets ---

async def create_ticket(
    pool: asyncpg.Pool,
    *,
    house_id: int,
    user_id: int,
    description: str,
    photo_file_id: str | None = None,
) -> dict:
    """Создать заявку."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO tickets (house_id, user_id, description, photo_file_id)
               VALUES ($1, $2, $3, $4)
               RETURNING *""",
            house_id, user_id, description, photo_file_id,
        )
        return dict(row)


async def update_ticket_status(
    pool: asyncpg.Pool,
    *,
    ticket_id: int,
    status: str,
    assigned_to: int | None = None,
) -> dict | None:
    """Обновить статус заявки."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE tickets
               SET status = $2::ticket_status, assigned_to = $3, updated_at = now()
               WHERE id = $1
               RETURNING *""",
            ticket_id, status, assigned_to,
        )
        return dict(row) if row else None


async def get_tickets_by_house(
    pool: asyncpg.Pool, *, house_id: int, status: str | None = None,
) -> list[dict]:
    """Получить заявки дома, опционально фильтр по статусу."""
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM tickets WHERE house_id = $1 AND status = $2::ticket_status ORDER BY created_at DESC",
                house_id, status,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM tickets WHERE house_id = $1 ORDER BY created_at DESC",
                house_id,
            )
        return [dict(r) for r in rows]


# --- Notifications ---

async def create_notification(
    pool: asyncpg.Pool,
    *,
    uk_id: int,
    type_: str,
    title: str,
    body: str,
    house_ids: list[int],
) -> dict:
    """Создать уведомление."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO notifications (uk_id, type, title, body, house_ids)
               VALUES ($1, $2::notification_type, $3, $4, $5)
               RETURNING *""",
            uk_id, type_, title, body, house_ids,
        )
        return dict(row)


async def mark_notification_sent(pool: asyncpg.Pool, *, notification_id: int) -> None:
    """Пометить уведомление как отправленное."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE notifications SET sent_at = now(), updated_at = now() WHERE id = $1",
            notification_id,
        )


# --- Message Log ---

async def log_message(
    pool: asyncpg.Pool,
    *,
    chat_id: int,
    user_id: int,
    text: str | None,
    message_type: str,
) -> None:
    """Записать сообщение в лог (для аналитики)."""
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO message_logs (chat_id, user_id, text, message_type)
               VALUES ($1, $2, $3, $4::message_type)""",
            chat_id, user_id, text, message_type,
        )


# --- Migrations ---

async def run_migrations(pool: asyncpg.Pool, migrations_dir: str) -> list[str]:
    """Применить непримененные SQL-миграции."""
    import os

    applied: list[str] = []
    async with pool.acquire() as conn:
        # Создать таблицу миграций, если не существует
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                filename TEXT NOT NULL UNIQUE,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)

        existing = {
            r["filename"]
            for r in await conn.fetch("SELECT filename FROM _migrations")
        }

        files = sorted(f for f in os.listdir(migrations_dir) if f.endswith(".sql"))
        for fname in files:
            if fname in existing:
                continue
            path = os.path.join(migrations_dir, fname)
            sql = open(path, encoding="utf-8").read()
            await conn.execute(sql)
            await conn.execute(
                "INSERT INTO _migrations (filename) VALUES ($1)", fname,
            )
            applied.append(fname)
            logger.info("Applied migration: %s", fname)

    return applied
