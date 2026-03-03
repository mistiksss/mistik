from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from database import requests as db


class AdminAccessMiddleware(BaseMiddleware):
    """Для admin-роутера: пропускает только пользователей из таблицы admins, не забаненных."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            user_id = event.from_user.id

        if user_id is None:
            return await handler(event, data)

        if not await db.is_admin(user_id):
            if isinstance(event, Message):
                await event.answer("Недостаточно прав.")
            else:
                await event.answer("Недостаточно прав.", show_alert=True)
            return None

        user = await db.get_user_by_telegram_id(user_id)
        if user and user.is_banned:
            if isinstance(event, Message):
                await event.answer("Ваш аккаунт заблокирован.")
            else:
                await event.answer("Ваш аккаунт заблокирован.", show_alert=True)
            return None

        return await handler(event, data)


class UserRequiredMiddleware(BaseMiddleware):
    """Для user-роутера: для /start и регистрации не требует user; для остальных ставит data['user'] или блокирует."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id

        if isinstance(event, Message) and event.text:
            text = event.text.strip()
            if text.startswith("/start") or text == "/cancel":
                return await handler(event, data)

        if await db.is_telegram_id_banned(user_id):
            if isinstance(event, Message):
                await event.answer("Ваш аккаунт заблокирован администратором.")
            else:
                await event.answer("Ваш аккаунт заблокирован.", show_alert=True)
            return None

        state = data.get("state")
        if state is not None:
            current = await state.get_state()
            if current and current.startswith("RegistrationState:"):
                return await handler(event, data)

        user = await db.get_user_by_telegram_id(user_id)
        if user is None:
            if isinstance(event, Message):
                await event.answer("Сначала пройдите регистрацию: /start")
            else:
                await event.answer("Сначала пройдите регистрацию: /start", show_alert=True)
            return None
        if user.is_banned:
            if isinstance(event, Message):
                await event.answer("Ваш аккаунт заблокирован администратором.")
            else:
                await event.answer("Ваш аккаунт заблокирован.", show_alert=True)
            return None

        data["user"] = user
        return await handler(event, data)
