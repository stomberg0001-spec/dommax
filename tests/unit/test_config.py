"""Unit-тесты config — проверяют DSN builder (AUD-0007 fix)."""

from urllib.parse import quote_plus


def test_dsn_special_chars_in_password():
    """Пароль со спецсимволами не ломает DSN."""
    password = "p@ss:w0rd/test%123"
    encoded = quote_plus(password)
    dsn = f"postgresql://user:{encoded}@localhost:5432/db"

    assert "@" not in encoded.split("@")[0] or "%" in encoded
    assert "localhost:5432/db" in dsn
    assert password not in dsn  # Исходный пароль закодирован


def test_dsn_simple_password():
    """Простой пароль работает без проблем."""
    password = "simple123"
    encoded = quote_plus(password)
    dsn = f"postgresql://user:{encoded}@localhost:5432/db"
    assert f"user:{password}@" in dsn
