import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from handlers import BotHandlers
from database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)
load_dotenv()

TG_API_KEY = os.getenv("TG_API_KEY")
URL = os.getenv("URL")

if not TG_API_KEY:
    raise SystemExit("Не найдены токены")

bot = Bot(TG_API_KEY)
dp = Dispatcher()
handlers = BotHandlers(url=URL)


# --- Запуск ---
async def main():
    dp.include_router(handlers.router)
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning(f"Ручная остановка")
