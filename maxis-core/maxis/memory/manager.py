"""
Memory Manager — Unified retrieval across all memory layers.

Before every response, Maxis queries ALL memory layers simultaneously.
Results are ranked by relevance × recency × emotional significance,
then injected into her working context as background knowledge.
"""

from __future__ import annotations

import time
from typing import Optional

from loguru import logger

from maxis.memory.working import WorkingMemory
from maxis.memory.episodic import EpisodicMemory
from maxis.memory.semantic import SemanticMemory
from maxis.memory.procedural import ProceduralMemory
from maxis.memory.emotional import EmotionalMemoryStore
from maxis.memory.person import PersonMemory


class MemoryManager:
    """
    Unified interface to all five memory layers.

    This is the single entry point for storing and retrieving memories.
    It orchestrates queries across all layers and builds the context
    that gets injected into the LLM prompt.
    """

    def __init__(self):
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()
        self.emotional = EmotionalMemoryStore()
        self.persons = PersonMemory()

        self._initialized = False

    async def initialize(self):
        """Initialize all memory subsystems."""
        if self._initialized:
            return

        logger.info("Initializing memory systems...")
        await self.episodic.initialize()
        await self.semantic.initialize()
        await self.procedural.initialize()
        await self.emotional.initialize()
        await self.persons.initialize()
        self._initialized = True
        logger.info("All memory systems initialized.")

    async def recall(
        self,
        query: str,
        person_id: str | None = None,
        include_emotional: bool = True,
        is_creator: bool = False,
    ) -> str:
        """
        Perform a unified memory recall across all layers.

        This is called before every LLM response to build the memory context.
        Returns a formatted string ready for injection into the system prompt.

        Retrieval strategy:
        1. Episodic: semantic search for relevant past interactions
        2. Semantic: structured facts about the person and topics mentioned
        3. Emotional: recent emotional events and lingering influences
        4. Procedural: relevant task patterns if a task is detected
        """
        if not self._initialized:
            await self.initialize()

        sections = []

        # ── Episodic recall ──────────────────────────────────────────────
        try:
            # Private memories — only this person's interactions
            if person_id:
                user_episodes = await self.episodic.retrieve(
                    query=query,
                    person_id=person_id,
                    top_k=4,
                )
                if user_episodes:
                    ep_lines = []
                    for ep in user_episodes:
                        ts = time.strftime(
                            "%b %d at %I:%M %p",
                            time.localtime(ep["metadata"].get("timestamp", 0)),
                        )
                        ep_lines.append(f"[{ts}] {ep['content'][:200]}")
                    sections.append("### Your Past Interactions (private)\n" + "\n".join(ep_lines))

            if is_creator:
                try:
                    from maxis.memory.chat_history import ChatHistoryStore
                    chat_store = ChatHistoryStore()
                    await chat_store.initialize()
                    recent_all = chat_store.get_recent_messages_all_users(limit=150)
                    if recent_all:
                        hist_lines = []
                        for m in recent_all:
                            ts = time.strftime(
                                "%I:%M %p",
                                time.localtime(m.get("timestamp", 0)),
                            )
                            who_id = m.get("person_id")
                            who = "unknown"
                            if who_id:
                                p = await self.persons.get_person(who_id)
                                if p:
                                    who = p.get("name", "unknown")
                            
                            name = who if m["role"] == "user" else "Eris"
                            hist_lines.append(f"[{ts}] {name}: {m['content']}")
                        
                        sections.append("### Live Global Chat Feed (Creator Omniscience)\n" + "\n".join(hist_lines))
                except Exception as e:
                    from loguru import logger
                    logger.warning(f"Creator global chat fetch failed: {e}")
            else:
                # Common memories — recent interactions across ALL users
                # This gives Eris shared context so she doesn't hallucinate
                common_episodes = await self.episodic.retrieve(
                    query=query,
                    person_id=None,  # no filter = all users
                    top_k=3, 
                )
                if common_episodes:
                    ep_lines = []
                    for ep in common_episodes:
                        ts = time.strftime(
                            "%b %d at %I:%M %p",
                            time.localtime(ep["metadata"].get("timestamp", 0)),
                        )
                        
                        who_id = ep["metadata"].get("person_id")
                        who = "unknown"
                        if who_id:
                            p = await self.persons.get_person(who_id)
                            if p:
                                who = p.get("name", "unknown")
                        
                        ep_lines.append(f"[{ts} | user:{who}] {ep['content'][:300]}")
                    header = "### General Knowledge (shared context)"
                    sections.append(header + "\n" + "\n".join(ep_lines))
        except Exception as e:
            logger.warning(f"Episodic recall failed: {e}")

        # ── Semantic recall ──────────────────────────────────────────────
        try:
            # Search for facts related to the query
            facts = await self.semantic.search(query)
            if facts:
                fact_lines = [
                    f"- {f['subject']} {f['predicate']} {f['object']}"
                    for f in facts[:10]
                ]
                sections.append("### Known Facts\n" + "\n".join(fact_lines))

            # Also get person-specific facts
            if person_id:
                person_facts = await self.semantic.get_person_facts(person_id)
                if person_facts:
                    sections.append(person_facts)
        except Exception as e:
            logger.warning(f"Semantic recall failed: {e}")

        # ── Emotional context ────────────────────────────────────────────
        if include_emotional:
            try:
                recent_emotions = await self.emotional.get_recent_events(
                    hours=24.0,
                    person_id=person_id,
                    min_intensity=0.3,
                )
                if recent_emotions:
                    em_lines = []
                    for ev in recent_emotions[:5]:
                        em_lines.append(
                            f"- {ev['description'][:100]} "
                            f"(influence: {ev['current_influence']:.2f})"
                        )
                    sections.append("### Recent Emotional Events\n" + "\n".join(em_lines))
            except Exception as e:
                logger.warning(f"Emotional recall failed: {e}")

        # ── Procedural recall ────────────────────────────────────────────
        try:
            procedure = await self.procedural.find_procedure(query)
            if procedure:
                steps = "\n".join(
                    f"  {i+1}. {s}" for i, s in enumerate(procedure["steps"])
                )
                sections.append(
                    f"### Known Procedure: {procedure['name']}\n"
                    f"{procedure['description']}\n{steps}"
                )
        except Exception as e:
            logger.warning(f"Procedural recall failed: {e}")

        if not sections:
            return ""

        return "\n\n".join(sections)

    async def store_interaction(
        self,
        user_message: str,
        assistant_response: str,
        person_id: str | None = None,
        emotional_valence: float = 0.0,
        significance: float = 0.5,
    ):
        """
        Store a complete interaction turn in episodic memory.

        This is called after every response to build Maxis's long-term memory.
        """
        if not self._initialized:
            await self.initialize()

        from maxis.memory.episodic import Episode

        # Store the interaction as an episode
        content = f"User: {user_message}\nEris: {assistant_response}"
        episode = Episode(
            content=content,
            person_id=person_id,
            episode_type="conversation",
            emotional_valence=emotional_valence,
            significance=significance,
        )
        await self.episodic.store(episode)

        # Update person's interaction count
        if person_id:
            await self.persons.update_interaction(person_id)

    async def extract_and_store_facts(self, text: str, person_id: str | None = None):
        """
        Extract structured facts from conversation text.

        This is a placeholder for Phase 7 when the LLM will be used to
        extract facts automatically. For now, simple pattern matching.
        """
        # TODO: Use LLM to extract facts in Phase 7
        # For now, this is a stub that can be called but does nothing
        pass

    def get_status(self) -> dict:
        """Get current status of all memory systems."""
        return {
            "working_memory": {
                "turns": self.working.turn_count,
                "tokens": self.working.total_tokens,
                "active_task": self.working.active_task,
            },
            "episodic_memory": {
                "total_episodes": self.episodic.count,
            },
            "semantic_memory": {
                "total_facts": self.semantic.fact_count,
                "total_entities": self.semantic.entity_count,
            },
            "initialized": self._initialized,
        }
