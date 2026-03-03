from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from config import settings
from database.models import Admin, Base, BannedId, Solution, User

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


def _ratings_map(raw: str | None) -> dict[str, int]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    normalized: dict[str, int] = {}
    for key, value in data.items():
        if isinstance(value, int):
            normalized[str(key)] = value
    return normalized


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.begin() as conn:
        if "sqlite" in settings.database_url:
            from sqlalchemy import text
            result = await conn.execute(text("PRAGMA table_info(solutions)"))
            columns = [row[1] for row in result.fetchall()]
            if "grade" not in columns:
                await conn.execute(text("ALTER TABLE solutions ADD COLUMN grade INTEGER DEFAULT 10"))


async def ensure_initial_admin() -> None:
    if settings.initial_admin_id <= 0:
        return
    await add_admin(settings.initial_admin_id, settings.initial_admin_id)


async def is_admin(telegram_id: int) -> bool:
    async with async_session() as session:
        stmt = select(Admin.id).where(Admin.telegram_id == telegram_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None


async def add_admin(telegram_id: int, added_by: int | None = None) -> bool:
    async with async_session() as session:
        stmt = select(Admin).where(Admin.telegram_id == telegram_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return False

        session.add(Admin(telegram_id=telegram_id, added_by=added_by))
        await session.commit()
        return True


async def get_admin_ids() -> list[int]:
    async with async_session() as session:
        stmt = select(Admin.telegram_id).order_by(Admin.created_at.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_user_by_telegram_id(telegram_id: int) -> User | None:
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def register_user(
    telegram_id: int,
    nickname: str,
    avatar_file_id: str | None = None,
) -> User:
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=telegram_id,
                nickname=nickname,
                avatar_file_id=avatar_file_id,
                rated_solutions_json="{}",
            )
            session.add(user)
        else:
            user.nickname = nickname
            user.avatar_file_id = avatar_file_id

        await session.commit()
        await session.refresh(user)
        return user


async def update_user_nickname(telegram_id: int, nickname: str) -> bool:
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return False

        user.nickname = nickname
        await session.commit()
        return True


async def update_user_avatar(telegram_id: int, avatar_file_id: str | None) -> bool:
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return False

        user.avatar_file_id = avatar_file_id
        await session.commit()
        return True


async def is_telegram_id_banned(telegram_id: int) -> bool:
    """Проверяет, забанен ли ID (в users.is_banned или в banned_ids)."""
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user and user.is_banned:
            return True

        stmt = select(BannedId.id).where(BannedId.telegram_id == telegram_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None


async def set_user_banned(telegram_id: int, banned: bool = True) -> bool:
    """Бан: если юзер есть — ставим is_banned; иначе добавляем в banned_ids."""
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is not None:
            user.is_banned = banned
            if not banned:
                stmt_ban = select(BannedId).where(BannedId.telegram_id == telegram_id)
                r = await session.execute(stmt_ban)
                banned_row = r.scalar_one_or_none()
                if banned_row:
                    await session.delete(banned_row)
            await session.commit()
            return True

        if banned:
            stmt_exist = select(BannedId.id).where(BannedId.telegram_id == telegram_id)
            r = await session.execute(stmt_exist)
            if r.scalar_one_or_none() is not None:
                await session.commit()
                return True
            session.add(BannedId(telegram_id=telegram_id))
        else:
            stmt_ban = select(BannedId).where(BannedId.telegram_id == telegram_id)
            r = await session.execute(stmt_ban)
            banned_row = r.scalar_one_or_none()
            if banned_row:
                await session.delete(banned_row)
            else:
                await session.commit()
                return False
        await session.commit()
        return True


async def create_solution(
    *,
    author_telegram_id: int,
    grade: int,
    solution_type: str,
    subject: str,
    content_type: str,
    content_value: str,
    description: str | None,
    self_assessment: int | None,
) -> Solution:
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == author_telegram_id)
        result = await session.execute(stmt)
        author = result.scalar_one_or_none()
        if author is None:
            raise ValueError("Пользователь не зарегистрирован")

        solution = Solution(
            author_id=author.id,
            grade=grade,
            solution_type=solution_type,
            subject=subject,
            content_type=content_type,
            content_value=content_value,
            description=description,
            self_assessment=self_assessment,
            status="pending",
        )
        session.add(solution)

        author.total_solutions_count += 1

        await session.commit()
        await session.refresh(solution)
        return solution


async def get_solution_with_author(solution_id: int) -> Solution | None:
    async with async_session() as session:
        stmt = (
            select(Solution)
            .options(selectinload(Solution.author))
            .where(Solution.id == solution_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def set_solution_status(
    solution_id: int,
    status: str,
    moderated_by_admin_id: int,
    moderation_note: str | None = None,
) -> Solution | None:
    async with async_session() as session:
        stmt = (
            select(Solution)
            .options(selectinload(Solution.author))
            .where(Solution.id == solution_id)
        )
        result = await session.execute(stmt)
        solution = result.scalar_one_or_none()
        if solution is None:
            return None

        previous_status = solution.status
        solution.status = status
        solution.moderated_by_admin_id = moderated_by_admin_id
        solution.moderation_note = moderation_note
        solution.moderated_at = datetime.now(timezone.utc)

        if previous_status != "approved" and status == "approved":
            solution.author.approved_solutions_count += 1
        elif previous_status == "approved" and status != "approved":
            solution.author.approved_solutions_count = max(
                0, solution.author.approved_solutions_count - 1
            )

        await session.commit()
        return solution


async def list_user_solutions(telegram_id: int, limit: int = 20) -> list[Solution]:
    async with async_session() as session:
        stmt = (
            select(Solution)
            .join(User, Solution.author_id == User.id)
            .where(User.telegram_id == telegram_id)
            .order_by(Solution.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_top_users(limit: int = 10) -> list[User]:
    async with async_session() as session:
        stmt = (
            select(User)
            .where(User.is_banned.is_(False))
            .order_by(
                User.approved_solutions_count.desc(),
                User.rating_points.desc(),
                User.created_at.asc(),
            )
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_user_rank(telegram_id: int) -> int | None:
    async with async_session() as session:
        stmt = (
            select(User.telegram_id)
            .where(User.is_banned.is_(False))
            .order_by(
                User.approved_solutions_count.desc(),
                User.rating_points.desc(),
                User.created_at.asc(),
            )
        )
        result = await session.execute(stmt)
        user_ids = list(result.scalars().all())

    for index, user_id in enumerate(user_ids, start=1):
        if user_id == telegram_id:
            return index
    return None


async def get_approved_solutions(
    *,
    grade: int | None = None,
    solution_type: str | None = None,
    subject: str | None = None,
    exclude_author_tg_id: int | None = None,
    limit: int = 50,
) -> list[Solution]:
    async with async_session() as session:
        stmt = (
            select(Solution)
            .options(selectinload(Solution.author))
            .join(User, Solution.author_id == User.id)
            .where(Solution.status == "approved")
            .where(User.is_banned.is_(False))
        )

        if grade is not None:
            stmt = stmt.where(Solution.grade == grade)
        if solution_type:
            stmt = stmt.where(Solution.solution_type == solution_type)
        if subject:
            stmt = stmt.where(Solution.subject == subject)
        if exclude_author_tg_id is not None:
            stmt = stmt.where(User.telegram_id != exclude_author_tg_id)

        stmt = stmt.order_by(Solution.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def rate_solution(
    *,
    rater_telegram_id: int,
    solution_id: int,
    stars: int,
) -> tuple[bool, str]:
    if stars < 1 or stars > 5:
        return False, "Оценка должна быть от 1 до 5."

    async with async_session() as session:
        rater_stmt = select(User).where(User.telegram_id == rater_telegram_id)
        rater_result = await session.execute(rater_stmt)
        rater = rater_result.scalar_one_or_none()
        if rater is None:
            return False, "Сначала пройдите регистрацию через /start."
        if rater.is_banned:
            return False, "Ваш аккаунт заблокирован."

        solution_stmt = (
            select(Solution)
            .options(selectinload(Solution.author))
            .where(Solution.id == solution_id)
        )
        solution_result = await session.execute(solution_stmt)
        solution = solution_result.scalar_one_or_none()
        if solution is None:
            return False, "Решение не найдено."
        if solution.status != "approved":
            return False, "Оценивать можно только одобренные решения."
        if solution.author.telegram_id == rater_telegram_id:
            return False, "Нельзя оценивать собственное решение."

        ratings = _ratings_map(rater.rated_solutions_json)
        solution_key = str(solution.id)
        if solution_key in ratings:
            return False, "Вы уже оценили это решение."

        ratings[solution_key] = stars
        rater.rated_solutions_json = json.dumps(ratings, ensure_ascii=False)

        solution.ratings_sum += stars
        solution.ratings_count += 1
        solution.author.rating_points += stars

        await session.commit()
        return True, "Спасибо! Оценка сохранена."


async def get_pending_solutions(limit: int = 100) -> list[Solution]:
    async with async_session() as session:
        stmt = (
            select(Solution)
            .options(selectinload(Solution.author))
            .where(Solution.status == "pending")
            .order_by(Solution.created_at.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_total_users_count() -> int:
    async with async_session() as session:
        stmt = select(func.count()).select_from(User)
        result = await session.execute(stmt)
        return int(result.scalar())


async def get_pending_solutions_count() -> int:
    async with async_session() as session:
        stmt = select(func.count()).select_from(Solution).where(Solution.status == "pending")
        result = await session.execute(stmt)
        return int(result.scalar())


def solution_status_label(status: str) -> str:
    labels: dict[str, str] = {
        "pending": "На модерации",
        "approved": "Одобрено",
        "rejected": "Отклонено",
    }
    return labels.get(status, status)
