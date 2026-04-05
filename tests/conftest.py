"""Pytest configuration — общие фикстуры."""

import os
import sys

# Добавить корень проекта в sys.path для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Установить переменные окружения для тестов (чтобы Settings() не падала)
os.environ.setdefault("BOT_TOKEN", "test-token-for-unit-tests")
os.environ.setdefault("DB_PASSWORD", "test-password")
