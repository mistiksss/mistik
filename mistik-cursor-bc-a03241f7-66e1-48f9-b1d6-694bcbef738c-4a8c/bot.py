from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from database import requests as db
from handlers.admin import router as admin_router
from handlers.user import router as user_router
from middlewares import AdminAccessMiddleware, ThrottlingMiddleware, UserRequiredMiddleware


async def on_startup(*_args, **_kwargs) -> None:
    await db.init_db()
    await db.ensure_initial_admin()
    logging.info("Database initialized and initial admin ensured")


async def main() -> None:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is empty. Set BOT_TOKEN in environment variables.")

    if settings.initial_admin_id <= 0:
        logging.warning("INITIAL_ADMIN_ID is not set or invalid. Admin features may be unavailable.")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.update.outer_middleware(ThrottlingMiddleware())
    admin_router.message.middleware(AdminAccessMiddleware())
    admin_router.callback_query.middleware(AdminAccessMiddleware())
    user_router.message.middleware(UserRequiredMiddleware())
    user_router.callback_query.middleware(UserRequiredMiddleware())

    dp.startup.register(on_startup)
    dp.include_router(admin_router)
    dp.include_router(user_router)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    asyncio.run(main())
