"""SQLAlchemy ORM models: User, Post, and PasswordResetToken."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey
from sqlalchemy.types import DateTime, Integer, String, Text

from app.database import Base
from app.image_utils import generate_presigned_url


class User(Base):
    """A registered account. Password stored only as a hash."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    image_file: Mapped[str | None] = mapped_column(
        String(200), nullable=True, default=None
    )

    posts: Mapped[list[Post]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )
    reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def image_key(self) -> str | None:
        """S3 object key for the profile picture, if one is uploaded."""
        if self.image_file:
            return f"profile_pics/{self.image_file}"
        return None

    @property
    def image_url(self) -> str:
        """Time-limited pre-signed URL, or the bundled default image."""
        if self.image_file:
            return generate_presigned_url(f"profile_pics/{self.image_file}")
        return "/static/profile_pics/default.jpg"


class Post(Base):
    """A blog post owned by a user."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    likes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    date_posted: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    author: Mapped[User] = relationship(back_populates="posts")


class PasswordResetToken(Base):
    """A one-time password-reset token; only its hash is stored."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    user: Mapped[User] = relationship(back_populates="reset_tokens")