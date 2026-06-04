"""
Chat History — Persistent conversation sessions.

Each user has multiple chat sessions. Messages within each session
are stored so users can browse and revisit past conversations.
The creator gets access to ALL sessions across ALL users.
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from loguru import logger
from sqlalchemy import create_engine, Column, String, Float, Text, Integer
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from maxis.config import SQLITE_DIR


class Base(DeclarativeBase):
    pass


class ChatSession(Base):
    """A conversation session."""
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True)
    person_id = Column(String, index=True)
    title = Column(String, default="New conversation")
    created_at = Column(Float, default=lambda: time.time())
    updated_at = Column(Float, default=lambda: time.time())


class ChatMessage(Base):
    """A single message within a session."""
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:16])
    session_id = Column(String, index=True)
    role = Column(String)  # 'user' or 'eris'
    content = Column(Text)
    timestamp = Column(Float, default=lambda: time.time())


class ChatHistoryStore:
    """
    Manages chat sessions and messages.

    Provides CRUD operations for conversation history,
    and special creator access to view all users' sessions.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ChatHistoryStore, cls).__new__(cls)
            cls._instance._engine = None
            cls._instance._Session = None
        return cls._instance

    def __init__(self):
        # Initialization handled by __new__ to ensure singleton properties
        pass

    async def initialize(self):
        """Initialize the chat history database."""
        if self._engine is not None:
            return  # Already initialized
        from maxis.config import get_config
        config = get_config()

        db_url = None
        if hasattr(config, 'cloud') and config.cloud and config.cloud.database_url:
            db_url = config.cloud.database_url
            logger.info("ChatHistory: Using cloud database")
        
        if not db_url:
            db_path = SQLITE_DIR / "chat_history.db"
            db_url = f"sqlite:///{db_path}"
            logger.info(f"ChatHistory: Using local SQLite at {db_path}")

        self._engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)
        logger.info("ChatHistory initialized.")

    def create_session(self, person_id: str, title: str = "New conversation") -> str:
        """Create a new chat session. Returns session ID."""
        session_id = uuid.uuid4().hex[:16]
        with self._Session() as db:
            db.add(ChatSession(
                id=session_id,
                person_id=person_id,
                title=title,
                created_at=time.time(),
                updated_at=time.time(),
            ))
            db.commit()
        logger.info(f"Created chat session {session_id} for {person_id[:8]}")
        return session_id

    def add_message(self, session_id: str, role: str, content: str):
        """Add a message to a chat session."""
        with self._Session() as db:
            db.add(ChatMessage(
                id=uuid.uuid4().hex[:16],
                session_id=session_id,
                role=role,
                content=content,
                timestamp=time.time(),
            ))
            # Update session timestamp and title if first user message
            session = db.query(ChatSession).filter_by(id=session_id).first()
            if session:
                session.updated_at = time.time()
                if role == 'user' and session.title == "New conversation":
                    # Auto-title from first message
                    session.title = content[:50] + ("..." if len(content) > 50 else "")
            db.commit()

    def get_sessions(self, person_id: str) -> list[dict]:
        """Get all chat sessions for a user, newest first."""
        with self._Session() as db:
            sessions = (
                db.query(ChatSession)
                .filter_by(person_id=person_id)
                .order_by(ChatSession.updated_at.desc())
                .all()
            )
            return [
                {
                    "id": s.id,
                    "title": s.title,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                    "person_id": s.person_id,
                }
                for s in sessions
            ]

    def get_all_sessions(self) -> list[dict]:
        """Get ALL chat sessions across ALL users (creator only)."""
        with self._Session() as db:
            sessions = (
                db.query(ChatSession)
                .order_by(ChatSession.updated_at.desc())
                .all()
            )
            return [
                {
                    "id": s.id,
                    "title": s.title,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                    "person_id": s.person_id,
                }
                for s in sessions
            ]

    def get_messages(self, session_id: str) -> list[dict]:
        """Get all messages in a session, ordered by time."""
        with self._Session() as db:
            messages = (
                db.query(ChatMessage)
                .filter_by(session_id=session_id)
                .order_by(ChatMessage.timestamp.asc())
                .all()
            )
            return [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                }
                for m in messages
            ]

    def get_recent_messages_all_users(self, limit: int = 20) -> list[dict]:
        """Get recent messages across ALL users (for creator context)."""
        with self._Session() as db:
            messages = (
                db.query(ChatMessage, ChatSession.person_id)
                .join(ChatSession, ChatMessage.session_id == ChatSession.id)
                .order_by(ChatMessage.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "role": m.ChatMessage.role,
                    "content": m.ChatMessage.content,
                    "person_id": m.person_id,
                    "timestamp": m.ChatMessage.timestamp,
                }
                for m in reversed(messages)
            ]

    def clear_all_conversations(self):
        """Delete ALL chat sessions and messages. Used for clean slate releases."""
        with self._Session() as db:
            db.query(ChatMessage).delete()
            db.query(ChatSession).delete()
            db.commit()
        logger.info("All chat conversations cleared.")
