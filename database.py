import aiosqlite
import os
from dotenv import load_dotenv


load_dotenv()

DB_PATH = os.getenv("DB_PATH")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                phone_number TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                status TEXT DEFAULT 'новая',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()


class Database:

    # ---------------- USERS ----------------
    @staticmethod
    async def add_user(user_id: int, first_name: str, last_name: str, phone_number: str):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO users (user_id, first_name, last_name, phone_number)
                VALUES (?, ?, ?, ?)
            """, (user_id, first_name, last_name, phone_number))
            await db.commit()

    @staticmethod
    async def is_registered(user_id: int) -> bool:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return row is not None

    # ---------------- REQUESTS ----------------
    @staticmethod
    async def add_request(user_id: int, text: str) -> int:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                INSERT INTO requests (user_id, text, status)
                VALUES (?, ?, ?)
            """, (user_id, text, "новая"))

            await db.commit()
            return cursor.lastrowid

    @staticmethod
    async def get_user_requests(user_id: int, hide_completed: bool = True):
        async with aiosqlite.connect(DB_PATH) as db:
            if hide_completed:
                cursor = await db.execute("""
                    SELECT id, text, status, created_at
                    FROM requests
                    WHERE user_id = ? AND status != 'отменена'
                    ORDER BY created_at DESC
                """, (user_id,))
            else:
                cursor = await db.execute("""
                    SELECT id, text, status, created_at
                    FROM requests
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                """, (user_id,))

            return await cursor.fetchall()

    @staticmethod
    async def get_all_requests(hide_completed: bool = False):
        async with aiosqlite.connect(DB_PATH) as db:
            if hide_completed:
                cursor = await db.execute("""
                    SELECT id, user_id, text, status, created_at
                    FROM requests
                    WHERE status != 'отменена'
                    ORDER BY created_at DESC
                """)
            else:
                cursor = await db.execute("""
                    SELECT id, user_id, text, status, created_at
                    FROM requests
                    ORDER BY created_at DESC
                """)

            return await cursor.fetchall()

    @staticmethod
    async def update_request_status(request_id: int, status: str):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE requests SET status=? WHERE id=?",
                (status, request_id)
            )
            await db.commit()

    @staticmethod
    async def delete_request(request_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM requests WHERE id=?",
                (request_id,)
            )
            await db.commit()
