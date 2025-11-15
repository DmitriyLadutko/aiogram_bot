import aiosqlite
import sqlite3
import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()
DB_PATH = os.getenv("DB_PATH") or "bot.db"


class Database:
    _conn: Optional[aiosqlite.Connection] = None

    @classmethod
    async def init(cls, db_path: Optional[str] = None):
        db_path = db_path or DB_PATH
        if not db_path:
            raise RuntimeError("DB_PATH не задан. Проверь .env")
        cls._conn = await aiosqlite.connect(db_path)
        cls._conn.row_factory = sqlite3.Row
        await cls._conn.execute("PRAGMA journal_mode=WAL;")
        await cls._conn.execute("PRAGMA foreign_keys = ON;")
        await cls._conn.commit()

    @classmethod
    async def close(cls):
        if cls._conn:
            await cls._conn.close()
            cls._conn = None

    @classmethod
    async def init_db(cls):
        if cls._conn is None:
            raise RuntimeError("DB не инициализирована. Вызови Database.init() первым.")
        await cls._conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                phone_number TEXT
            )
        """)
        await cls._conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                status TEXT DEFAULT 'новая',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await cls._conn.commit()

    # ---------------- USERS ----------------
    @classmethod
    async def add_user(cls, user_id: int, first_name: str, last_name: str, phone_number: str):
        if cls._conn is None:
            raise RuntimeError("DB not initialized")
        cur = await cls._conn.execute(
            "INSERT OR REPLACE INTO users (user_id, first_name, last_name, phone_number) VALUES (?, ?, ?, ?)",
            (user_id, first_name, last_name, phone_number)
        )
        await cls._conn.commit()
        await cur.close()

    @classmethod
    async def is_registered(cls, user_id: int) -> bool:
        if cls._conn is None:
            raise RuntimeError("DB not initialized")
        cur = await cls._conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        await cur.close()
        return row is not None

    # ---------------- REQUESTS ----------------
    @classmethod
    async def add_request(cls, user_id: int, text: str) -> int:
        if cls._conn is None:
            raise RuntimeError("DB not initialized")
        cur = await cls._conn.execute(
            "INSERT INTO requests (user_id, text, status) VALUES (?, ?, ?)",
            (user_id, text, "новая")
        )
        await cls._conn.commit()
        last_id = cur.lastrowid
        await cur.close()
        return last_id

    @classmethod
    async def get_user_requests(cls, user_id: int, hide_completed: bool = True):
        if cls._conn is None:
            raise RuntimeError("DB not initialized")
        if hide_completed:
            cur = await cls._conn.execute("""
                SELECT id, text, status, created_at
                FROM requests
                WHERE user_id = ? AND status != 'отменена'
                ORDER BY created_at DESC
            """, (user_id,))
        else:
            cur = await cls._conn.execute("""
                SELECT id, text, status, created_at
                FROM requests
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,))
        rows = await cur.fetchall()
        await cur.close()
        return rows

    @classmethod
    async def get_all_requests(cls, hide_completed: bool = False):
        if cls._conn is None:
            raise RuntimeError("DB not initialized")
        if hide_completed:
            cur = await cls._conn.execute("""
                SELECT id, user_id, text, status, created_at
                FROM requests
                WHERE status != 'отменена'
                ORDER BY created_at DESC
            """)
        else:
            cur = await cls._conn.execute("""
                SELECT id, user_id, text, status, created_at
                FROM requests
                ORDER BY created_at DESC
            """)
        rows = await cur.fetchall()
        await cur.close()
        return rows

    @classmethod
    async def update_request_status(cls, request_id: int, status: str) -> bool:
        if cls._conn is None:
            raise RuntimeError("DB not initialized")
        cur = await cls._conn.execute("UPDATE requests SET status=? WHERE id=?", (status, request_id))
        await cls._conn.commit()
        changed = cur.rowcount > 0
        await cur.close()
        return changed

    @classmethod
    async def delete_request(cls, request_id: int) -> bool:
        if cls._conn is None:
            raise RuntimeError("DB not initialized")
        cur = await cls._conn.execute("DELETE FROM requests WHERE id=?", (request_id,))
        await cls._conn.commit()
        deleted = cur.rowcount > 0
        await cur.close()
        return deleted
