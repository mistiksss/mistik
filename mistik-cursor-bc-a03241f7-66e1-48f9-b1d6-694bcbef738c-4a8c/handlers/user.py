from __future__ import annotations

from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import (
    ALLOWED_DOCUMENT_EXTENSIONS,
    ALLOWED_DOCUMENT_MIME_TYPES,
    BTN_BROWSE_SOLUTIONS,
    BTN_LEADERBOARD,
    BTN_PROFILE,
    BTN_SKIP,
    BTN_SUPPORT,
    BTN_UPLOAD_SOLUTION,
    GRADES,
    SOLUTION_TYPES,
    settings,
)
from database import requests as db
from database.models import User
from keyboards.inline import (
    BrowseActionCallback,
    BrowseGradeCallback,
    BrowseSubjectCallback,
    BrowseTypeCallback,
    ProfileActionCallback,
    SelfAssessmentCallback,
    SolutionRateCallback,
    UploadContentConfirmCallback,
    UploadGradeCallback,
    UploadSubjectCallback,
    UploadTypeCallback,
    UserProfileCallback,
    browse_grade_keyboard,
    browse_subject_keyboard,
    browse_type_keyboard,
    leaderboard_keyboard,
    moderation_keyboard,
    profile_actions_keyboard,
    self_assessment_keyboard,
    solution_review_keyboard,
    upload_content_confirm_keyboard,
    upload_grade_keyboard,
    upload_subject_keyboard,
    upload_type_keyboard,
)
from keyboards.reply import (
    main_menu,
    registration_avatar_keyboard,
    remove_keyboard,
)
from states import BrowseSolutionsState, ProfileState, RegistrationState, UploadSolutionState

router = Router(name="user")


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _profile_text(user, rank: int | None) -> str:
    rank_text = f"#{rank}" if rank else "—"
    return (
        "<b>Профиль</b>\n"
        f"Ник: <b>{escape(user.nickname)}</b>\n"
        f"Рейтинг: {user.rating_points} ⭐\n"
        f"Место в топе: {rank_text}\n"
        f"Решений: {user.approved_solutions_count}"
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
        f"Класс: {getattr(solution, 'grade', 10)}\n"
        f"Автор: <b>{escape(solution.author.nickname)}</b>\n"
        f"Тип: {escape(solution.solution_type)}\n"
        f"Предмет: {escape(solution.subject)}\n"
        f"Предположительная оценка: {solution.self_assessment or '—'}\n"
        f"Оценка пользователей: {solution.average_rating}⭐\n"
        f"Описание: {description}"
    )


def _moderation_text(solution) -> str:
    description = escape(solution.description or "Без описания")
    return (
        "<b>Новое решение на модерацию</b>\n"
        f"ID: <code>{solution.id}</code>\n"
        f"Класс: {getattr(solution, 'grade', 10)}\n"
        f"Автор: <b>{escape(solution.author.nickname)}</b> "
        f"(<code>{solution.author.telegram_id}</code>)\n"
        f"Тип: {escape(solution.solution_type)}\n"
        f"Предмет: {escape(solution.subject)}\n"
        f"Оценка автора: {solution.self_assessment or '—'}⭐\n"
        f"Описание: {description}"
    )


async def _send_solution_content(
    bot: Bot,
    chat_id: int,
    solution,
    caption: str,
    reply_markup,
) -> None:
    cap_short = _truncate(caption, 1024)
    if solution.content_type == "photo":
        await bot.send_photo(
            chat_id=chat_id,
            photo=solution.content_value,
            caption=cap_short,
            reply_markup=reply_markup,
        )
        return
    if solution.content_type == "document":
        await bot.send_document(
            chat_id=chat_id,
            document=solution.content_value,
            caption=cap_short,
            reply_markup=reply_markup,
        )
        return
    text_full = (
        f"{caption}\n\n"
        f"<b>Текст решения:</b>\n{escape(solution.content_value)}"
    )
    await bot.send_message(
        chat_id=chat_id,
        text=_truncate(text_full, 4096),
        reply_markup=reply_markup,
    )


async def _send_solution_for_review(bot: Bot, chat_id: int, solution_id: int) -> None:
    solution = await db.get_solution_with_author(solution_id)
    if solution is None:
        await bot.send_message(chat_id, "Решение не найдено.")
        return
    caption = _solution_card_text(solution)
    keyboard = solution_review_keyboard(solution.id, solution.author.telegram_id)
    await _send_solution_content(bot, chat_id, solution, caption, keyboard)


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
            await _send_solution_content(bot, admin_id, solution, header, keyboard)
        except TelegramBadRequest:
            continue


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user_by_telegram_id(message.from_user.id)
    if await db.is_telegram_id_banned(message.from_user.id):
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
        "Отправь ник (одно слово, 4-24 символа).\n"
        "Пожалуйста не используй свое настоящее ФИО.",
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
    if not 4 <= len(nickname) <= 24:
        await message.answer("Длина ника должна быть от 4 до 24 символов.")
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


def _is_gif_or_animation(message: Message) -> bool:
    return message.animation is not None or (
        message.document is not None
        and message.document.mime_type
        and "gif" in (message.document.mime_type or "").lower()
    )


def _is_allowed_document(document) -> bool:
    if document is None:
        return False
    mime = (document.mime_type or "").strip().lower()
    if mime and mime in ALLOWED_DOCUMENT_MIME_TYPES:
        return True
    if document.file_name:
        ext = (document.file_name.split(".")[-1] or "").lower()
        return ext in ALLOWED_DOCUMENT_EXTENSIONS
    return False


@router.message(RegistrationState.waiting_avatar)
async def registration_avatar(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    nickname = data.get("nickname")
    if not nickname:
        await state.clear()
        await message.answer("Сессия регистрации устарела. Начните заново: /start")
        return

    if _is_gif_or_animation(message):
        await message.answer("GIF не поддерживаются. Отправьте обычное фото или нажмите «Пропустить».")
        return

    avatar_file_id = None
    if message.photo:
        avatar_file_id = message.photo[-1].file_id
    elif message.text and message.text.strip().lower() == BTN_SKIP.lower():
        avatar_file_id = None
    else:
        await message.answer(f"Отправьте фото или нажмите кнопку «{BTN_SKIP}». ")
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


@router.message(F.text == BTN_PROFILE)
async def menu_profile(message: Message, user: User) -> None:
    await _send_profile(message, user, with_actions=True)


@router.callback_query(ProfileActionCallback.filter(F.action == "change_avatar"))
async def profile_change_avatar_start(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await state.set_state(ProfileState.waiting_new_avatar)
    await callback.message.answer(
        "Отправьте новое фото для аватарки (не GIF).",
        reply_markup=registration_avatar_keyboard(),
    )
    await callback.answer()


@router.message(ProfileState.waiting_new_avatar)
async def profile_change_avatar_finish(message: Message, state: FSMContext, user: User) -> None:
    if _is_gif_or_animation(message):
        await message.answer("GIF не поддерживаются. Отправьте обычное фото или нажмите «Пропустить».")
        return

    avatar_file_id = None
    if message.photo:
        avatar_file_id = message.photo[-1].file_id
    elif message.text and message.text.strip().lower() == BTN_SKIP.lower():
        avatar_file_id = None
    else:
        await message.answer(f"Отправьте фото или нажмите «{BTN_SKIP}».")
        return

    await db.update_user_avatar(message.from_user.id, avatar_file_id)
    await state.clear()
    await message.answer(
        "Аватар обновлён.",
        reply_markup=main_menu(is_admin=await db.is_admin(message.from_user.id)),
    )
    updated_user = await db.get_user_by_telegram_id(message.from_user.id)
    if updated_user:
        await _send_profile(message, updated_user, with_actions=True)


@router.callback_query(ProfileActionCallback.filter(F.action == "my_solutions"))
async def profile_my_solutions(callback: CallbackQuery, user: User) -> None:
    solutions = await db.list_user_solutions(user.telegram_id, limit=30)
    if not solutions:
        await callback.answer("У вас пока нет загруженных решений.", show_alert=True)
        return

    lines = ["<b>Мои решения:</b>"]
    for solution in solutions:
        grade = getattr(solution, "grade", 10)
        lines.append(
            f"#{solution.id} | {grade} кл | {escape(solution.subject)} | {escape(solution.solution_type)} | "
            f"{db.solution_status_label(solution.status)}"
        )

    await callback.message.answer(_truncate("\n".join(lines), 4096))
    await callback.answer()


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


@router.message(F.text == BTN_LEADERBOARD)
async def menu_leaderboard(message: Message, user: User) -> None:
    top_users = await db.get_top_users(limit=10)
    if not top_users:
        await message.answer("Лидерборд пока пуст.")
        return

    lines = ["<b>ТОП-10 активных пользователей:</b>"]
    for index, top_user in enumerate(top_users, start=1):
        approved_count = top_user.approved_solutions_count
        solutions_word = _pluralize_ru(approved_count, "решение", "решения", "решений")
        lines.append(
            f"{index}. {escape(top_user.nickname)} — "
            f"{approved_count} {solutions_word} | {top_user.rating_points} ⭐"
        )

    await message.answer(
        "\n".join(lines),
        reply_markup=leaderboard_keyboard(top_users),
    )


@router.callback_query(UserProfileCallback.filter())
async def open_public_profile(
    callback: CallbackQuery,
    callback_data: UserProfileCallback,
    user: User,
) -> None:
    target_user = await db.get_user_by_telegram_id(callback_data.telegram_id)
    if target_user is None:
        await callback.answer("Профиль не найден.", show_alert=True)
        return

    await _send_profile(callback, target_user, with_actions=False)
    await callback.answer()


@router.message(F.text == BTN_UPLOAD_SOLUTION)
async def menu_upload_solution(message: Message, state: FSMContext, user: User) -> None:
    await state.clear()
    await state.set_state(UploadSolutionState.waiting_grade)
    await message.answer(
        "Выберите класс:",
        reply_markup=upload_grade_keyboard(),
    )


@router.callback_query(UploadSolutionState.waiting_grade, UploadGradeCallback.filter())
async def upload_pick_grade(
    callback: CallbackQuery,
    callback_data: UploadGradeCallback,
    state: FSMContext,
    user: User,
) -> None:
    if callback_data.grade not in GRADES:
        await callback.answer("Некорректный класс.", show_alert=True)
        return

    await state.update_data(grade=callback_data.grade)
    await state.set_state(UploadSolutionState.waiting_type)
    await callback.message.answer(
        "Выберите тип решения:",
        reply_markup=upload_type_keyboard(),
    )
    await callback.answer()


@router.callback_query(UploadSolutionState.waiting_type, UploadTypeCallback.filter())
async def upload_pick_type(
    callback: CallbackQuery,
    callback_data: UploadTypeCallback,
    state: FSMContext,
    user: User,
) -> None:
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
    user: User,
) -> None:
    await state.update_data(subject=callback_data.subject)
    await state.set_state(UploadSolutionState.waiting_content)
    await callback.message.answer(
        "Отправьте решение: текст, фото (JPG, PNG) или файл (PDF, DOC, DOCX, PNG, JPG, WEBP)."
    )
    await callback.answer()


@router.message(UploadSolutionState.waiting_content)
async def upload_content(message: Message, state: FSMContext, user: User) -> None:
    if _is_gif_or_animation(message):
        await message.answer("GIF не поддерживаются. Отправьте фото, документ или текст.")
        return

    content_type: str | None = None
    content_value: str | None = None

    if message.photo:
        content_type = "photo"
        content_value = message.photo[-1].file_id
    elif message.document:
        if not _is_allowed_document(message.document):
            await message.answer(
                "Недопустимый формат файла. Разрешены только: PDF, DOC, DOCX, PNG, JPG, WEBP."
            )
            return
        content_type = "document"
        content_value = message.document.file_id
    elif message.text:
        content_type = "text"
        content_value = message.text.strip()
        if not content_value:
            await message.answer("Текст решения пуст. Отправьте корректный текст.")
            return

    if content_type is None or content_value is None:
        await message.answer(
            "Поддерживаются: текст, фото (JPG, PNG) или файлы PDF, DOC, DOCX, PNG, JPG, WEBP."
        )
        return

    await state.update_data(content_type=content_type, content_value=content_value)

    content_label = {"photo": "фото", "document": "документ", "text": "текст"}.get(content_type, "файл")
    await state.set_state(UploadSolutionState.waiting_content_confirm)
    await message.answer(
        f"Вы точно отправили нужное {content_label}?",
        reply_markup=upload_content_confirm_keyboard(),
    )


@router.callback_query(
    UploadSolutionState.waiting_content_confirm, UploadContentConfirmCallback.filter()
)
async def upload_content_confirm(
    callback: CallbackQuery,
    callback_data: UploadContentConfirmCallback,
    state: FSMContext,
    user: User,
) -> None:
    if callback_data.action == "replace":
        await state.set_state(UploadSolutionState.waiting_content)
        await callback.message.answer(
            "Отправьте решение заново: текст, фото (JPG, PNG) или файл (PDF, DOC, DOCX, PNG, JPG, WEBP)."
        )
        await callback.answer("Отправьте новое решение")
        return

    await state.set_state(UploadSolutionState.waiting_description)
    await callback.message.answer(
        "Добавьте краткое описание решения или нажмите «Пропустить».\n"
        "Пример описания: Ответы могут быть не верными",
        reply_markup=registration_avatar_keyboard(),
    )
    await callback.answer()


@router.message(UploadSolutionState.waiting_description, F.text)
async def upload_description(message: Message, state: FSMContext, user: User) -> None:
    text = (message.text or "").strip()

    if text == BTN_SKIP:
        description: str | None = None
    else:
        description = _truncate(text, 1500) if text else None

    await state.update_data(description=description)
    await state.set_state(UploadSolutionState.waiting_assessment)
    await message.answer(
        "Оцените на какую оценку ваше решение (2-5):",
        reply_markup=self_assessment_keyboard(),
    )


@router.callback_query(
    UploadSolutionState.waiting_assessment, SelfAssessmentCallback.filter()
)
async def upload_finish(
    callback: CallbackQuery,
    callback_data: SelfAssessmentCallback,
    state: FSMContext,
    user: User,
) -> None:
    form = await state.get_data()
    required_keys = ("grade", "solution_type", "subject", "content_type", "content_value", "description")
    if not all(key in form for key in required_keys):
        await state.clear()
        await callback.answer("Сессия загрузки устарела. Начните заново.", show_alert=True)
        return

    solution = await db.create_solution(
        author_telegram_id=callback.from_user.id,
        grade=form["grade"],
        solution_type=form["solution_type"],
        subject=form["subject"],
        content_type=form["content_type"],
        content_value=form["content_value"],
        description=form["description"],
        self_assessment=callback_data.stars,
    )
    await state.clear()

    await callback.message.answer(
        f"Решение #{solution.id} отправлено на модерацию. Мы рассмотрим его как можно скорее!",
        reply_markup=main_menu(is_admin=await db.is_admin(callback.from_user.id)),
    )
    await callback.answer("Отправлено")
    await _send_solution_to_admins(callback.bot, solution.id)


@router.message(F.text == BTN_BROWSE_SOLUTIONS)
async def menu_browse_solutions(message: Message, state: FSMContext, user: User) -> None:
    await state.clear()
    await state.set_state(BrowseSolutionsState.waiting_grade)
    await message.answer("Выберите класс:", reply_markup=browse_grade_keyboard())


@router.callback_query(BrowseSolutionsState.waiting_grade, BrowseGradeCallback.filter())
async def browse_pick_grade(
    callback: CallbackQuery,
    callback_data: BrowseGradeCallback,
    state: FSMContext,
    user: User,
) -> None:
    grade = None if callback_data.grade == 0 else callback_data.grade
    await state.update_data(filter_grade=grade)
    await state.set_state(BrowseSolutionsState.waiting_type)
    await callback.message.answer("Выберите тип решений:", reply_markup=browse_type_keyboard())
    await callback.answer()


@router.callback_query(BrowseSolutionsState.waiting_type, BrowseTypeCallback.filter())
async def browse_pick_type(
    callback: CallbackQuery,
    callback_data: BrowseTypeCallback,
    state: FSMContext,
    user: User,
) -> None:
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
    user: User,
) -> None:
    data = await state.get_data()
    subject = None if callback_data.subject == "any" else callback_data.subject
    filter_type = data.get("filter_type")
    filter_grade = data.get("filter_grade")

    solutions = await db.get_approved_solutions(
        grade=filter_grade,
        solution_type=filter_type,
        subject=subject,
        limit=150,
    )
    if not solutions:
        await callback.message.answer(
            "По выбранным фильтрам решений не найдено. Выберите другой предмет:",
            reply_markup=browse_subject_keyboard(),
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
async def browse_next_solution(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    data = await state.get_data()
    solution_ids: list[int] = data.get("solution_ids", [])
    if not solution_ids:
        await callback.answer("Решений больше нет.", show_alert=True)
        return

    index = int(data.get("browse_index", 0))
    next_index = index + 1
    if next_index >= len(solution_ids):
        await callback.answer("Решений больше нет. Вы просмотрели все.", show_alert=True)
        return

    await state.update_data(browse_index=next_index)
    await _send_solution_for_review(callback.bot, callback.message.chat.id, solution_ids[next_index])
    await callback.answer(f"{next_index + 1}/{len(solution_ids)}")


@router.callback_query(SolutionRateCallback.filter())
async def rate_solution(
    callback: CallbackQuery,
    callback_data: SolutionRateCallback,
    user: User,
) -> None:
    success, text = await db.rate_solution(
        rater_telegram_id=callback.from_user.id,
        solution_id=callback_data.solution_id,
        stars=callback_data.stars,
    )
    await callback.answer(text, show_alert=not success)


@router.message(F.text == BTN_SUPPORT)
async def menu_support(message: Message, user: User) -> None:
    text = (
        "<b>Поддержать проект денюжкой ♥</b>\n\n"
        "По номеру телефона: <code>+7 926 884-80-10</code>"
    )
    await message.answer(text)
