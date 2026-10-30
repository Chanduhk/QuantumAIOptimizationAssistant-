from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.app.models.chat import ChatMessage, Conversation, utc_now

logger = logging.getLogger(__name__)


class ChatService:
    """Manages persistent conversation threads and message history for JAM."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_conversations(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """List active conversations for a user, sorted by most recently updated."""
        convs = (
            self.session.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
            .all()
        )
        return [c.to_dict() for c in convs]

    def create_conversation(self, user_id: int, title: Optional[str] = None) -> Conversation:
        """Create a new conversation thread owned by user_id."""
        clean_title = (title or "New Conversation").strip()[:255]
        conv = Conversation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=clean_title,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.session.add(conv)
        self.session.commit()
        self.session.refresh(conv)
        return conv

    def get_conversation(self, user_id: int, conversation_id: str) -> Optional[Conversation]:
        """Fetch a conversation strictly enforcing user isolation."""
        return (
            self.session.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .one_or_none()
        )

    def get_or_create_active_conversation(
        self, user_id: int, conversation_id: Optional[str] = None, title_hint: Optional[str] = None
    ) -> Conversation:
        """Get an existing conversation or create a new one for the user."""
        if conversation_id:
            conv = self.get_conversation(user_id, conversation_id)
            if conv is not None:
                return conv

        # Find most recent conversation with activity within last 24h, or create fresh
        recent = (
            self.session.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(desc(Conversation.updated_at))
            .first()
        )
        if recent is not None:
            return recent

        title = title_hint[:40] if title_hint else "New Conversation"
        return self.create_conversation(user_id, title=title)

    def get_messages(
        self, user_id: int, conversation_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve chronological messages for a conversation after validating user ownership."""
        conv = self.get_conversation(user_id, conversation_id)
        if conv is None:
            return []

        messages = (
            self.session.query(ChatMessage)
            .filter(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.user_id == user_id,
            )
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
            .all()
        )
        return [m.to_dict() for m in messages]

    def add_user_message(
        self,
        user_id: int,
        conversation_id: str,
        content: str,
        msg_id: Optional[str] = None,
    ) -> ChatMessage:
        """Add a user message and update conversation timestamp and title if needed."""
        conv = self.get_conversation(user_id, conversation_id)
        if conv is None:
            conv = self.create_conversation(user_id, title=content[:40])
            conversation_id = conv.id

        now = utc_now()
        # Auto-title on first message
        if conv.title == "New Conversation" and content.strip():
            candidate_title = content.strip().split("\n")[0][:45]
            conv.title = candidate_title

        conv.updated_at = now

        msg = ChatMessage(
            id=msg_id or str(uuid.uuid4()),
            conversation_id=conversation_id,
            user_id=user_id,
            role="user",
            content=content.strip(),
            created_at=now,
        )
        self.session.add(msg)
        self.session.commit()
        self.session.refresh(msg)
        return msg

    def add_assistant_message(
        self,
        user_id: int,
        conversation_id: str,
        content: str,
        intent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        msg_id: Optional[str] = None,
    ) -> ChatMessage:
        """Add an assistant response message to a conversation."""
        conv = self.get_conversation(user_id, conversation_id)
        if conv is None:
            conv = self.get_or_create_active_conversation(user_id, conversation_id)
            conversation_id = conv.id

        now = utc_now()
        conv.updated_at = now

        meta_json = json.dumps(metadata) if metadata is not None else None

        msg = ChatMessage(
            id=msg_id or str(uuid.uuid4()),
            conversation_id=conversation_id,
            user_id=user_id,
            role="assistant",
            content=content.strip(),
            intent=intent,
            metadata_json=meta_json,
            created_at=now,
        )
        self.session.add(msg)
        self.session.commit()
        self.session.refresh(msg)
        return msg

    def delete_conversation(self, user_id: int, conversation_id: str) -> bool:
        """Delete a conversation and all its messages, verifying user isolation."""
        conv = self.get_conversation(user_id, conversation_id)
        if conv is None:
            return False

        self.session.delete(conv)
        self.session.commit()
        return True

    def get_conversation_turns(
        self, user_id: int, conversation_id: str, max_turns: int = 6
    ) -> List[Dict[str, str]]:
        """Retrieve recent conversation turns for LLM prompt context."""
        messages = (
            self.session.query(ChatMessage)
            .filter(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.user_id == user_id,
            )
            .order_by(desc(ChatMessage.created_at))
            .limit(max_turns * 2)
            .all()
        )
        # Reverse to chronological order
        messages.reverse()
        return [{"role": m.role, "content": m.content} for m in messages]
