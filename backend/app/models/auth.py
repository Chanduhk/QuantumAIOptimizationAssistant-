from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from .base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(320), nullable=False, unique=True, index=True)
    password_hash = Column(String(256), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash = Column(String(64), primary_key=True)
    csrf_hash = Column(String(64), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True)
