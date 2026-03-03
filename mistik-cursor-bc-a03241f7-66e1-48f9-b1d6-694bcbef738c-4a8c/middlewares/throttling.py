from __future__ import annotations

import time
from collections import deque
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    """Ограничивает частоту запросов по user_id."""

    def __init__(self, rate_limit: int = 30, period_sec: float = 60.0) -> None:
        self.rate_limit = rate_limit
        self.period_sec = period_sec
        self._user_timestamps: dict[int, deque[float]] = {}

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

        now = time.monotonic()
        if user_id not in self._user_timestamps:
            self._user_timestamps[user_id] = deque(maxlen=self.rate_limit + 1)

        timestamps = self._user_timestamps[user_id]
        while timestamps and now - timestamps[0] > self.period_sec:
            timestamps.popleft()

        if len(timestamps) >= self.rate_limit:
            if isinstance(event, Message):
                await event.answer("Слишком частые запросы. Подождите минуту.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Слишком частые запросы.", show_alert=True)
            return None

        timestamps.append(now)
        return await handler(event, data)
