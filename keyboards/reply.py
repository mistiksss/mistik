from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="Профиль"), KeyboardButton(text="Лидерборд")],
        [KeyboardButton(text="Загрузить решение"), KeyboardButton(text="Смотреть решения")],
        [KeyboardButton(text="Поддержка")],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="Админ-панель")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def registration_avatar_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Пропустить")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить админа"), KeyboardButton(text="🚫 Забанить пользователя")],
            [KeyboardButton(text="↩️ В главное меню")],
        ],
        resize_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
