"""DOM_MAX — Бот-диспетчер для УК в домовых чатах Max."""

import logging
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from src.config import settings
from src.logging_config import configure_logging

logger = logging.getLogger("dom_max")

db_pool: asyncpg.Pool | None = None
redis_client: aioredis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, redis_client

    configure_logging(debug=settings.debug)
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

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    await redis_client.ping()
    logger.info("Redis connected")

    yield

    logger.info("Shutting down DOM_MAX...")
    if redis_client:
        await redis_client.aclose()
    if db_pool:
        await db_pool.close()
    logger.info("Bye.")


app = FastAPI(
    title="DOM_MAX",
    description="Бот-диспетчер для УК в домовых чатах Max",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> JSONResponse:
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
    return JSONResponse(
        content={"status": "ok"} if healthy else {"status": "degraded", "checks": checks},
        status_code=200 if healthy else 503,
    )


@app.post("/webhook")
async def webhook(
    request: Request,
    x_max_bot_api_secret: str | None = Header(default=None, alias="X-Max-Bot-Api-Secret"),
) -> JSONResponse:
    """Принимает события от Max Bot API. Верифицирует X-Max-Bot-Api-Secret."""
    from src.bot.webhook import handle_update

    expected = settings.webhook_secret
    if expected:
        if not x_max_bot_api_secret or x_max_bot_api_secret != expected:
            logger.warning(
                "Webhook signature mismatch from %s",
                request.client.host if request.client else "?",
            )
            raise HTTPException(status_code=401, detail="invalid signature")

    payload = await request.json()
    logger.debug("Webhook payload: %s", payload)

    try:
        result = await handle_update(payload, db_pool, redis_client)
        return JSONResponse({"ok": True, "result": result})
    except Exception:
        logger.exception("Webhook handler error")
        return JSONResponse({"ok": False}, status_code=200)
