"""Unit-тесты FAQ Engine — проверяют логику нечёткого поиска (L1 vs L0)."""

import pytest

from src.bot.faq_engine import (
    HIGH_CONFIDENCE,
    MATCH_THRESHOLD,
    format_faq_response,
)


class TestFormatFaqResponse:
    """Тестируем форматирование ответа (не требует БД)."""

    def _make_match(self, score: float, question: str = "Q", answer: str = "A") -> dict:
        return {
            "item": {"question": question, "answer": answer},
            "score": score,
        }

    def test_high_confidence_returns_answer_only(self):
        match = self._make_match(HIGH_CONFIDENCE + 1, answer="Ответ УК")
        result = format_faq_response(match)
        assert result == "Ответ УК"

    def test_low_confidence_returns_clarification(self):
        match = self._make_match(MATCH_THRESHOLD + 1, question="Как подать показания?", answer="Через ЛК")
        result = format_faq_response(match)
        assert "Возможно, вы спрашиваете" in result
        assert "Как подать показания?" in result
        assert "Через ЛК" in result
        assert "/ticket" in result

    def test_threshold_boundary(self):
        match = self._make_match(HIGH_CONFIDENCE, answer="Exact")
        result = format_faq_response(match)
        # Ровно HIGH_CONFIDENCE — не высокая уверенность, показываем уточнение
        assert "Возможно" in result


class TestConstants:
    def test_threshold_less_than_high_confidence(self):
        assert MATCH_THRESHOLD < HIGH_CONFIDENCE

    def test_threshold_reasonable_range(self):
        assert 40 <= MATCH_THRESHOLD <= 80

    def test_high_confidence_reasonable(self):
        assert 70 <= HIGH_CONFIDENCE <= 95
