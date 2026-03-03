from __future__ import annotations

from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import SOLUTION_TYPES, settings
from database import requests as db
from keyboards.inline import (
    BrowseActionCallback,
    BrowseSubjectCallback,
    BrowseTypeCallback,
    ProfileActionCallback,
    SelfAssessmentCallback,
    SolutionRateCallback,
    UploadSubjectCallback,
    UploadTypeCallback,
    UserProfileCallback,
    browse_subject_keyboard,
    browse_type_keyboard,
    leaderboard_keyboard,
    moderation_keyboard,
    profile_actions_keyboard,
    self_assessment_keyboard,
    solution_review_keyboard,
    upload_subject_keyboard,
    upload_type_keyboard,
)
from keyboards.reply import (
    main_menu,
    registration_avatar_keyboard,
    remove_keyboard,
)
from states import BrowseSolutionsState, RegistrationState, UploadSolutionState

router = Router(name="user")


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _pluralize_ru(number: int, form_one: str, form_few: str, form_many: str) -> str:
    last_two = abs(number) % 100
    last_one = last_two % 10
    if 11 <= last_two <= 14:
        return form_many
    if last_one == 1:
        return form_one
    if 2 <= last_one <= 4:
        return form_few
    return form_many


async def _ensure_registered_message(message: Message):
    user = await db.get_user_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer("Сначала пройдите регистрацию: /start")
        return None
    if user.is_banned:
        await message.answer("Ваш аккаунт заблокирован администратором.")
        return None
    return user


async def _ensure_registered_callback(callback: CallbackQuery):
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer("Сначала пройдите регистрацию: /start", show_alert=True)
        return None
    if user.is_banned:
        await callback.answer("Ваш аккаунт заблокирован.", show_alert=True)
        return None
    return user


def _profile_text(user, rank: int | None) -> str:
    rank_text = f"#{rank}" if rank else "—"
    return (
        "<b>Профиль</b>\n"
        f"Ник: <b>{escape(user.nickname)}</b>\n"
        f"Рейтинг: ⭐ {user.rating_points}\n"
        f"Место в топе: {rank_text}\n"
        f"Решений: {user.total_solutions_count}\n"
        f"Одобрено: {user.approved_solutions_count}"
    )


async def _send_profile(chat_target: Message | CallbackQuery, target_user, with_actions: bool) -> None:
    rank = await db.get_user_rank(target_user.telegram_id)
    text = _profile_text(target_user, rank)
    keyboard = profile_actions_keyboard() if with_actions else None

    if isinstance(chat_target, CallbackQuery):
        send_text = chat_target.message.answer
        send_photo = chat_target.message.answer_photo
    else:
        send_text = chat_target.answer
        send_photo = chat_target.answer_photo

    if target_user.avatar_file_id:
        try:
            await send_photo(
                photo=target_user.avatar_file_id,
                caption=text,
                reply_markup=keyboard,
            )
            return
        except TelegramBadRequest:
            pass

    await send_text(text, reply_markup=keyboard)


def _solution_card_text(solution) -> str:
    description = escape(solution.description or "Без описания")
    return (
        "<b>Решение</b>\n"
        f"ID: <code>{solution.id}</code>\n"
        f"Автор: <b>{escape(solution.author.nickname)}</b>\n"
        f"Тип: {escape(solution.solution_type)}\n"
        f"Предмет: {escape(solution.subject)}\n"
        f"Оценка автора: {solution.self_assessment or '—'}⭐\n"
        f"Средняя оценка: {solution.average_rating}⭐\n"
        f"Описание: {description}"
    )


async def _send_solution_for_review(bot: Bot, chat_id: int, solution_id: int) -> None:
    solution = await db.get_solution_with_author(solution_id)
    if solution is None:
        await bot.send_message(chat_id, "Решение не найдено.")
        return

    caption = _solution_card_text(solution)
    keyboard = solution_review_keyboard(solution.id, solution.author.telegram_id)

    if solution.content_type == "photo":
        await bot.send_photo(
            chat_id=chat_id,
            photo=solution.content_value,
            caption=_truncate(caption, 1024),
            reply_markup=keyboard,
        )
        return

    if solution.content_type == "document":
        await bot.send_document(
            chat_id=chat_id,
            document=solution.content_value,
            caption=_truncate(caption, 1024),
            reply_markup=keyboard,
        )
        return

    content_text = (
        f"{caption}\n\n"
        f"<b>Текст решения:</b>\n{escape(solution.content_value)}"
    )
    await bot.send_message(
        chat_id=chat_id,
        text=_truncate(content_text, 4096),
        reply_markup=keyboard,
    )


def _moderation_text(solution) -> str:
    description = escape(solution.description or "Без описания")
    return (
        "<b>Новое решение на модерацию</b>\n"
        f"ID: <code>{solution.id}</code>\n"
        f"Автор: <b>{escape(solution.author.nickname)}</b> "
        f"(<code>{solution.author.telegram_id}</code>)\n"
        f"Тип: {escape(solution.solution_type)}\n"
        f"Предмет: {escape(solution.subject)}\n"
        f"Оценка автора: {solution.self_assessment or '—'}⭐\n"
        f"Описание: {description}"
    )


async def _send_solution_to_admins(bot: Bot, solution_id: int) -> None:
    solution = await db.get_solution_with_author(solution_id)
    if solution is None:
        return

    admin_ids = await db.get_admin_ids()
    if not admin_ids:
        return

    header = _moderation_text(solution)
    keyboard = moderation_keyboard(solution.id)

    for admin_id in admin_ids:
        try:
            if solution.content_type == "photo":
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=solution.content_value,
                    caption=_truncate(header, 1024),
                    reply_markup=keyboard,
                )
            elif solution.content_type == "document":
                await bot.send_document(
                    chat_id=admin_id,
                    document=solution.content_value,
                    caption=_truncate(header, 1024),
                    reply_markup=keyboard,
                )
            else:
                payload = (
                    f"{header}\n\n"
                    f"<b>Текст решения:</b>\n{escape(solution.content_value)}"
                )
                await bot.send_message(
                    chat_id=admin_id,
                    text=_truncate(payload, 4096),
                    reply_markup=keyboard,
                )
        except TelegramBadRequest:
            continue


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user_by_telegram_id(message.from_user.id)
    if user and user.is_banned:
        await message.answer("Ваш аккаунт заблокирован администратором.")
        return

    if user:
        await message.answer(
            "С возвращением! Открываю главное меню.",
            reply_markup=main_menu(is_admin=await db.is_admin(message.from_user.id)),
        )
        return

    await state.set_state(RegistrationState.waiting_nickname)
    await message.answer(
        "Привет! Давай зарегистрируемся.\n"
        "Отправь ник (одно слово, 3-24 символа).",
        reply_markup=remove_keyboard(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer("Действие отменено. Для регистрации отправьте /start")
        return
    await message.answer(
        "Текущее действие отменено.",
        reply_markup=main_menu(is_admin=await db.is_admin(message.from_user.id)),
    )


@router.message(RegistrationState.waiting_nickname, F.text)
async def registration_nickname(message: Message, state: FSMContext) -> None:
    nickname = message.text.strip()
    if " " in nickname:
        await message.answer("Ник должен быть одним словом без пробелов.")
        return
    if not 3 <= len(nickname) <= 24:
        await message.answer("Длина ника должна быть от 3 до 24 символов.")
        return

    await state.update_data(nickname=nickname)
    await state.set_state(RegistrationState.waiting_avatar)
    await message.answer(
        "Отправьте аватарку (фото) или нажмите «Пропустить».",
        reply_markup=registration_avatar_keyboard(),
    )


@router.message(RegistrationState.waiting_nickname)
async def registration_nickname_fallback(message: Message) -> None:
    await message.answer("Отправьте ник обычным текстом.")


@router.message(RegistrationState.waiting_avatar)
async def registration_avatar(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    nickname = data.get("nickname")
    if not nickname:
        await state.clear()
        await message.answer("Сессия регистрации устарела. Начните заново: /start")
        return

    avatar_file_id = None
    if message.photo:
        avatar_file_id = message.photo[-1].file_id
    elif message.text and message.text.strip().lower() == "пропустить":
        avatar_file_id = None
    else:
        await message.answer("Отправьте фото или нажмите кнопку «Пропустить».")
        return

    await db.register_user(
        telegram_id=message.from_user.id,
        nickname=nickname,
        avatar_file_id=avatar_file_id,
    )
    await state.clear()
    await message.answer(
        "Регистрация завершена ✅",
        reply_markup=main_menu(is_admin=await db.is_admin(message.from_user.id)),
    )


@router.message(F.text == "Профиль")
async def menu_profile(message: Message) -> None:
    user = await _ensure_registered_message(message)
    if user is None:
        return
    await _send_profile(message, user, with_actions=True)


@router.callback_query(ProfileActionCallback.filter(F.action == "my_solutions"))
async def profile_my_solutions(callback: CallbackQuery) -> None:
    user = await _ensure_registered_callback(callback)
    if user is None:
        return

    solutions = await db.list_user_solutions(user.telegram_id, limit=30)
    if not solutions:
        await callback.answer("У вас пока нет загруженных решений.", show_alert=True)
        return

    lines = ["<b>Мои решения:</b>"]
    for solution in solutions:
        lines.append(
            f"#{solution.id} | {escape(solution.subject)} | {escape(solution.solution_type)} | "
            f"{db.solution_status_label(solution.status)}"
        )

    await callback.message.answer(_truncate("\n".join(lines), 4096))
    await callback.answer()


@router.message(F.text == "Лидерборд")
async def menu_leaderboard(message: Message) -> None:
    user = await _ensure_registered_message(message)
    if user is None:
        return

    top_users = await db.get_top_users(limit=10)
    if not top_users:
        await message.answer("Лидерборд пока пуст.")
        return

    lines = ["<b>ТОП-10 по одобренным решениям:</b>"]
    for index, top_user in enumerate(top_users, start=1):
        approved_count = top_user.approved_solutions_count
        solutions_word = _pluralize_ru(approved_count, "решение", "решения", "решений")
        lines.append(
            f"{index}. {escape(top_user.nickname)} — "
            f"{approved_count} {solutions_word} | ⭐ {top_user.rating_points}"
        )

    await message.answer(
        "\n".join(lines),
        reply_markup=leaderboard_keyboard(top_users),
    )


@router.callback_query(UserProfileCallback.filter())
async def open_public_profile(
    callback: CallbackQuery, callback_data: UserProfileCallback
) -> None:
    viewer = await _ensure_registered_callback(callback)
    if viewer is None:
        return

    target_user = await db.get_user_by_telegram_id(callback_data.telegram_id)
    if target_user is None:
        await callback.answer("Профиль не найден.", show_alert=True)
        return

    await _send_profile(callback, target_user, with_actions=False)
    await callback.answer()


@router.message(F.text == "Загрузить решение")
async def menu_upload_solution(message: Message, state: FSMContext) -> None:
    user = await _ensure_registered_message(message)
    if user is None:
        return

    await state.clear()
    await state.set_state(UploadSolutionState.waiting_type)
    await message.answer(
        "Выберите тип решения:",
        reply_markup=upload_type_keyboard(),
    )


@router.callback_query(UploadSolutionState.waiting_type, UploadTypeCallback.filter())
async def upload_pick_type(
    callback: CallbackQuery,
    callback_data: UploadTypeCallback,
    state: FSMContext,
) -> None:
    user = await _ensure_registered_callback(callback)
    if user is None:
        return

    selected = SOLUTION_TYPES.get(callback_data.type_key)
    if not selected:
        await callback.answer("Неизвестный тип.", show_alert=True)
        return

    await state.update_data(solution_type=selected)
    await state.set_state(UploadSolutionState.waiting_subject)
    await callback.message.answer("Выберите предмет:", reply_markup=upload_subject_keyboard())
    await callback.answer()


@router.callback_query(UploadSolutionState.waiting_subject, UploadSubjectCallback.filter())
async def upload_pick_subject(
    callback: CallbackQuery,
    callback_data: UploadSubjectCallback,
    state: FSMContext,
) -> None:
    user = await _ensure_registered_callback(callback)
    if user is None:
        return

    await state.update_data(subject=callback_data.subject)
    await state.set_state(UploadSolutionState.waiting_content)
    await callback.message.answer(
        "Отправьте решение: текст, фото или файл (document)."
    )
    await callback.answer()


@router.message(UploadSolutionState.waiting_content)
async def upload_content(message: Message, state: FSMContext) -> None:
    user = await _ensure_registered_message(message)
    if user is None:
        return

    content_type: str | None = None
    content_value: str | None = None

    if message.photo:
        content_type = "photo"
        content_value = message.photo[-1].file_id
    elif message.document:
        content_type = "document"
        content_value = message.document.file_id
    elif message.text:
        content_type = "text"
        content_value = message.text.strip()
        if not content_value:
            await message.answer("Текст решения пуст. Отправьте корректный текст.")
            return

    if content_type is None or content_value is None:
        await message.answer("Поддерживаются только текст, фото или файл (document).")
        return

    await state.update_data(content_type=content_type, content_value=content_value)
    await state.set_state(UploadSolutionState.waiting_description)
    await message.answer("Добавьте краткое описание решения.")


@router.message(UploadSolutionState.waiting_description, F.text)
async def upload_description(message: Message, state: FSMContext) -> None:
    user = await _ensure_registered_message(message)
    if user is None:
        return

    description = message.text.strip()
    if len(description) < 3:
        await message.answer("Описание слишком короткое. Напишите минимум 3 символа.")
        return

    await state.update_data(description=_truncate(description, 1500))
    await state.set_state(UploadSolutionState.waiting_assessment)
    await message.answer(
        "Оцените ваше решение (1-5 ⭐):",
        reply_markup=self_assessment_keyboard(),
    )


@router.message(UploadSolutionState.waiting_description)
async def upload_description_fallback(message: Message) -> None:
    await message.answer("Описание должно быть текстом.")


@router.callback_query(
    UploadSolutionState.waiting_assessment, SelfAssessmentCallback.filter()
)
async def upload_finish(
    callback: CallbackQuery,
    callback_data: SelfAssessmentCallback,
    state: FSMContext,
) -> None:
    user = await _ensure_registered_callback(callback)
    if user is None:
        return

    form = await state.get_data()
    required_keys = ("solution_type", "subject", "content_type", "content_value", "description")
    if not all(key in form for key in required_keys):
        await state.clear()
        await callback.answer("Сессия загрузки устарела. Начните заново.", show_alert=True)
        return

    solution = await db.create_solution(
        author_telegram_id=callback.from_user.id,
        solution_type=form["solution_type"],
        subject=form["subject"],
        content_type=form["content_type"],
        content_value=form["content_value"],
        description=form["description"],
        self_assessment=callback_data.stars,
    )
    await state.clear()

    await callback.message.answer(
        f"Решение #{solution.id} отправлено на модерацию ✅",
        reply_markup=main_menu(is_admin=await db.is_admin(callback.from_user.id)),
    )
    await callback.answer("Отправлено")
    await _send_solution_to_admins(callback.bot, solution.id)


@router.message(F.text == "Смотреть решения")
async def menu_browse_solutions(message: Message, state: FSMContext) -> None:
    user = await _ensure_registered_message(message)
    if user is None:
        return

    await state.clear()
    await state.set_state(BrowseSolutionsState.waiting_type)
    await message.answer("Выберите тип решений:", reply_markup=browse_type_keyboard())


@router.callback_query(BrowseSolutionsState.waiting_type, BrowseTypeCallback.filter())
async def browse_pick_type(
    callback: CallbackQuery,
    callback_data: BrowseTypeCallback,
    state: FSMContext,
) -> None:
    user = await _ensure_registered_callback(callback)
    if user is None:
        return

    selected_type = None
    if callback_data.type_key != "any":
        selected_type = SOLUTION_TYPES.get(callback_data.type_key)
        if selected_type is None:
            await callback.answer("Неизвестный тип.", show_alert=True)
            return

    await state.update_data(filter_type=selected_type)
    await state.set_state(BrowseSolutionsState.waiting_subject)
    await callback.message.answer("Выберите предмет:", reply_markup=browse_subject_keyboard())
    await callback.answer()


@router.callback_query(BrowseSolutionsState.waiting_subject, BrowseSubjectCallback.filter())
async def browse_pick_subject(
    callback: CallbackQuery,
    callback_data: BrowseSubjectCallback,
    state: FSMContext,
) -> None:
    user = await _ensure_registered_callback(callback)
    if user is None:
        return

    data = await state.get_data()
    subject = None if callback_data.subject == "any" else callback_data.subject
    filter_type = data.get("filter_type")

    solutions = await db.get_approved_solutions(
        solution_type=filter_type,
        subject=subject,
        exclude_author_tg_id=callback.from_user.id,
        limit=100,
    )
    if not solutions:
        await state.clear()
        await callback.message.answer(
            "По выбранным фильтрам решений не найдено.",
            reply_markup=main_menu(is_admin=await db.is_admin(callback.from_user.id)),
        )
        await callback.answer()
        return

    solution_ids = [solution.id for solution in solutions]
    await state.update_data(solution_ids=solution_ids, browse_index=0)
    await state.set_state(BrowseSolutionsState.browsing)

    await callback.message.answer(f"Найдено решений: {len(solution_ids)}")
    await _send_solution_for_review(callback.bot, callback.message.chat.id, solution_ids[0])
    await callback.answer()


@router.callback_query(BrowseSolutionsState.browsing, BrowseActionCallback.filter(F.action == "next"))
async def browse_next_solution(callback: CallbackQuery, state: FSMContext) -> None:
    user = await _ensure_registered_callback(callback)
    if user is None:
        return

    data = await state.get_data()
    solution_ids: list[int] = data.get("solution_ids", [])
    if not solution_ids:
        await callback.answer("Список решений пуст.", show_alert=True)
        return

    index = int(data.get("browse_index", 0))
    index = (index + 1) % len(solution_ids)
    await state.update_data(browse_index=index)

    await _send_solution_for_review(callback.bot, callback.message.chat.id, solution_ids[index])
    await callback.answer(f"{index + 1}/{len(solution_ids)}")


@router.callback_query(SolutionRateCallback.filter())
async def rate_solution(
    callback: CallbackQuery,
    callback_data: SolutionRateCallback,
) -> None:
    user = await _ensure_registered_callback(callback)
    if user is None:
        return

    success, text = await db.rate_solution(
        rater_telegram_id=callback.from_user.id,
        solution_id=callback_data.solution_id,
        stars=callback_data.stars,
    )
    await callback.answer(text, show_alert=not success)


@router.message(F.text == "Поддержка")
async def menu_support(message: Message) -> None:
    user = await _ensure_registered_message(message)
    if user is None:
        return

    text = (
        "<b>Поддержка проекта</b>\n"
        "Можно поддержать через СБП 🙌\n"
        f"Ссылка-заглушка: <a href=\"{escape(settings.support_link)}\">оплатить</a>"
    )
    await message.answer(text)
