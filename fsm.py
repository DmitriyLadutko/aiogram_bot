from aiogram.fsm.state import State, StatesGroup


class UserRegistration(StatesGroup):
    number = State()


class RequestState(StatesGroup):
    entering_text = State()


class ReminderState(StatesGroup):
    choosing_time = State()
    entering_custom_time = State()
    entering_text = State()
