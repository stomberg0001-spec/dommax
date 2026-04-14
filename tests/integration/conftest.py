"""Integration-фикстуры: реальная PostgreSQL через pytest-postgresql."""

from pathlib import Path

import asyncpg
import pytest_asyncio
from pytest_postgresql import factories

postgresql_proc = factories.postgresql_proc(
    port=None,
    unixsocketdir="/tmp",
)
postgresql = factories.postgresql("postgresql_proc")


@pytest_asyncio.fixture
async def db_pool(postgresql):
    """Пул asyncpg, накатывающий миграции из src/db/migrations/."""
    dsn = (
        f"postgresql://{postgresql.info.user}@"
        f"{postgresql.info.host}:{postgresql.info.port}/"
        f"{postgresql.info.dbname}"
    )
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)

    migrations_dir = Path(__file__).parent.parent.parent / "src" / "db" / "migrations"
    for sql_file in sorted(migrations_dir.glob("*.sql")):
        async with pool.acquire() as conn:
            await conn.execute(sql_file.read_text(encoding="utf-8"))

    yield pool
    await pool.close()
