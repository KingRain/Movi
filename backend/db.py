"""SQLite database for user accounts and taste profiles."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "movi.db"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_movies (
                user_id INTEGER NOT NULL,
                tmdb_id INTEGER NOT NULL,
                loved INTEGER NOT NULL DEFAULT 0,
                watched INTEGER NOT NULL DEFAULT 0,
                title TEXT NOT NULL DEFAULT '',
                overview TEXT NOT NULL DEFAULT '',
                poster_url TEXT,
                release_year INTEGER,
                genres TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, tmdb_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS guest_sessions (
                token TEXT PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guest_token TEXT,
                tmdb_id INTEGER NOT NULL,
                interaction_type TEXT NOT NULL,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                completion_ratio REAL NOT NULL DEFAULT 0.0,
                weight REAL NOT NULL DEFAULT 1.0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_user_interactions_user
                ON user_interactions(user_id, tmdb_id);
            CREATE INDEX IF NOT EXISTS idx_user_interactions_guest
                ON user_interactions(guest_token, tmdb_id);
            """
        )
        conn.commit()
