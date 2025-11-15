from aiogram import BaseMiddleware
from aiogram import types
from database import Database


class RegistrationMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message):
            if event.text in ("/reg", "/start", "📝 Зарегистрироваться"):
                return await handler(event, data)
            if event.content_type == "contact":
                return await handler(event, data)

        return await handler(event, data)
