from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Conversation(Base):
    """A persistent conversation thread for the JAM assistant."""

    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(255), nullable=False, default="New Conversation")
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    messages = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": len(self.messages) if self.messages else 0,
        }


class ChatMessage(Base):
    """An individual user command or assistant response in a conversation."""

    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(Integer, nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    intent = Column(String(60), nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON-encoded result/payload
    created_at = Column(DateTime, nullable=False, default=utc_now)

    conversation = relationship("Conversation", back_populates="messages")

    def to_dict(self) -> dict:
        import json
        meta = None
        if self.metadata_json:
            try:
                meta = json.loads(self.metadata_json)
            except Exception:
                meta = None
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "intent": self.intent,
            "metadata": meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
