from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from database import requests as db
from keyboards.inline import ModerationCallback
from keyboards.reply import admin_menu, main_menu
from states import AdminState

router = Router(name="admin")


async def _ensure_admin_message(message: Message):
    if not await db.is_admin(message.from_user.id):
        return False
    user = await db.get_user_by_telegram_id(message.from_user.id)
    if user and user.is_banned:
        await message.answer("Ваш аккаунт заблокирован.")
        return False
    return True


async def _ensure_admin_callback(callback: CallbackQuery):
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return False
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if user and user.is_banned:
        await callback.answer("Ваш аккаунт заблокирован.", show_alert=True)
        return False
    return True


@router.message(Command("admin"))
@router.message(F.text == "Админ-панель")
async def open_admin_panel(message: Message, state: FSMContext) -> None:
    if not await _ensure_admin_message(message):
        return
    await state.clear()
    pending = await db.get_pending_solutions_count()
    await message.answer(
        f"Админ-панель\n\n"
        f"Решений на модерации: {pending}\n"
        f"Выберите действие:",
        reply_markup=admin_menu(),
    )


@router.message(F.text == "↩️ В главное меню")
async def back_to_main_menu(message: Message, state: FSMContext) -> None:
    if not await _ensure_admin_message(message):
        return
    await state.clear()
    await message.answer("Главное меню.", reply_markup=main_menu(is_admin=True))


@router.message(F.text == "➕ Добавить админа")
async def add_admin_start(message: Message, state: FSMContext) -> None:
    if not await _ensure_admin_message(message):
        return
    await state.set_state(AdminState.waiting_new_admin_id)
    await message.answer("Отправьте Telegram ID пользователя, которого нужно назначить админом.")


@router.message(AdminState.waiting_new_admin_id, F.text)
async def add_admin_finish(message: Message, state: FSMContext) -> None:
    if not await _ensure_admin_message(message):
        return

    raw = message.text.strip()
    if raw.lower() == "отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=admin_menu())
        return

    try:
        target_id = int(raw)
    except ValueError:
        await message.answer("Некорректный ID. Введите число или «Отмена».")
        return

    created = await db.add_admin(target_id, added_by=message.from_user.id)
    await state.clear()

    if created:
        await message.answer(
            f"Пользователь <code>{target_id}</code> добавлен в администраторы.",
            reply_markup=admin_menu(),
        )
    else:
        await message.answer(
            f"Пользователь <code>{target_id}</code> уже является администратором.",
            reply_markup=admin_menu(),
        )


@router.message(AdminState.waiting_new_admin_id)
async def add_admin_fallback(message: Message) -> None:
    await message.answer("Введите Telegram ID текстом или «Отмена».")


@router.message(F.text == "🚫 Забанить пользователя")
async def ban_user_start(message: Message, state: FSMContext) -> None:
    if not await _ensure_admin_message(message):
        return
    await state.set_state(AdminState.waiting_ban_user_id)
    await message.answer("Отправьте Telegram ID пользователя для бана.")


@router.message(AdminState.waiting_ban_user_id, F.text)
async def ban_user_finish(message: Message, state: FSMContext) -> None:
    if not await _ensure_admin_message(message):
        return

    raw = message.text.strip()
    if raw.lower() == "отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=admin_menu())
        return

    try:
        target_id = int(raw)
    except ValueError:
        await message.answer("Некорректный ID. Введите число или «Отмена».")
        return

    if target_id == settings.initial_admin_id:
        await message.answer("Нельзя забанить INITIAL_ADMIN_ID.")
        return

    success = await db.set_user_banned(target_id, banned=True)
    await state.clear()
    if success:
        await message.answer(
            f"Пользователь <code>{target_id}</code> заблокирован.",
            reply_markup=admin_menu(),
        )
    else:
        await message.answer(
            f"Пользователь <code>{target_id}</code> не найден в базе.",
            reply_markup=admin_menu(),
        )


@router.message(AdminState.waiting_ban_user_id)
async def ban_user_fallback(message: Message) -> None:
    await message.answer("Введите Telegram ID текстом или «Отмена».")


@router.callback_query(ModerationCallback.filter())
async def moderate_solution(
    callback: CallbackQuery,
    callback_data: ModerationCallback,
) -> None:
    if not await _ensure_admin_callback(callback):
        return

    solution = await db.get_solution_with_author(callback_data.solution_id)
    if solution is None:
        await callback.answer("Решение не найдено.", show_alert=True)
        return
    if solution.status != "pending":
        await callback.answer("Это решение уже модерировано.", show_alert=True)
        return

    status = "approved" if callback_data.action == "approve" else "rejected"
    moderated = await db.set_solution_status(
        solution_id=callback_data.solution_id,
        status=status,
        moderated_by_admin_id=callback.from_user.id,
    )
    if moderated is None:
        await callback.answer("Не удалось обновить статус.", show_alert=True)
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    decision_text = "✅ Одобрено" if status == "approved" else "❌ Отклонено"
    await callback.message.answer(f"{decision_text} решение #{moderated.id}.")
    await callback.answer("Готово")

    notice = (
        f"{decision_text}\n"
        f"Ваше решение #{moderated.id}\n"
        f"Предмет: {moderated.subject}\n"
        f"Тип: {moderated.solution_type}"
    )
    try:
        await callback.bot.send_message(moderated.author.telegram_id, notice)
    except TelegramBadRequest:
        pass
