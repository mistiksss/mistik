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

SOLUTION_TYPES: dict[str, str] = {
    "written": "Письменно",
    "cdz": "ЦДЗ",
}

SUBJECTS: tuple[str, ...] = (
    "Математика",
    "Физика",
    "Информатика",
    "Русский язык",
    "Литература",
    "Английский язык",
    "История",
    "Обществознание",
    "Биология",
    "Химия",
)
