"""
Episodic Memory — Timestamped records of every meaningful interaction.

Stored in ChromaDB as semantic embeddings alongside raw content. This allows
Maxis to retrieve memories by MEANING and ASSOCIATION, not just keywords.

"Remember when we talked about my project deadline?" retrieves the right
episodes through semantic similarity, not string matching.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from maxis.config import get_config, CHROMA_DIR


@dataclass
class Episode:
    """A single episodic memory entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""  # the raw text of what happened
    summary: str = ""  # compressed summary (filled by compression)
    timestamp: float = field(default_factory=time.time)
    person_id: Optional[str] = None  # who was involved
    episode_type: str = "conversation"  # conversation, observation, event, task
    emotional_valence: float = 0.0  # -1 negative ... +1 positive
    significance: float = 0.5  # 0 trivial ... 1 critical
    metadata: dict = field(default_factory=dict)

    def to_document(self) -> str:
        """Text representation for embedding."""
        return self.summary if self.summary else self.content

    def to_metadata(self) -> dict:
        """Metadata for ChromaDB storage."""
        meta = {
            "timestamp": self.timestamp,
            "episode_type": self.episode_type,
            "emotional_valence": self.emotional_valence,
            "significance": self.significance,
        }
        if self.person_id:
            meta["person_id"] = self.person_id
        meta.update(self.metadata)
        return meta


class EpisodicMemory:
    """
    ChromaDB-backed episodic memory store.

    Every meaningful interaction is stored as a semantic embedding so Maxis
    can retrieve memories by meaning rather than exact keywords.
    """

    def __init__(self):
        self._client = None
        self._collection = None
        self._initialized = False

    async def initialize(self):
        """Initialize ChromaDB client and collection."""
        if self._initialized:
            return

        import chromadb
        from chromadb.config import Settings

        config = get_config()

        self._client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )

        # Use the default embedding function (all-MiniLM-L6-v2)
        # ChromaDB downloads and caches this automatically
        self._collection = self._client.get_or_create_collection(
            name=config.memory.episodic_collection,
            metadata={"hnsw:space": "cosine"},
        )

        count = self._collection.count()
        logger.info(f"Episodic memory initialized with {count} episodes")
        self._initialized = True

    async def store(self, episode: Episode):
        """Store a new episode in memory."""
        if not self._initialized:
            await self.initialize()

        self._collection.add(
            ids=[episode.id],
            documents=[episode.to_document()],
            metadatas=[episode.to_metadata()],
        )
        logger.debug(f"Stored episode {episode.id[:8]}: {episode.content[:80]}...")

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        person_id: str | None = None,
        episode_type: str | None = None,
        min_significance: float = 0.0,
    ) -> list[dict]:
        """
        Retrieve episodes by semantic similarity to a query.

        Returns list of dicts with 'id', 'content', 'distance', 'metadata'.
        """
        if not self._initialized:
            await self.initialize()

        config = get_config()
        k = top_k or config.memory.episodic_top_k

        # Build where filter
        where_filter = {}
        conditions = []

        if person_id:
            conditions.append({"person_id": {"$eq": person_id}})
        if episode_type:
            conditions.append({"episode_type": {"$eq": episode_type}})
        if min_significance > 0:
            conditions.append({"significance": {"$gte": min_significance}})

        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(k, self._collection.count() or 1),
                where=where_filter if where_filter else None,
            )
        except Exception as e:
            logger.warning(f"Episodic retrieval failed: {e}")
            return []

        episodes = []
        if results and results["ids"] and results["ids"][0]:
            for i, eid in enumerate(results["ids"][0]):
                episodes.append({
                    "id": eid,
                    "content": results["documents"][0][i],
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })

        return episodes

    async def get_recent(self, limit: int = 20) -> list[dict]:
        """Get the most recent episodes by timestamp."""
        if not self._initialized:
            await self.initialize()

        count = self._collection.count()
        if count == 0:
            return []

        # ChromaDB doesn't support ORDER BY, so we fetch all and sort
        # For large collections, this should use the SQLite index instead
        results = self._collection.get(
            limit=min(limit * 3, count),  # over-fetch to account for ordering
            include=["documents", "metadatas"],
        )

        if not results["ids"]:
            return []

        episodes = []
        for i, eid in enumerate(results["ids"]):
            episodes.append({
                "id": eid,
                "content": results["documents"][i],
                "metadata": results["metadatas"][i],
            })

        # Sort by timestamp descending
        episodes.sort(key=lambda e: e["metadata"].get("timestamp", 0), reverse=True)
        return episodes[:limit]

    async def delete(self, episode_ids: list[str]):
        """Delete episodes by ID (used by compression)."""
        if not self._initialized:
            await self.initialize()

        if episode_ids:
            self._collection.delete(ids=episode_ids)
            logger.debug(f"Deleted {len(episode_ids)} episodes")

    @property
    def count(self) -> int:
        """Total number of stored episodes."""
        if not self._initialized:
            return 0
        return self._collection.count()
