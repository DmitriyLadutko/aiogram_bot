import aiohttp
import asyncio

from aiogram import F, types, Router, Bot, exceptions
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import datetime
from zoneinfo import ZoneInfo
from database import Database
from midleware import RegistrationMiddleware
from fsm import UserRegistration, RequestState, ReminderState

class BotHandlers:
    ADMINS = [7678570149]
    REQUESTS_PER_PAGE = 3

    def __init__(self, url: str):
        self.url = url
        self.router = Router()

        # Команды без регистрации
        self.router.message.register(self.start_cmd, CommandStart())
        self.router.message.register(self.user_registration_start, F.text == "📝 Зарегистрироваться")
        self.router.message.register(self.receive_contact, F.content_type == "contact")

        # Главное меню кнопки
        self.router.message.register(self.about_cmd, F.text == "О боте")
        self.router.message.register(self.handle_time, F.text == "⏱ Время")
        self.router.message.register(self.ask_city_for_currency, F.text == "Курс валют")
        self.router.message.register(self.handle_remind, F.text == "🔔 Напоминание")
        self.router.message.register(self.handle_location, F.content_type == "location")

        # Callback-и
        self.router.callback_query.register(self.handle_city_selected, F.data.startswith("city:"))
        self.router.callback_query.register(self.choose_ready_time, F.data.startswith("rem_time"))
        self.router.callback_query.register(self.choose_custom_interval, F.data == "rem_custom")
        self.router.callback_query.register(self.handle_page_callback, F.data.startswith("page:"))

        # FSM Handlers
        self.router.message.register(self.save_custom_interval, ReminderState.entering_custom_time)
        self.router.message.register(self.save_reminder_text, ReminderState.entering_text)

        # Middleware
        self.router.message.middleware.register(RegistrationMiddleware())

        # Заявки
        self.router.message.register(self.create_request_start, F.text == "➕ Создать заявку")
        self.router.message.register(self.save_request, RequestState.entering_text)
        self.router.message.register(self.show_user_requests, F.text == "📄 Мои заявки")
        self.router.callback_query.register(self.cancel_request, F.data.startswith("cancel:"))

        # Админка
        self.router.message.register(self.show_all_requests, F.text == "📋 Все заявки")
        self.router.callback_query.register(self.change_status, F.data.startswith("status:"))

    # --------------------
    # START / REGISTRATION
    # --------------------
    async def main_menu(self, user_id: int):
        keyboard = [
            [KeyboardButton(text="Курс валют"), KeyboardButton(text="⏱ Время")],
            [KeyboardButton(text="🔔 Напоминание"), KeyboardButton(text="📍 Отправить локацию", request_location=True)],
            [KeyboardButton(text="➕ Создать заявку"), KeyboardButton(text="📄 Мои заявки")]
        ]
        if user_id in BotHandlers.ADMINS:
            keyboard.append([KeyboardButton(text="📋 Все заявки")])
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    async def start_cmd(self, message: types.Message):
        if await Database.is_registered(message.from_user.id):
            await message.answer(
                text="👋 С возвращением!",
                reply_markup=await self.main_menu(message.from_user.id)
            )
        else:
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="📝 Зарегистрироваться", request_contact=False)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await message.answer(
                f"👋 Привет, {message.from_user.first_name}!\nНажми кнопку для регистрации",
                reply_markup=keyboard
            )

    async def user_registration_start(self, message: types.Message, state: FSMContext):
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Отправить контакт", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer("Для регистрации отправь контакт 📲", reply_markup=keyboard)
        await state.set_state(UserRegistration.number)

    async def receive_contact(self, message: types.Message, state: FSMContext):
        if not message.contact:
            await message.answer("Используй кнопку для отправки контакта.")
            return

        contact = message.contact
        await Database.add_user(
            user_id=message.from_user.id,
            first_name=contact.first_name,
            last_name=contact.last_name or "",
            phone_number=contact.phone_number
        )
        await message.answer(
            f"✅ Ты зарегистрирован как {contact.first_name} {contact.last_name or ''} {contact.phone_number}",
            reply_markup=await self.main_menu(message.from_user.id)
        )
        await state.clear()

    # --------------------
    # MENU HANDLERS
    # --------------------

    async def about_cmd(self, message: types.Message):
        await message.answer("🤖 Я крутой бот!")

    async def handle_time(self, message: types.Message):
        now = datetime.now(ZoneInfo("Europe/Minsk"))
        await message.answer(f"⏰ Сейчас в Минске: {now.strftime('%H:%M:%S')}")

    async def ask_city_for_currency(self, message: types.Message):
        kb = InlineKeyboardBuilder()
        cities = ["Минск", "Брест", "Гродно", "Гомель", "Витебск", "Могилев"]
        for city in cities:
            kb.button(text=city, callback_data=f"city:{city}")
        kb.adjust(2)
        await message.answer("Выбери город:", reply_markup=kb.as_markup())

    async def handle_city_selected(self, callback: types.CallbackQuery):
        city = callback.data.split(":")[1]
        await callback.answer(f"Получаю данные для {city}…", show_alert=True)
        await self.send_currency(callback.message, city)

    async def send_currency(self, message: types.Message, city: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url, params={"city": city}) as resp:
                data = await resp.json()
        if not data:
            await message.answer("❌ Не удалось получить данные.")
            return
        branch = data[0]
        usd_in = float(branch["USD_in"])
        usd_out = float(branch["USD_out"])
        rub_in = float(branch["RUB_in"]) / 100
        rub_out = float(branch["RUB_out"]) / 100
        cny_in = float(branch["CNY_in"]) / 10
        cny_out = float(branch["CNY_out"]) / 10
        await message.answer(
            f"*Курс валют в {city}:*\n"
            f"💵 USD: {usd_in:.4f}/{usd_out:.4f}\n"
            f"🇷🇺 RUB: {rub_in:.4f}/{rub_out:.4f}\n"
            f"🇨🇳 CNY: {cny_in:.4f}/{cny_out:.4f}",
            parse_mode="Markdown"
        )

    # --------------------
    # REMINDER
    # --------------------
    async def handle_remind(self, message: types.Message, state: FSMContext):
        kb = InlineKeyboardBuilder()
        for m in [1, 5, 10, 30]:
            kb.button(text=f"{m} мин", callback_data=f"rem_time:{m}")
        kb.button(text="Свой интервал ⌨️", callback_data="rem_custom")
        kb.adjust(2)
        await message.answer("⏱ Выбери интервал или введи свой:", reply_markup=kb.as_markup())
        await state.set_state(ReminderState.choosing_time)

    async def choose_ready_time(self, callback: types.CallbackQuery, state: FSMContext):
        minutes = int(callback.data.split(":")[1])
        await state.update_data(minutes=minutes)
        await callback.message.edit_text("📝 Теперь введи текст напоминания:")
        await state.set_state(ReminderState.entering_text)

    async def choose_custom_interval(self, callback: types.CallbackQuery, state: FSMContext):
        await callback.message.edit_text("⌨️ Введи количество минут вручную")
        await state.set_state(ReminderState.entering_custom_time)

    async def save_custom_interval(self, message: types.Message, state: FSMContext):
        try:
            minutes = int(message.text)
            if minutes <= 0:
                raise ValueError
        except ValueError:
            await message.answer("❗ Введи число минут")
            return
        await state.update_data(minutes=minutes)
        await message.answer("📝 Теперь введи текст напоминания:")
        await state.set_state(ReminderState.entering_text)

    async def save_reminder_text(self, message: types.Message, state: FSMContext):
        text = message.text
        data = await state.get_data()
        minutes = data["minutes"]
        await message.answer(f"🔔 Ок! Напомню через {minutes} минут.")
        asyncio.create_task(self.send_reminder(message.bot, message.chat.id, minutes, text))
        await state.clear()

    async def send_reminder(self, bot: Bot, chat_id: int, minutes: int, text: str):
        await asyncio.sleep(minutes * 60)
        await bot.send_message(chat_id, f"⏰ Напоминание: {text}")

    async def handle_location(self, message: types.Message):
        if not message.location:
            await message.answer("Пожалуйста, отправь свою локацию через кнопку 📍")
            return
        latitude = message.location.latitude
        longitude = message.location.longitude

        await message.answer_location(latitude=latitude, longitude=longitude)
        await message.answer(f"Вот твоя локация:\nШирота: {latitude}\nДолгота: {longitude}")

    async def create_request_start(self, message: types.Message, state: FSMContext):
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Отменить")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer("📝 Введи текст заявки:", reply_markup=kb)
        await state.set_state(RequestState.entering_text)

    async def save_request(self, message: types.Message, state: FSMContext):
        if message.text.lower() == "отменить":
            await message.answer("❌ Заявка отменена", reply_markup=await self.main_menu(message.from_user.id))
            await state.clear()
            return

        request_id = await Database.add_request(user_id=message.from_user.id, text=message.text)

        await message.answer("✅ Заявка принята!", reply_markup=await self.main_menu(message.from_user.id))
        await state.clear()

        for admin_id in BotHandlers.ADMINS:
            try:
                kb = InlineKeyboardBuilder()
                kb.button(text="✅ В работе", callback_data=f"status:{request_id}:в работе")
                kb.button(text="✅ Выполнено", callback_data=f"status:{request_id}:выполнена")
                kb.button(text="❌ Отменить", callback_data=f"status:{request_id}:отменена")
                kb.adjust(3)

                await message.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"📢 Новая заявка от {message.from_user.full_name}:\n\n"
                        f"{message.text}\n\n"
                        f"ID заявки: {request_id}"
                    ),
                    parse_mode="Markdown",
                    reply_markup=kb.as_markup()
                )
            except Exception as e:
                print(f"Не удалось отправить уведомление админу {admin_id}: {e}")

    def build_requests_keyboard(self, requests, page=0, is_admin=False):
        kb = InlineKeyboardBuilder()
        start = page * BotHandlers.REQUESTS_PER_PAGE
        end = start + BotHandlers.REQUESTS_PER_PAGE
        for r in requests[start:end]:
            if is_admin:
                kb.button(text="✅ В работе", callback_data=f"status:{r[0]}:в работе")
                kb.button(text="✅ Выполнено", callback_data=f"status:{r[0]}:выполнена")
                kb.button(text="❌ Отменить", callback_data=f"status:{r[0]}:отменена")
            else:
                kb.button(text="❌ Отменить", callback_data=f"cancel:{r[0]}")
        kb.adjust(3 if is_admin else 1)

        # Навигация страниц
        total_pages = (len(requests) - 1) // BotHandlers.REQUESTS_PER_PAGE
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"page:{page - 1}:{'admin' if is_admin else 'user'}")
            )
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(
                text="➡️ Вперед",
                callback_data=f"page:{page + 1}:{'admin' if is_admin else 'user'}")
            )
        if nav_buttons:
            kb.row(*nav_buttons)

        return kb.as_markup()

    async def show_user_requests(self, message: types.Message, page: int = 0, user_id: int = None):
        user_id = user_id or message.from_user.id
        requests = await Database.get_user_requests(user_id, hide_completed=True)
        if not requests:
            await message.answer("У тебя нет заявок")
            return

        start = page * BotHandlers.REQUESTS_PER_PAGE
        end = start + BotHandlers.REQUESTS_PER_PAGE
        requests_page = requests[start:end]

        for r in requests_page:
            kb = InlineKeyboardBuilder()
            kb.button(text="❌ Отменить", callback_data=f"cancel:{r[0]}")
            kb.adjust(3)
            status = r[2]

            if status.lower() == "новая":
                status_display = "🔵 Новая"
            elif status.lower() == "в работе":
                status_display = "🟡 В работе"
            elif status.lower() == "выполнена":
                status_display = "🟢 Выполнена"
            else:
                status_display = status

            await message.answer(
                f"ID: {r[0]}\nТекст: {r[1]}\nСтатус: *{status_display}*",
                parse_mode="Markdown",
                reply_markup=kb.as_markup()
            )

        total_pages = (len(requests) - 1) // BotHandlers.REQUESTS_PER_PAGE
        if total_pages > 0:
            nav_kb = InlineKeyboardBuilder()
            if page > 0:
                nav_kb.button(text="⬅️ Назад", callback_data=f"page:{page - 1}:user")
            if page < total_pages:
                nav_kb.button(text="➡️ Вперед", callback_data=f"page:{page + 1}:user")
            nav_kb.adjust(2)
            await message.answer("Страницы:", reply_markup=nav_kb.as_markup())

    async def show_all_requests(self, message: types.Message, page: int = 0, user_id: int = None):
        user_id = user_id or message.from_user.id
        if user_id not in BotHandlers.ADMINS:
            await message.answer("❌ Доступ запрещен")
            return
        requests = await Database.get_all_requests(hide_completed=True)
        if not requests:
            await message.answer("Заявок нет")
            return

        start = page *BotHandlers. REQUESTS_PER_PAGE
        end = start + BotHandlers.REQUESTS_PER_PAGE
        requests_page = requests[start:end]

        for r in requests_page:
            kb = InlineKeyboardBuilder()
            kb.button(text="✅ В работе", callback_data=f"status:{r[0]}:в работе")
            kb.button(text="✅ Выполнено", callback_data=f"status:{r[0]}:выполнена")
            kb.button(text="❌ Отменить", callback_data=f"status:{r[0]}:отменена")
            kb.adjust(3)
            await message.answer(f"ID: {r[0]}\nПользователь: {r[1]}\nТекст: {r[2]}\nСтатус: {r[3]}",
                                 reply_markup=kb.as_markup())

        total_pages = (len(requests) - 1) // BotHandlers.REQUESTS_PER_PAGE
        if total_pages > 0:
            nav_kb = InlineKeyboardBuilder()
            if page > 0:
                nav_kb.button(text="⬅️ Назад", callback_data=f"page:{page - 1}:admin")
            if page < total_pages:
                nav_kb.button(text="➡️ Вперед", callback_data=f"page:{page + 1}:admin")
            nav_kb.adjust(2)
            await message.answer("Страницы:", reply_markup=nav_kb.as_markup())

    async def handle_page_callback(self, callback: types.CallbackQuery):
        data = callback.data.split(":")
        page = int(data[1])
        is_admin = data[2] == "admin"

        if is_admin:
            await self.show_all_requests(callback.message, page, user_id=callback.from_user.id)
        else:
            await self.show_user_requests(callback.message, page, user_id=callback.from_user.id)
        await callback.answer()

    async def cancel_request(self, callback: types.CallbackQuery):
        await callback.answer()
        parts = callback.data.split(sep=":", maxsplit=1)
        if len(parts) < 2:
            return
        try:
            request_id = int(parts[1])
        except ValueError:
            await callback.answer("Неверный id заявки", show_alert=False)
            return
        try:
            deleted = await Database.delete_request(request_id)
        except Exception:
            await callback.answer("Ошибка при работе с БД", show_alert=False)
            return
        if deleted:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except exceptions.TelegramBadRequest:
                pass
        else:
            await callback.answer("Заявка не найдена или уже удалена", show_alert=False)

    async def change_status(self, callback: types.CallbackQuery):
        await callback.answer()
        parts = callback.data.split(sep=":", maxsplit=2)
        if len(parts) < 3:
            return
        try:
            request_id = int(parts[1])
        except ValueError:
            await callback.answer("Неверный id заявки", show_alert=False)
            return
        status = parts[2]
        try:
            updated = await Database.update_request_status(request_id, status)
        except Exception:
            await callback.answer("Ошибка при работе с БД", show_alert=False)
            return
        if updated:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except exceptions.TelegramBadRequest:
                pass
        else:
            await callback.answer("Заявка не найдена", show_alert=False)
