-- 001_init.sql — Начальная миграция DOM_MAX
-- Соответствует L0: src/api/schemas.py
-- Дата: 2026-04-05

BEGIN;

-- Enums (соответствуют StrEnum в schemas.py)
CREATE TYPE ticket_status AS ENUM ('new', 'accepted', 'in_progress', 'done', 'rejected');
CREATE TYPE notification_type AS ENUM ('emergency', 'planned_works', 'meeting', 'info');
CREATE TYPE message_type AS ENUM ('text', 'photo', 'command', 'callback', 'sticker', 'other');

-- УК (UKProfile)
CREATE TABLE uk_profiles (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    inn         VARCHAR(12) NOT NULL CHECK (inn ~ '^\d{10,12}$'),
    contact_phone VARCHAR(20) NOT NULL CHECK (contact_phone ~ '^\+7\d{10}$'),
    contact_email TEXT NOT NULL CHECK (contact_email ~* '^[^@]+@[^@]+\.[^@]+$'),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_uk_profiles_inn ON uk_profiles(inn);

-- Дома (House)
CREATE TABLE houses (
    id               BIGSERIAL PRIMARY KEY,
    uk_id            BIGINT NOT NULL REFERENCES uk_profiles(id) ON DELETE CASCADE,
    address          TEXT NOT NULL,
    chat_id          BIGINT NOT NULL,  -- ID группового чата в Max
    apartments_count INT NOT NULL DEFAULT 0 CHECK (apartments_count >= 0),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_houses_chat_id ON houses(chat_id);
CREATE INDEX idx_houses_uk_id ON houses(uk_id);

-- Пользователи (User)
CREATE TABLE users (
    id           BIGSERIAL PRIMARY KEY,
    max_user_id  BIGINT NOT NULL,  -- ID пользователя в Max
    house_id     BIGINT REFERENCES houses(id) ON DELETE SET NULL,
    display_name TEXT NOT NULL,
    is_uk_staff  BOOLEAN NOT NULL DEFAULT false,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_users_max_user_id ON users(max_user_id);
CREATE INDEX idx_users_house_id ON users(house_id);

-- FAQ (FAQItem)
CREATE TABLE faq_items (
    id         BIGSERIAL PRIMARY KEY,
    uk_id      BIGINT NOT NULL REFERENCES uk_profiles(id) ON DELETE CASCADE,
    question   TEXT NOT NULL,
    answer     TEXT NOT NULL,
    category   TEXT NOT NULL DEFAULT '',
    is_active  BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_faq_items_uk_id ON faq_items(uk_id);
CREATE INDEX idx_faq_items_active ON faq_items(uk_id, is_active) WHERE is_active = true;

-- Заявки (Ticket)
CREATE TABLE tickets (
    id            BIGSERIAL PRIMARY KEY,
    house_id      BIGINT NOT NULL REFERENCES houses(id) ON DELETE CASCADE,
    user_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    description   TEXT NOT NULL CHECK (char_length(description) >= 5),
    photo_file_id TEXT,
    status        ticket_status NOT NULL DEFAULT 'new',
    assigned_to   BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tickets_house_id ON tickets(house_id);
CREATE INDEX idx_tickets_status ON tickets(house_id, status);
CREATE INDEX idx_tickets_user_id ON tickets(user_id);

-- Уведомления (Notification)
CREATE TABLE notifications (
    id         BIGSERIAL PRIMARY KEY,
    uk_id      BIGINT NOT NULL REFERENCES uk_profiles(id) ON DELETE CASCADE,
    type       notification_type NOT NULL,
    title      TEXT NOT NULL CHECK (char_length(title) >= 3),
    body       TEXT NOT NULL,
    house_ids  BIGINT[] NOT NULL CHECK (array_length(house_ids, 1) >= 1),
    sent_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notifications_uk_id ON notifications(uk_id);

-- Лог сообщений (MessageLog)
CREATE TABLE message_logs (
    id           BIGSERIAL PRIMARY KEY,
    chat_id      BIGINT NOT NULL,
    user_id      BIGINT NOT NULL,
    text         TEXT,
    message_type message_type NOT NULL DEFAULT 'text',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_message_logs_chat_id ON message_logs(chat_id);
CREATE INDEX idx_message_logs_created ON message_logs(created_at);

-- Миграции — трекинг
CREATE TABLE _migrations (
    id         SERIAL PRIMARY KEY,
    filename   TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO _migrations (filename) VALUES ('001_init.sql');

COMMIT;
