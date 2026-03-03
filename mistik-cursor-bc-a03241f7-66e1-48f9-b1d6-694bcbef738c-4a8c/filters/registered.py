from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from database import requests as db


class RegisteredUserFilter(BaseFilter):
    """Пропускает только зарегистрированных и не забаненных пользователей."""

    async def __call__(
        self,
        event: Message | CallbackQuery,
    ) -> bool | dict:
        if not event.from_user:
            return False
        user = await db.get_user_by_telegram_id(event.from_user.id)
        if user is None:
            if isinstance(event, Message):
                await event.answer("Сначала пройдите регистрацию: /start")
            else:
                await event.answer("Сначала пройдите регистрацию: /start", show_alert=True)
            return False
        if user.is_banned:
            if isinstance(event, Message):
                await event.answer("Ваш аккаунт заблокирован администратором.")
            else:
                await event.answer("Ваш аккаунт заблокирован.", show_alert=True)
            return False
        return {"user": user}
