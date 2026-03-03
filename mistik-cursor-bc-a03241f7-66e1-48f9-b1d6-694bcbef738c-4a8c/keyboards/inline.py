from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import GRADES, SOLUTION_TYPES, SUBJECTS


class ModerationCallback(CallbackData, prefix="mod"):
    action: str
    solution_id: int


class UploadGradeCallback(CallbackData, prefix="upl_g"):
    grade: int


class UploadTypeCallback(CallbackData, prefix="upl_t"):
    type_key: str


class UploadSubjectCallback(CallbackData, prefix="upl_s"):
    subject: str


class UploadContentConfirmCallback(CallbackData, prefix="upl_c"):
    action: str  # "confirm" | "replace"


class SelfAssessmentCallback(CallbackData, prefix="self"):
    stars: int


class BrowseGradeCallback(CallbackData, prefix="br_g"):
    grade: int


class BrowseTypeCallback(CallbackData, prefix="br_t"):
    type_key: str


class BrowseSubjectCallback(CallbackData, prefix="br_s"):
    subject: str


class SolutionRateCallback(CallbackData, prefix="rate"):
    solution_id: int
    stars: int


class BrowseActionCallback(CallbackData, prefix="br_a"):
    action: str


class UserProfileCallback(CallbackData, prefix="u_prof"):
    telegram_id: int


class ProfileActionCallback(CallbackData, prefix="p_act"):
    action: str


class AdminPendingSolutionCallback(CallbackData, prefix="adm_pend"):
    solution_id: int


class AdminManageUserCallback(CallbackData, prefix="adm_usr"):
    telegram_id: int
    action: str  # "change_nickname" | "remove_avatar" | "change_avatar"


def moderation_keyboard(solution_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Одобрить ✅",
        callback_data=ModerationCallback(action="approve", solution_id=solution_id).pack(),
    )
    builder.button(
        text="Отклонить ❌",
        callback_data=ModerationCallback(action="reject", solution_id=solution_id).pack(),
    )
    builder.adjust(2)
    return builder.as_markup()


def upload_grade_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for grade in GRADES:
        builder.button(
            text=f"{grade} класс",
            callback_data=UploadGradeCallback(grade=grade).pack(),
        )
    builder.adjust(len(GRADES))
    return builder.as_markup()


def upload_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for type_key, title in SOLUTION_TYPES.items():
        builder.button(
            text=title,
            callback_data=UploadTypeCallback(type_key=type_key).pack(),
        )
    builder.adjust(2)
    return builder.as_markup()


def upload_subject_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for subject in SUBJECTS:
        builder.button(
            text=subject,
            callback_data=UploadSubjectCallback(subject=subject).pack(),
        )
    builder.adjust(2)
    return builder.as_markup()


def upload_content_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Всё верно ✅",
        callback_data=UploadContentConfirmCallback(action="confirm").pack(),
    )
    builder.button(
        text="Заменить",
        callback_data=UploadContentConfirmCallback(action="replace").pack(),
    )
    builder.adjust(2)
    return builder.as_markup()


def self_assessment_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for stars in range(2, 6):
        builder.button(
            text=f"{stars}",
            callback_data=SelfAssessmentCallback(stars=stars).pack(),
        )
    builder.adjust(4)
    return builder.as_markup()


def browse_grade_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Любой класс", callback_data=BrowseGradeCallback(grade=0).pack())
    for grade in GRADES:
        builder.button(
            text=f"{grade} класс",
            callback_data=BrowseGradeCallback(grade=grade).pack(),
        )
    builder.adjust(1, len(GRADES))
    return builder.as_markup()


def browse_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Любой тип", callback_data=BrowseTypeCallback(type_key="any").pack())
    for type_key, title in SOLUTION_TYPES.items():
        builder.button(
            text=title,
            callback_data=BrowseTypeCallback(type_key=type_key).pack(),
        )
    builder.adjust(1, 2)
    return builder.as_markup()


def browse_subject_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Любой предмет", callback_data=BrowseSubjectCallback(subject="any").pack())
    for subject in SUBJECTS:
        builder.button(
            text=subject,
            callback_data=BrowseSubjectCallback(subject=subject).pack(),
        )
    builder.adjust(1, 2)
    return builder.as_markup()


def profile_actions_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Мои решения",
        callback_data=ProfileActionCallback(action="my_solutions").pack(),
    )
    builder.button(
        text="Изменить аватар",
        callback_data=ProfileActionCallback(action="change_avatar").pack(),
    )
    builder.adjust(1)
    return builder.as_markup()


def leaderboard_keyboard(users: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for user in users:
        builder.button(
            text=f"👤 {user.nickname}",
            callback_data=UserProfileCallback(telegram_id=user.telegram_id).pack(),
        )
    builder.adjust(1)
    return builder.as_markup()


def admin_pending_solutions_keyboard(solutions: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in solutions:
        builder.button(
            text=f"#{s.id} | {s.subject} | {s.author.nickname}",
            callback_data=AdminPendingSolutionCallback(solution_id=s.id).pack(),
        )
    builder.adjust(1)
    return builder.as_markup()


def admin_manage_user_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Изменить ник",
        callback_data=AdminManageUserCallback(telegram_id=telegram_id, action="change_nickname").pack(),
    )
    builder.button(
        text="Удалить аватар",
        callback_data=AdminManageUserCallback(telegram_id=telegram_id, action="remove_avatar").pack(),
    )
    builder.button(
        text="Изменить аватар",
        callback_data=AdminManageUserCallback(telegram_id=telegram_id, action="change_avatar").pack(),
    )
    builder.adjust(1)
    return builder.as_markup()


def solution_review_keyboard(solution_id: int, author_tg_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for stars in range(1, 6):
        builder.button(
            text=f"{stars}⭐",
            callback_data=SolutionRateCallback(solution_id=solution_id, stars=stars).pack(),
        )
    builder.button(
        text="Следующее ➡️",
        callback_data=BrowseActionCallback(action="next").pack(),
    )
    builder.button(
        text="Профиль автора",
        callback_data=UserProfileCallback(telegram_id=author_tg_id).pack(),
    )
    builder.adjust(5, 2)
    return builder.as_markup()
