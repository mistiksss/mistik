from __future__ import annotations

import os
from dataclasses import dataclass


def _safe_int(value: str | None, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    initial_admin_id: int
    database_url: str
    support_link: str


settings = Settings(
    bot_token=os.getenv("BOT_TOKEN", ""),
    initial_admin_id=_safe_int(os.getenv("INITIAL_ADMIN_ID"), 0),
    database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot.sqlite3"),
    support_link=os.getenv("SUPPORT_LINK", "https://example.com/sbp"),
)

GRADES: tuple[int, ...] = (10, 11)

SOLUTION_TYPES: dict[str, str] = {
    "written": "Письменные",
    "cdz": "ЦДЗ",
}

SUBJECTS: tuple[str, ...] = (
    "Алгебра",
    "Геометрия",
    "ТВиСТ",
    "Физика",
    "Информатика",
    "Русский язык",
    "Литература",
    "Английский язык",
    "История",
    "География",
    "ОБЖ",
    "Обществознание",
    "Биология",
    "Химия",
)

BTN_PROFILE = "Профиль"
BTN_LEADERBOARD = "Лидерборд"
BTN_UPLOAD_SOLUTION = "Загрузить решение"
BTN_BROWSE_SOLUTIONS = "Смотреть решения"
BTN_SUPPORT = "Поддержать проект 👼"
BTN_ADMIN_PANEL = "Админ-панель"
BTN_ADD_ADMIN = "Добавить админа"
BTN_BAN_USER = "Забанить пользователя"
BTN_UNBAN_USER = "Разбанить пользователя"
BTN_VIEW_PENDING = "Решения на модерацию"
BTN_STATISTICS = "Статистика"
BTN_MANAGE_USERS = "Управление пользователями"
BTN_SKIP = "Пропустить"
BTN_BACK_TO_MAIN = "Выйти из админ панели ↩️"

# Разрешённые типы файлов для загрузки решений
ALLOWED_DOCUMENT_MIME_TYPES: frozenset[str] = frozenset({
    "application/pdf",
    "application/msword",  # .doc
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
    "image/webp",
})
ALLOWED_DOCUMENT_EXTENSIONS: frozenset[str] = frozenset({
    "pdf", "doc", "docx", "png", "jpg", "jpeg", "webp",
})
