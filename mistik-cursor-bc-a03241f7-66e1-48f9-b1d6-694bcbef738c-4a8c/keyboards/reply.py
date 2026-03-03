from __future__ import annotations

from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardRemove

from config import (
    BTN_ADD_ADMIN,
    BTN_ADMIN_PANEL,
    BTN_BACK_TO_MAIN,
    BTN_BAN_USER,
    BTN_MANAGE_USERS,
    BTN_STATISTICS,
    BTN_UNBAN_USER,
    BTN_VIEW_PENDING,
    BTN_BROWSE_SOLUTIONS,
    BTN_LEADERBOARD,
    BTN_PROFILE,
    BTN_SKIP,
    BTN_SUPPORT,
    BTN_UPLOAD_SOLUTION,
)


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_PROFILE)
    builder.button(text=BTN_LEADERBOARD)
    builder.button(text=BTN_UPLOAD_SOLUTION)
    builder.button(text=BTN_BROWSE_SOLUTIONS)
    builder.button(text=BTN_SUPPORT)
    if is_admin:
        builder.button(text=BTN_ADMIN_PANEL)
    builder.adjust(2, 2, 2) if is_admin else builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def admin_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_VIEW_PENDING)
    builder.button(text=BTN_ADD_ADMIN)
    builder.button(text=BTN_BAN_USER)
    builder.button(text=BTN_UNBAN_USER)
    builder.button(text=BTN_STATISTICS)
    builder.button(text=BTN_MANAGE_USERS)
    builder.button(text=BTN_BACK_TO_MAIN)
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def registration_avatar_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_SKIP)
    return builder.as_markup(resize_keyboard=True)


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove(remove_keyboard=True)
