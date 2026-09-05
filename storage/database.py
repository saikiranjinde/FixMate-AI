"""Local SQLite storage foundation for FixMate-AI."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

APP_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FixMate-AI"
DB_DIR = APP_DATA_DIR / "database"
DB_PATH = DB_DIR / "fixmate.db"


def get_connection() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                email TEXT UNIQUE,
                display_name TEXT,
                created_at TEXT NOT NULL,
                last_login_at TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                user_id INTEGER,
                provider TEXT,
                email TEXT,
                display_name TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS diagnosis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                overall_severity TEXT,
                issue_count INTEGER DEFAULT 0,
                report_path TEXT,
                status TEXT NOT NULL DEFAULT 'completed'
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )


def get_setting(key: str, default: str | None = None) -> str | None:
    initialize_database()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    initialize_database()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO app_settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
