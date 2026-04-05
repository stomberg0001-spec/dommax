"""FAQ Engine — нечёткий поиск ответов по базе знаний УК.

Stage 1: rapidfuzz (token_sort_ratio)
Stage 2: sentence-transformers (TODO)
Stage 3: GigaChat RAG (TODO)
"""

import logging
import unicodedata

from rapidfuzz import fuzz

import asyncpg
from src.db.queries import get_active_faq

logger = logging.getLogger("dom_max.faq")

# Порог уверенности: ниже — не отвечаем
MATCH_THRESHOLD = 60.0

# Порог высокой уверенности: выше — отвечаем без уточнения
HIGH_CONFIDENCE = 80.0


async def match_faq(
    pool: asyncpg.Pool,
    *,
    uk_id: int,
    user_text: str,
) -> dict | None:
    """Найти лучшее совпадение FAQ для текста пользователя.

    Returns:
        dict с ключами: item (FAQItem dict), score (float 0-100)
        или None, если совпадений нет.
    """
    faq_items = await get_active_faq(pool, uk_id=uk_id)
    if not faq_items:
        return None

    # BUG-010 fix: ограничение длины; BUG-007 fix: Unicode NFC
    user_lower = unicodedata.normalize("NFC", user_text[:2000].lower().strip())
    if len(user_lower) < 3:
        return None

    best_match: dict | None = None
    best_score: float = 0.0

    for item in faq_items:
        question_lower = item["question"].lower()

        # Основной скор: нечёткое сравнение
        score = fuzz.token_sort_ratio(user_lower, question_lower)

        # Бонус за точное вхождение ключевых слов
        if user_lower in question_lower or question_lower in user_lower:
            score = min(score + 15, 100.0)

        if score > best_score:
            best_score = score
            best_match = item

    if best_score < MATCH_THRESHOLD or best_match is None:
        return None

    logger.info(
        "FAQ match: score=%.1f question='%s' user='%s'",
        best_score, best_match["question"][:50], user_text[:50],
    )

    return {"item": best_match, "score": best_score}


def format_faq_response(match: dict) -> str:
    """Форматировать ответ FAQ для пользователя."""
    item = match["item"]
    score = match["score"]

    if score >= HIGH_CONFIDENCE:
        return item["answer"]

    return (
        f"Возможно, вы спрашиваете: *{item['question']}*\n\n"
        f"{item['answer']}\n\n"
        f"_Если это не то, что вы искали — напишите заявку командой /ticket_"
    )
