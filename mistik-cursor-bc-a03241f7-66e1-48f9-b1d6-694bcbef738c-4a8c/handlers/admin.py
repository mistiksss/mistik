from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from config import (
    BTN_ADD_ADMIN,
    BTN_ADMIN_PANEL,
    BTN_BACK_TO_MAIN,
    BTN_BAN_USER,
    BTN_MANAGE_USERS,
    BTN_SKIP,
    BTN_STATISTICS,
    BTN_UNBAN_USER,
    BTN_VIEW_PENDING,
)
from database import requests as db
from handlers.user import _is_gif_or_animation, _moderation_text, _send_solution_content
from keyboards.inline import (
    AdminManageUserCallback,
    AdminPendingSolutionCallback,
    ModerationCallback,
    admin_manage_user_keyboard,
    admin_pending_solutions_keyboard,
    moderation_keyboard,
)
from keyboards.reply import admin_menu, main_menu, registration_avatar_keyboard
from states import AdminState

router = Router(name="admin")


@router.message(Command("admin"))
@router.message(F.text == BTN_ADMIN_PANEL)
async def open_admin_panel(message: Message, state: FSMContext) -> None:
    await state.clear()
    pending = await db.get_pending_solutions_count()
    total_users = await db.get_total_users_count()
    await message.answer(
        f"Админ-панель\n\n"
        f"📊 Всего пользователей: {total_users}\n"
        f"⏳ Решений на модерации: {pending}\n\n"
        f"Выберите действие:",
        reply_markup=admin_menu(),
    )


@router.message(F.text == BTN_BACK_TO_MAIN)
async def back_to_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню.", reply_markup=main_menu(is_admin=True))


@router.message(F.text == BTN_ADD_ADMIN)
async def add_admin_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminState.waiting_new_admin_id)
    await message.answer("Отправьте Telegram ID пользователя, которого нужно назначить админом.")


@router.message(AdminState.waiting_new_admin_id, F.text)
async def add_admin_finish(message: Message, state: FSMContext) -> None:
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


@router.message(F.text == BTN_BAN_USER)
async def ban_user_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminState.waiting_ban_user_id)
    await message.answer("Отправьте Telegram ID пользователя для бана.")


@router.message(AdminState.waiting_ban_user_id, F.text)
async def ban_user_finish(message: Message, state: FSMContext) -> None:
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
    await message.answer(
        f"Пользователь <code>{target_id}</code> заблокирован.",
        reply_markup=admin_menu(),
    )


@router.message(AdminState.waiting_ban_user_id)
async def ban_user_fallback(message: Message) -> None:
    await message.answer("Введите Telegram ID текстом или «Отмена».")


@router.message(F.text == BTN_UNBAN_USER)
async def unban_user_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminState.waiting_unban_user_id)
    await message.answer("Отправьте Telegram ID пользователя для разбана.")


@router.message(AdminState.waiting_unban_user_id, F.text)
async def unban_user_finish(message: Message, state: FSMContext) -> None:
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

    success = await db.set_user_banned(target_id, banned=False)
    await state.clear()
    if success:
        await message.answer(
            f"Пользователь <code>{target_id}</code> разблокирован.",
            reply_markup=admin_menu(),
        )
    else:
        await message.answer(
            f"ID <code>{target_id}</code> не был забанен.",
            reply_markup=admin_menu(),
        )


@router.message(AdminState.waiting_unban_user_id)
async def unban_user_fallback(message: Message) -> None:
    await message.answer("Введите Telegram ID текстом или «Отмена».")


@router.message(F.text == BTN_VIEW_PENDING)
async def view_pending_solutions(message: Message, state: FSMContext) -> None:
    await state.clear()
    solutions = await db.get_pending_solutions(limit=50)
    if not solutions:
        await message.answer("Решений на модерации нет.", reply_markup=admin_menu())
        return

    await message.answer(
        f"Решений на модерации: {len(solutions)}\nВыберите решение:",
        reply_markup=admin_pending_solutions_keyboard(solutions),
    )


@router.callback_query(AdminPendingSolutionCallback.filter())
async def admin_open_pending_solution(
    callback: CallbackQuery,
    callback_data: AdminPendingSolutionCallback,
) -> None:
    solution = await db.get_solution_with_author(callback_data.solution_id)
    if solution is None:
        await callback.answer("Решение не найдено.", show_alert=True)
        return
    if solution.status != "pending":
        await callback.answer("Решение уже модерировано.", show_alert=True)
        return

    header = _moderation_text(solution)
    kb = moderation_keyboard(solution.id)
    await _send_solution_content(
        callback.bot,
        callback.message.chat.id,
        solution,
        header,
        kb,
    )
    await callback.answer()


@router.message(F.text == BTN_STATISTICS)
async def admin_statistics(message: Message, state: FSMContext) -> None:
    await state.clear()
    total_users = await db.get_total_users_count()
    pending = await db.get_pending_solutions_count()
    await message.answer(
        f"<b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"⏳ Решений на модерации: {pending}",
        reply_markup=admin_menu(),
    )


@router.message(F.text == BTN_MANAGE_USERS)
async def manage_users_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminState.waiting_manage_user_id)
    await message.answer("Введите Telegram ID пользователя для управления.")


@router.message(AdminState.waiting_manage_user_id, F.text)
async def manage_users_pick_user(message: Message, state: FSMContext) -> None:
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

    user = await db.get_user_by_telegram_id(target_id)
    if user is None:
        await message.answer("Пользователь не найден.")
        return

    avatar_status = "есть" if user.avatar_file_id else "нет"
    text = (
        f"<b>Пользователь</b>\n"
        f"ID: <code>{user.telegram_id}</code>\n"
        f"Ник: <b>{escape(user.nickname)}</b>\n"
        f"Аватар: {avatar_status}\n"
        f"Забанен: {'да' if user.is_banned else 'нет'}"
    )
    await state.update_data(manage_target_id=target_id)
    await state.set_state(AdminState.waiting_manage_user_id)  # keep state for callback
    await message.answer(text, reply_markup=admin_manage_user_keyboard(target_id))


@router.callback_query(AdminManageUserCallback.filter(F.action == "change_nickname"))
async def admin_change_nickname_start(
    callback: CallbackQuery,
    callback_data: AdminManageUserCallback,
    state: FSMContext,
) -> None:
    await state.set_state(AdminState.waiting_new_nickname)
    await state.update_data(manage_target_id=callback_data.telegram_id)
    await callback.message.answer(
        f"Введите новый ник для пользователя {callback_data.telegram_id} (4–24 символа, без пробелов)."
    )
    await callback.answer()


@router.message(AdminState.waiting_new_nickname, F.text)
async def admin_change_nickname_finish(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    target_id = data.get("manage_target_id")
    if not target_id:
        await state.clear()
        await message.answer("Сессия устарела.", reply_markup=admin_menu())
        return

    nickname = message.text.strip()
    if " " in nickname:
        await message.answer("Ник должен быть без пробелов.")
        return
    if not 4 <= len(nickname) <= 24:
        await message.answer("Длина ника: 4–24 символа.")
        return

    success = await db.update_user_nickname(target_id, nickname)
    await state.clear()
    if success:
        await message.answer(
            f"Ник пользователя <code>{target_id}</code> изменён на <b>{escape(nickname)}</b>.",
            reply_markup=admin_menu(),
        )
    else:
        await message.answer("Ошибка обновления.", reply_markup=admin_menu())


@router.callback_query(AdminManageUserCallback.filter(F.action == "remove_avatar"))
async def admin_remove_avatar(
    callback: CallbackQuery,
    callback_data: AdminManageUserCallback,
    state: FSMContext,
) -> None:
    await state.clear()
    success = await db.update_user_avatar(callback_data.telegram_id, None)
    if success:
        await callback.message.answer(
            f"Аватар пользователя <code>{callback_data.telegram_id}</code> удалён.",
            reply_markup=admin_menu(),
        )
    else:
        await callback.message.answer("Ошибка.", reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(AdminManageUserCallback.filter(F.action == "change_avatar"))
async def admin_change_avatar_start(
    callback: CallbackQuery,
    callback_data: AdminManageUserCallback,
    state: FSMContext,
) -> None:
    await state.set_state(AdminState.waiting_new_avatar_for_user)
    await state.update_data(manage_target_id=callback_data.telegram_id)
    await callback.message.answer(
        f"Отправьте новое фото для аватара пользователя {callback_data.telegram_id} (не GIF).",
        reply_markup=registration_avatar_keyboard(),
    )
    await callback.answer()


@router.message(AdminState.waiting_new_avatar_for_user)
async def admin_change_avatar_finish(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    target_id = data.get("manage_target_id")
    if not target_id:
        await state.clear()
        await message.answer("Сессия устарела.", reply_markup=admin_menu())
        return

    if _is_gif_or_animation(message):
        await message.answer("GIF не поддерживаются. Отправьте обычное фото.")
        return

    avatar_file_id = None
    if message.photo:
        avatar_file_id = message.photo[-1].file_id
    elif message.text and message.text.strip().lower() == BTN_SKIP.lower():
        avatar_file_id = None
    else:
        await message.answer("Отправьте фото или «Пропустить».")
        return

    success = await db.update_user_avatar(target_id, avatar_file_id)
    await state.clear()
    if success:
        await message.answer(
            f"Аватар пользователя <code>{target_id}</code> обновлён.",
            reply_markup=admin_menu(),
        )
    else:
        await message.answer("Ошибка.", reply_markup=admin_menu())


@router.message(AdminState.waiting_new_nickname)
async def admin_change_nickname_fallback(message: Message) -> None:
    await message.answer("Введите новый ник текстом.")


@router.message(AdminState.waiting_reject_reason)
async def reject_with_reason(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    solution_id = data.get("reject_solution_id")
    reason = (message.text or "").strip()

    if not solution_id:
        await state.clear()
        await message.answer("Сессия модерации устарела. Попробуйте ещё раз из панели.")
        return

    moderated = await db.set_solution_status(
        solution_id=solution_id,
        status="rejected",
        moderated_by_admin_id=message.from_user.id,
        moderation_note=reason or None,
    )
    await state.clear()

    if moderated is None:
        await message.answer("Не удалось обновить статус решения.")
        return

    await message.answer(f"❌ Отклонено решение #{moderated.id}.")

    note_part = f"\nПричина: {moderated.moderation_note}" if moderated.moderation_note else ""
    notice = (
        f"❌ Ваше решение #{moderated.id} отклонено.\n"
        f"Предмет: {moderated.subject}\n"
        f"Тип: {moderated.solution_type}"
        f"{note_part}"
    )
    try:
        await message.bot.send_message(moderated.author.telegram_id, notice)
    except TelegramBadRequest:
        pass


@router.callback_query(ModerationCallback.filter())
async def moderate_solution(
    callback: CallbackQuery,
    callback_data: ModerationCallback,
    state: FSMContext,
) -> None:
    solution = await db.get_solution_with_author(callback_data.solution_id)
    if solution is None:
        await callback.answer("Решение не найдено.", show_alert=True)
        return
    if solution.status != "pending":
        await callback.answer("Это решение уже модерировано.", show_alert=True)
        return

    if callback_data.action == "approve":
        moderated = await db.set_solution_status(
            solution_id=callback_data.solution_id,
            status="approved",
            moderated_by_admin_id=callback.from_user.id,
        )
        if moderated is None:
            await callback.answer("Не удалось обновить статус.", show_alert=True)
            return

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass

        decision_text = "✅ Одобрено"
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
        return

    if callback_data.action == "reject":
        await state.set_state(AdminState.waiting_reject_reason)
        await state.update_data(reject_solution_id=callback_data.solution_id)
        await callback.message.answer(
            f"Напишите причину отклонения для решения #{solution.id} (одним сообщением)."
        )
        await callback.answer()
