"""
Semantic Memory — Structured knowledge graph.

Facts, relationships, and knowledge extracted from episodes over time.
Maxis knows your birthday not because she searched for it, but because
she extracted it from conversation and stored it as a structured fact.

Uses NetworkX for in-memory graph operations with SQLite persistence.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

import networkx as nx
from loguru import logger
from sqlalchemy import create_engine, Column, String, Float, Text, Integer
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from maxis.config import SQLITE_DIR


# ── SQLite ORM ───────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class KnowledgeFact(Base):
    """A single fact in the knowledge graph, persisted to SQLite."""
    __tablename__ = "knowledge_facts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject = Column(String, nullable=False, index=True)
    predicate = Column(String, nullable=False, index=True)
    obj = Column(String, nullable=False)  # 'object' is reserved
    confidence = Column(Float, default=1.0)
    source = Column(String, default="conversation")  # where this fact came from
    timestamp = Column(Float, default=0.0)
    metadata_json = Column(Text, default="{}")


class SemanticMemory:
    """
    Knowledge graph backed by NetworkX + SQLite.

    Stores structured facts as (subject, predicate, object) triples.
    Examples:
        ("user", "birthday", "March 15")
        ("user", "prefers", "dark_mode")
        ("user", "works_on", "machine_learning_project")
        ("alice", "relationship_to_user", "sister")
    """

    def __init__(self):
        self._graph: nx.DiGraph = nx.DiGraph()
        self._engine = None
        self._session_factory = None
        self._initialized = False

    async def initialize(self):
        """Load knowledge graph from SQLite into NetworkX."""
        if self._initialized:
            return

        db_path = SQLITE_DIR / "knowledge.db"
        self._engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine)

        # Load all facts into the graph
        with self._session_factory() as session:
            facts = session.query(KnowledgeFact).all()
            for fact in facts:
                self._graph.add_edge(
                    fact.subject,
                    fact.obj,
                    predicate=fact.predicate,
                    confidence=fact.confidence,
                    source=fact.source,
                    timestamp=fact.timestamp,
                )

        logger.info(
            f"Semantic memory loaded: {self._graph.number_of_nodes()} entities, "
            f"{self._graph.number_of_edges()} facts"
        )
        self._initialized = True

    async def store_fact(
        self,
        subject: str,
        predicate: str,
        obj: str,
        confidence: float = 1.0,
        source: str = "conversation",
        metadata: dict | None = None,
    ):
        """
        Store a knowledge fact. If the same (subject, predicate) exists,
        update it rather than duplicating.
        """
        if not self._initialized:
            await self.initialize()

        now = time.time()

        # Update graph
        self._graph.add_edge(
            subject, obj,
            predicate=predicate,
            confidence=confidence,
            source=source,
            timestamp=now,
        )

        # Persist to SQLite
        with self._session_factory() as session:
            # Check for existing fact with same subject+predicate
            existing = session.query(KnowledgeFact).filter_by(
                subject=subject, predicate=predicate
            ).first()

            if existing:
                existing.obj = obj
                existing.confidence = confidence
                existing.source = source
                existing.timestamp = now
                existing.metadata_json = json.dumps(metadata or {})
            else:
                fact = KnowledgeFact(
                    subject=subject,
                    predicate=predicate,
                    obj=obj,
                    confidence=confidence,
                    source=source,
                    timestamp=now,
                    metadata_json=json.dumps(metadata or {}),
                )
                session.add(fact)

            session.commit()

        logger.debug(f"Stored fact: ({subject}) --[{predicate}]--> ({obj})")

    async def query_subject(self, subject: str) -> list[dict]:
        """Get all facts about a subject."""
        if not self._initialized:
            await self.initialize()

        facts = []
        if subject in self._graph:
            for _, target, data in self._graph.out_edges(subject, data=True):
                facts.append({
                    "subject": subject,
                    "predicate": data.get("predicate", ""),
                    "object": target,
                    "confidence": data.get("confidence", 1.0),
                })
        return facts

    async def query_predicate(self, predicate: str) -> list[dict]:
        """Get all facts with a given predicate (e.g., all 'birthday' facts)."""
        if not self._initialized:
            await self.initialize()

        facts = []
        for u, v, data in self._graph.edges(data=True):
            if data.get("predicate") == predicate:
                facts.append({
                    "subject": u,
                    "predicate": predicate,
                    "object": v,
                    "confidence": data.get("confidence", 1.0),
                })
        return facts

    async def get_person_facts(self, person_id: str) -> str:
        """Get a readable summary of all known facts about a person."""
        facts = await self.query_subject(person_id)
        if not facts:
            return ""

        lines = [f"Known facts about {person_id}:"]
        for f in facts:
            lines.append(f"  - {f['predicate']}: {f['object']}")
        return "\n".join(lines)

    async def search(self, query: str) -> list[dict]:
        """
        Simple text search across all facts.
        For semantic search, use episodic memory instead.
        """
        if not self._initialized:
            await self.initialize()

        query_lower = query.lower()
        results = []

        for u, v, data in self._graph.edges(data=True):
            predicate = data.get("predicate", "")
            if (query_lower in u.lower()
                    or query_lower in v.lower()
                    or query_lower in predicate.lower()):
                results.append({
                    "subject": u,
                    "predicate": predicate,
                    "object": v,
                    "confidence": data.get("confidence", 1.0),
                })

        return results

    async def delete_fact(self, subject: str, predicate: str):
        """Remove a specific fact."""
        if not self._initialized:
            await self.initialize()

        # Remove from graph
        to_remove = []
        for _, target, data in self._graph.out_edges(subject, data=True):
            if data.get("predicate") == predicate:
                to_remove.append((subject, target))
        for edge in to_remove:
            self._graph.remove_edge(*edge)

        # Remove from SQLite
        with self._session_factory() as session:
            session.query(KnowledgeFact).filter_by(
                subject=subject, predicate=predicate
            ).delete()
            session.commit()

    @property
    def fact_count(self) -> int:
        return self._graph.number_of_edges()

    @property
    def entity_count(self) -> int:
        return self._graph.number_of_nodes()
