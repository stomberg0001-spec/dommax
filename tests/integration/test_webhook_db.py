"""End-to-end сценарий: житель → FAQ → тикет → статус (реальная БД)."""

import pytest

from src.db.queries import (
    create_ticket,
    get_active_faq,
    get_or_create_user,
    get_tickets_by_house,
    get_uk_by_chat_id,
)


@pytest.mark.asyncio
async def test_user_ticket_flow_against_real_postgres(db_pool):
    async with db_pool.acquire() as conn:
        uk_id = await conn.fetchval(
            "INSERT INTO uk_profiles (name, inn, contact_phone, contact_email) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            "Тест-УК", "1234567890", "+79991234567", "uk@test.ru",
        )
        house_id = await conn.fetchval(
            "INSERT INTO houses (uk_id, address, chat_id) VALUES ($1, $2, $3) RETURNING id",
            uk_id, "ул. Тест 1", 100500,
        )

    user = await get_or_create_user(
        db_pool, max_user_id=42, display_name="Иван", chat_id=100500,
    )
    assert user["house_id"] == house_id

    uk = await get_uk_by_chat_id(db_pool, chat_id=100500)
    assert uk and uk["id"] == uk_id

    ticket = await create_ticket(
        db_pool,
        house_id=house_id,
        user_id=user["id"],
        description="Течёт кран на кухне, нужна помощь",
    )
    assert ticket["status"] == "new"

    tickets = await get_tickets_by_house(db_pool, house_id=house_id)
    assert len(tickets) == 1
    assert tickets[0]["id"] == ticket["id"]


@pytest.mark.asyncio
async def test_faq_returns_empty_when_no_items(db_pool):
    async with db_pool.acquire() as conn:
        uk_id = await conn.fetchval(
            "INSERT INTO uk_profiles (name, inn, contact_phone, contact_email) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            "УК2", "9876543210", "+79997654321", "uk2@test.ru",
        )
    items = await get_active_faq(db_pool, uk_id=uk_id)
    assert items == []
