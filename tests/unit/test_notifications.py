"""Unit-тесты notification worker — проверяют форматирование и edge cases."""

from src.services.notifications import TYPE_EMOJI, TYPE_LABEL


class TestNotificationConstants:
    def test_all_types_have_emoji(self):
        """Каждый тип уведомления имеет эмодзи."""
        expected_types = {"emergency", "planned_works", "meeting", "info"}
        assert set(TYPE_EMOJI.keys()) == expected_types

    def test_all_types_have_label(self):
        """Каждый тип уведомления имеет человекочитаемый лейбл."""
        expected_types = {"emergency", "planned_works", "meeting", "info"}
        assert set(TYPE_LABEL.keys()) == expected_types

    def test_emergency_is_prominent(self):
        """Аварийное уведомление выделяется."""
        assert "🚨" in TYPE_EMOJI["emergency"]
        assert TYPE_LABEL["emergency"] == "АВАРИЯ"

    def test_labels_are_russian(self):
        """Все лейблы на русском."""
        for label in TYPE_LABEL.values():
            # Хотя бы одна кириллическая буква
            assert any("\u0400" <= c <= "\u04ff" for c in label), f"Label '{label}' is not Russian"
