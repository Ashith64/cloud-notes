"""SQLAlchemy 2 declarative models for Cloud Notes.

All tables follow the spec section D4.  UUID primary keys are stored as
VARCHAR(36) strings so they work on both SQLite and MySQL without the
mysql-connector-python UUID extension.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    failed_logins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    notebooks: Mapped[list["Notebook"]] = relationship(
        "Notebook", back_populates="user", cascade="all, delete-orphan"
    )
    notes: Mapped[list["Note"]] = relationship(
        "Note", back_populates="user", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", back_populates="user", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment", back_populates="user", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# notebooks
# ---------------------------------------------------------------------------
class Notebook(Base):
    __tablename__ = "notebooks"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_notebook_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    user: Mapped["User"] = relationship("User", back_populates="notebooks")
    notes: Mapped[list["Note"]] = relationship(
        "Note", back_populates="notebook"
    )


# ---------------------------------------------------------------------------
# notes  (UUID primary key, stored as VARCHAR(36))
# ---------------------------------------------------------------------------
class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (
        Index("ix_notes_user_updated", "user_id", "updated_at"),
        Index("ix_notes_user_deleted", "user_id", "deleted_at"),
        Index("ix_notes_title", "title"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    notebook_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("notebooks.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="Untitled")
    snippet: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    user: Mapped["User"] = relationship("User", back_populates="notes")
    notebook: Mapped["Notebook | None"] = relationship(
        "Notebook", back_populates="notes"
    )
    note_tags: Mapped[list["NoteTag"]] = relationship(
        "NoteTag", back_populates="note", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment", back_populates="note", cascade="all, delete-orphan"
    )
    history: Mapped[list["NoteHistory"]] = relationship(
        "NoteHistory", back_populates="note", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# tags + note_tags (many-to-many join)
# ---------------------------------------------------------------------------
class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_tag_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="tags")
    note_tags: Mapped[list["NoteTag"]] = relationship(
        "NoteTag", back_populates="tag", cascade="all, delete-orphan"
    )


class NoteTag(Base):
    __tablename__ = "note_tags"

    note_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    note: Mapped["Note"] = relationship("Note", back_populates="note_tags")
    tag: Mapped["Tag"] = relationship("Tag", back_populates="note_tags")


# ---------------------------------------------------------------------------
# attachments  (UUID primary key)
# ---------------------------------------------------------------------------
class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    note_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notes.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    user: Mapped["User"] = relationship("User", back_populates="attachments")
    note: Mapped["Note"] = relationship("Note", back_populates="attachments")


# ---------------------------------------------------------------------------
# note_history  (Could tier – table always created, feature gated elsewhere)
# ---------------------------------------------------------------------------
class NoteHistory(Base):
    __tablename__ = "note_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    note_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notes.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    note: Mapped["Note"] = relationship("Note", back_populates="history")
