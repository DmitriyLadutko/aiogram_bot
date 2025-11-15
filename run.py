import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from database import Database
from handlers import BotHandlers

load_dotenv()
TOKEN = os.getenv("TG_API_KEY")
DB_PATH = os.getenv("DB_PATH") or "bot.db"
URL = os.getenv("URL")


async def main():
    if not TOKEN:
        raise RuntimeError("TG_API_KEY не задан в .env")
    bot = Bot(token=TOKEN)
    storage = MemoryStorage() # На всякий, dp его создает сам
    dp = Dispatcher(storage=storage)
    handlers = BotHandlers(url=URL)
    dp.include_router(handlers.router)
    await Database.init(DB_PATH)
    await Database.init_db()
    try:
        await dp.start_polling(bot)
    finally:
        await Database.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
