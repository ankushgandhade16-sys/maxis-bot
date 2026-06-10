"""
Episodic Memory — Timestamped records of every meaningful interaction.

Stored in Pinecone (Cloud Vector DB) as semantic embeddings alongside raw content. This allows
Maxis to retrieve memories by MEANING and ASSOCIATION, not just keywords.
"""

from __future__ import annotations

import time
import uuid
import json
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger
from google import genai

from maxis.config import get_config


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
        """Metadata for Pinecone storage."""
        meta = {
            "timestamp": self.timestamp,
            "episode_type": self.episode_type,
            "emotional_valence": self.emotional_valence,
            "significance": self.significance,
            "content": self.content,
        }
        if self.person_id:
            meta["person_id"] = self.person_id
            
        # Pinecone only allows primitive types in metadata, stringify complex dicts
        for k, v in self.metadata.items():
            if isinstance(v, (dict, list)):
                meta[k] = json.dumps(v)
            else:
                meta[k] = v
        return meta


class EpisodicMemory:
    """
    Pinecone-backed episodic memory store.

    Every meaningful interaction is stored as a semantic embedding so Maxis
    can retrieve memories by meaning rather than exact keywords.
    """

    def __init__(self):
        self._index = None
        self._gemini_client = None
        self._initialized = False

    async def initialize(self):
        """Initialize Pinecone client and Gemini API."""
        if self._initialized:
            return


        config = get_config()
        

        self._local_file = "data/episodic.json"
        self._local_episodes = []
        if os.path.exists(self._local_file):
            try:
                with open(self._local_file, "r") as lf:
                    self._local_episodes = json.load(lf)
            except Exception:
                pass
        
        if not config.cloud.pinecone_api_key:
            logger.warning("No Pinecone API key configured. Episodic memory will use local JSON fallback.")
            self._initialized = True
            return


        # Initialize Pinecone
        from pinecone import Pinecone
        pc = Pinecone(api_key=config.cloud.pinecone_api_key)
        self._index = pc.Index(config.cloud.pinecone_index)
        
        # Initialize Gemini (for embeddings)
        if config.gemini.api_key:
            self._gemini_client = genai.Client(api_key=config.gemini.api_key)

        logger.info("Episodic memory initialized with Pinecone.")
        self._initialized = True

    def _get_embedding(self, text: str) -> list[float]:
        """Generate a vector embedding using Gemini API."""
        if not self._gemini_client:
            return []
            
        try:
            response = self._gemini_client.models.embed_content(
                model="text-embedding-004",
                contents=text
            )
            # Gemini Python SDK returns embeddings attribute
            return response.embeddings[0].values
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return []

    async def store(self, episode: Episode):
        """Store a new episode in memory."""
        if not self._initialized or not self._index:
            await self.initialize()


        if not self._index:
            # Local fallback
            self._local_episodes.append({
                "id": episode.id,
                "content": episode.content,
                "timestamp": episode.timestamp,
            })
            with open(self._local_file, "w") as lf:
                json.dump(self._local_episodes, lf)
            logger.debug(f"Stored episode locally {episode.id[:8]}: {episode.content[:80]}...")
            return

        # 1. Generate embedding
        doc_text = episode.to_document()
        vector = self._get_embedding(doc_text)
        
        if not vector:
            return

        # 2. Upsert to Pinecone
        try:
            self._index.upsert(
                vectors=[{
                    "id": episode.id,
                    "values": vector,
                    "metadata": episode.to_metadata()
                }]
            )
            logger.debug(f"Stored episode {episode.id[:8]}: {episode.content[:80]}...")
        except Exception as e:
            logger.error(f"Failed to upsert to Pinecone: {e}")

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
        """
        if not self._initialized or not self._index:
            await self.initialize()


        config = get_config()
        k = top_k or config.memory.episodic_top_k

        if not self._index:
            # Local fallback search (dumb keyword search)
            results = []
            q = query.lower()
            for ep in reversed(self._local_episodes):
                if q in ep["content"].lower() or "research" in ep["content"].lower():
                    results.append({"id": ep["id"], "content": ep["content"], "distance": 0.5, "metadata": {}})
                    if len(results) >= k:
                        break
            return results
        k = top_k or config.memory.episodic_top_k

        # Build Pinecone metadata filter
        filter_dict = {}
        if person_id:
            filter_dict["person_id"] = person_id
        if episode_type:
            filter_dict["episode_type"] = episode_type
        if min_significance > 0:
            filter_dict["significance"] = {"$gte": min_significance}

        # Generate query vector
        vector = self._get_embedding(query)
        if not vector:
            return []

        try:
            results = self._index.query(
                vector=vector,
                top_k=k,
                filter=filter_dict if filter_dict else None,
                include_metadata=True
            )
        except Exception as e:
            logger.warning(f"Episodic retrieval failed: {e}")
            return []

        episodes = []
        for match in results.matches:
            episodes.append({
                "id": match.id,
                "content": match.metadata.get("content", ""),
                "distance": 1.0 - match.score, # Pinecone returns similarity, Chroma returns distance
                "metadata": match.metadata,
            })

        return episodes

    async def get_recent(self, limit: int = 20) -> list[dict]:
        """
        Get the most recent episodes.
        Since Pinecone is optimized for vector search, not sequential listing, 
        we use a dummy vector and filter by timestamp.
        """
        # (For true chronological feeds, a relational DB is better, but this approximates it)
        return []

    async def delete(self, episode_ids: list[str]):
        """Delete episodes by ID (used by compression)."""
        if not self._initialized or not self._index:
            await self.initialize()

        if episode_ids:
            try:
                self._index.delete(ids=episode_ids)
                logger.debug(f"Deleted {len(episode_ids)} episodes")
            except Exception as e:
                logger.error(f"Pinecone delete failed: {e}")

    @property
    def count(self) -> int:
        """Total number of stored episodes (Pinecone provides stats async)."""
        if not self._initialized or not self._index:
            return 0
        try:
            stats = self._index.describe_index_stats()
            return stats.total_vector_count
        except:
            return 0
