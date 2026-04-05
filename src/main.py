"""DOM_MAX — Бот-диспетчер для УК в домовых чатах Max.

Точка входа: uvicorn src.main:app --reload
"""

import asyncio
import logging
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response

from src.config import settings

logger = logging.getLogger("dom_max")


# --- Глобальные ресурсы (инициализируются в lifespan) ---

db_pool: asyncpg.Pool | None = None
redis_client: aioredis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация и очистка ресурсов."""
    global db_pool, redis_client

    # --- Startup ---
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    logger.info("Starting DOM_MAX...")

    db_pool = await asyncpg.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        min_size=2,
        max_size=10,
    )
    logger.info("PostgreSQL pool ready")

    redis_client = aioredis.from_url(
        settings.redis_url, decode_responses=True,
    )
    await redis_client.ping()
    logger.info("Redis connected")

    yield

    # --- Shutdown ---
    logger.info("Shutting down DOM_MAX...")
    if redis_client:
        await redis_client.aclose()
    if db_pool:
        await db_pool.close()
    logger.info("Bye.")


app = FastAPI(
    title="DOM_MAX",
    description="Бот-диспетчер для УК в домовых чатах Max",
    version="0.1.0",
    lifespan=lifespan,
)


# --- Health check ---

@app.get("/health")
async def health():
    """L4: health check для мониторинга."""
    checks = {"app": "ok", "db": "error", "redis": "error"}
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["db"] = "ok"
    except Exception as e:
        logger.error("DB health check failed: %s", e)

    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as e:
        logger.error("Redis health check failed: %s", e)

    healthy = all(v == "ok" for v in checks.values())
    return Response(
        content='{"status":"ok"}' if healthy else '{"status":"degraded","checks":' + str(checks).replace("'", '"') + '}',
        status_code=200 if healthy else 503,
        media_type="application/json",
    )


# --- Max Bot Webhook ---

@app.post("/webhook")
async def webhook(request: Request):
    """Принимает входящие события от Max Bot API."""
    from src.bot.webhook import handle_update

    payload = await request.json()
    logger.debug("Webhook payload: %s", payload)

    try:
        result = await handle_update(payload, db_pool, redis_client)
        return {"ok": True, "result": result}
    except Exception:
        logger.exception("Webhook handler error")
        return {"ok": False}


# --- REST API для Mini App (Stage 3) ---
# from src.api.routes import router as api_router
# app.include_router(api_router, prefix="/api/v1")
