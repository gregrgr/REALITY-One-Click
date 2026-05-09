from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .security import hash_password, random_token, random_uuid


SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    uuid TEXT NOT NULL UNIQUE,
    subscription_token TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path

    @contextmanager
    def connect(self) -> Iterable[sqlite3.Connection]:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def upsert_admin(self, username: str, password: str) -> None:
        password_digest = hash_password(password)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO admins (username, password_hash)
                VALUES (?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password_hash = excluded.password_hash,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (username, password_digest),
            )

    def get_admin_by_username(self, username: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM admins WHERE username = ?",
                (username,),
            ).fetchone()

    def set_settings(self, values: dict[str, str]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                sorted(values.items()),
            )

    def get_settings(self) -> dict[str, str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def ensure_user(self, name: str) -> sqlite3.Row:
        existing = self.get_user_by_name(name)
        if existing:
            return existing
        return self.create_user(name)

    def create_user(self, name: str) -> sqlite3.Row:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (name, uuid, subscription_token, enabled)
                VALUES (?, ?, ?, 1)
                """,
                (name, random_uuid(), random_token()),
            )
            user_id = cursor.lastrowid
            return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def list_users(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM users ORDER BY id ASC",
            ).fetchall()

    def enabled_users(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE enabled = 1 ORDER BY id ASC",
            ).fetchall()

    def get_user(self, user_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def get_user_by_name(self, name: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()

    def get_user_by_token(self, token: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE subscription_token = ? AND enabled = 1",
                (token,),
            ).fetchone()

    def set_user_enabled(self, user_id: int, enabled: bool) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE users SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (1 if enabled else 0, user_id),
            )

    def delete_user(self, user_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    def reset_user_token(self, user_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET subscription_token = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (random_token(), user_id),
            )
            return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def reset_user_uuid(self, user_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET uuid = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (random_uuid(), user_id),
            )
            return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None

