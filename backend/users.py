"""User accounts, sessions, and persisted taste profiles."""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from typing import Any

from db import connect, init_db

init_db()


def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    )
    return digest.hex()


def register_user(username: str, password: str) -> dict[str, Any]:
    name = username.strip()
    if len(name) < 3:
        raise ValueError("Username must be at least 3 characters")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)

    with connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
                (name, password_hash, salt),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Username already taken") from exc
        user_id = int(cur.lastrowid)
        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO sessions (token, user_id) VALUES (?, ?)",
            (token, user_id),
        )
        conn.commit()

    return {"token": token, "user": {"id": user_id, "username": name}}


def login_user(username: str, password: str) -> dict[str, Any]:
    name = username.strip()
    with connect() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, salt FROM users WHERE username = ?",
            (name,),
        ).fetchone()
        if not row:
            raise ValueError("Invalid username or password")
        if _hash_password(password, row["salt"]) != row["password_hash"]:
            raise ValueError("Invalid username or password")

        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO sessions (token, user_id) VALUES (?, ?)",
            (token, row["id"]),
        )
        conn.commit()

    return {"token": token, "user": {"id": row["id"], "username": row["username"]}}


def logout_user(token: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()


def user_from_token(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    with connect() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.username
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
    if not row:
        return None
    return {"id": row["id"], "username": row["username"]}


def get_taste(user_id: int) -> dict[str, Any]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT tmdb_id, loved, watched, title, overview, poster_url,
                   release_year, genres
            FROM user_movies
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id,),
        ).fetchall()

    liked: list[int] = []
    watched: list[int] = []
    movies: list[dict[str, Any]] = []

    for row in rows:
        tid = int(row["tmdb_id"])
        is_watched = bool(row["watched"]) or bool(row["loved"])
        if is_watched:
            watched.append(tid)
            try:
                genre_ids = json.loads(row["genres"] or "[]")
            except json.JSONDecodeError:
                genre_ids = []
            movies.append(
                {
                    "tmdb_id": tid,
                    "id": tid,
                    "title": row["title"],
                    "overview": row["overview"],
                    "poster_url": row["poster_url"],
                    "release_year": row["release_year"],
                    "genre_ids": genre_ids,
                    "watched": True,
                }
            )

    return {"watched": watched, "movies": movies}


def upsert_movie(user_id: int, movie: dict[str, Any]) -> None:
    tid = int(movie["tmdb_id"])
    watched = 1 if movie.get("watched") else 0
    genres = json.dumps(movie.get("genre_ids") or [])

    if not watched:
        with connect() as conn:
            conn.execute(
                "DELETE FROM user_movies WHERE user_id = ? AND tmdb_id = ?",
                (user_id, tid),
            )
            conn.commit()
        return

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO user_movies (
                user_id, tmdb_id, loved, watched, title, overview,
                poster_url, release_year, genres, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, tmdb_id) DO UPDATE SET
                loved = 0,
                watched = excluded.watched,
                title = excluded.title,
                overview = excluded.overview,
                poster_url = excluded.poster_url,
                release_year = excluded.release_year,
                genres = excluded.genres,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                tid,
                0,
                watched,
                movie.get("title", ""),
                movie.get("overview", ""),
                movie.get("poster_url"),
                movie.get("release_year"),
                genres,
            ),
        )
        conn.commit()


def clear_taste(user_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM user_movies WHERE user_id = ?", (user_id,))
        conn.commit()
