"""
Procedural Memory — Learned workflows and task patterns.

Stores successful task sequences so Maxis knows HOW to do things she's
done before, and can apply those patterns to similar future tasks.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from loguru import logger
from sqlalchemy import create_engine, Column, String, Float, Text, Integer
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from maxis.config import SQLITE_DIR


class Base(DeclarativeBase):
    pass


class Procedure(Base):
    """A learned workflow or task pattern."""
    __tablename__ = "procedures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, default="")
    steps_json = Column(Text, default="[]")  # JSON list of step descriptions
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_used = Column(Float, default=0.0)
    created_at = Column(Float, default=0.0)
    tags_json = Column(Text, default="[]")  # JSON list of tags for matching


class ProceduralMemory:
    """
    Stores and retrieves learned task patterns.

    When Maxis successfully completes a multi-step task, the procedure
    is stored here. Next time a similar task comes up, she can retrieve
    and follow the same pattern.
    """

    def __init__(self):
        self._engine = None
        self._session_factory = None
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return

        from maxis.config import get_config
        config = get_config()

        if config.cloud.database_url:
            db_url = config.cloud.database_url
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
        else:
            db_path = SQLITE_DIR / "procedures.db"
            db_url = f"sqlite:///{db_path}"

        self._engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine)

        with self._session_factory() as session:
            count = session.query(Procedure).count()
        logger.info(f"Procedural memory loaded: {count} procedures")
        self._initialized = True

    async def store_procedure(
        self,
        name: str,
        description: str,
        steps: list[str],
        tags: list[str] | None = None,
    ):
        """Store or update a learned procedure."""
        if not self._initialized:
            await self.initialize()

        now = time.time()

        with self._session_factory() as session:
            existing = session.query(Procedure).filter_by(name=name).first()

            if existing:
                existing.description = description
                existing.steps_json = json.dumps(steps)
                existing.success_count += 1
                existing.last_used = now
                existing.tags_json = json.dumps(tags or [])
            else:
                proc = Procedure(
                    name=name,
                    description=description,
                    steps_json=json.dumps(steps),
                    success_count=1,
                    last_used=now,
                    created_at=now,
                    tags_json=json.dumps(tags or []),
                )
                session.add(proc)

            session.commit()

        logger.debug(f"Stored procedure: {name}")

    async def find_procedure(self, query: str) -> Optional[dict]:
        """Find the best matching procedure for a task description."""
        if not self._initialized:
            await self.initialize()

        query_lower = query.lower()

        with self._session_factory() as session:
            procedures = session.query(Procedure).all()

            best_match = None
            best_score = 0

            for proc in procedures:
                # Simple keyword matching (semantic matching added later)
                score = 0
                tags = json.loads(proc.tags_json)
                for tag in tags:
                    if tag.lower() in query_lower:
                        score += 2
                if proc.name.lower() in query_lower:
                    score += 3
                # Boost by success rate
                total = proc.success_count + proc.failure_count
                if total > 0:
                    score *= (proc.success_count / total)

                if score > best_score:
                    best_score = score
                    best_match = proc

            if best_match and best_score > 0:
                return {
                    "name": best_match.name,
                    "description": best_match.description,
                    "steps": json.loads(best_match.steps_json),
                    "success_count": best_match.success_count,
                    "score": best_score,
                }

        return None

    async def record_outcome(self, name: str, success: bool):
        """Record whether a procedure succeeded or failed."""
        if not self._initialized:
            await self.initialize()

        with self._session_factory() as session:
            proc = session.query(Procedure).filter_by(name=name).first()
            if proc:
                if success:
                    proc.success_count += 1
                else:
                    proc.failure_count += 1
                proc.last_used = time.time()
                session.commit()
