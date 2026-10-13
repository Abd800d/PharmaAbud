"""AI assistant: conversations, messages, citations (RAG provenance)."""
from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import Timestamped, UUIDPk, utcnow


class AiConversation(Base, UUIDPk, Timestamped):
    __tablename__ = "ai_conversations"

    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    device_id: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)

    messages: Mapped[list["AiMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", lazy="selectin"
    )


class AiMessage(Base, UUIDPk, Timestamped):
    __tablename__ = "ai_messages"

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    provider: Mapped[str] = mapped_column(String(48), default="extractive", nullable=False)
    safety_note: Mapped[str] = mapped_column(Text, default="", nullable=False)

    conversation: Mapped[AiConversation] = relationship(back_populates="messages", lazy="selectin")
    citations: Mapped[list["AiCitation"]] = relationship(
        back_populates="message", cascade="all, delete-orphan", lazy="selectin"
    )


class AiCitation(Base, UUIDPk):
    """A citation is recorded ONLY for sources actually retrieved (§43)."""

    __tablename__ = "ai_citations"

    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    source_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    section: Mapped[str] = mapped_column(String(96), default="", nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), default="", nullable=False)
    quote: Mapped[str] = mapped_column(Text, default="", nullable=False)
    last_verified_date: Mapped[str] = mapped_column(String(64), default="", nullable=False)

    message: Mapped[AiMessage] = relationship(back_populates="citations", lazy="selectin")
