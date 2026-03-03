from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(50))
    avatar_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    rating_points: Mapped[int] = mapped_column(Integer, default=0)
    total_solutions_count: Mapped[int] = mapped_column(Integer, default=0)
    approved_solutions_count: Mapped[int] = mapped_column(Integer, default=0)

    rated_solutions_json: Mapped[str] = mapped_column(Text, default="{}")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    solutions: Mapped[list["Solution"]] = relationship(
        "Solution", back_populates="author", foreign_keys="Solution.author_id"
    )


class Solution(Base):
    __tablename__ = "solutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    grade: Mapped[int] = mapped_column(Integer, default=10, index=True)
    solution_type: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(100))

    content_type: Mapped[str] = mapped_column(String(20))
    content_value: Mapped[str] = mapped_column(Text)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    self_assessment: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    moderated_by_admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    moderation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ratings_sum: Mapped[int] = mapped_column(Integer, default=0)
    ratings_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    author: Mapped[User] = relationship("User", back_populates="solutions", foreign_keys=[author_id])

    @property
    def average_rating(self) -> float:
        if not self.ratings_count:
            return 0.0
        return round(self.ratings_sum / self.ratings_count, 2)


class BannedId(Base):
    """Telegram IDs забаненные до регистрации."""

    __tablename__ = "banned_ids"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    added_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
