"""
Orchestrator — The main request pipeline.

This is the central nervous system of Maxis. Every input — text, voice,
visual event — flows through here. The orchestrator coordinates:

1. Perceive: understand what just happened (parse input, identify person)
2. Remember: retrieve relevant memories across all layers
3. Think: build context, route to LLM, generate response
4. Feel: update emotional state based on interaction (Phase 4)
5. Respond: deliver response via appropriate channel
6. Store: save the interaction to memory
"""

from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from loguru import logger

from maxis.config import get_config
from maxis.core.identity import build_system_prompt
from maxis.emotion.state import EmotionalState
from maxis.intelligence.llm_router import LLMRouter
from maxis.memory.manager import MemoryManager
from maxis.memory.compression import MemoryCompressor
from maxis.memory.chat_history import ChatHistoryStore


class Orchestrator:
    """
    Central orchestrator for the Maxis system.

    Coordinates all subsystems to process inputs and generate responses.
    """

    def __init__(self):
        self.memory = MemoryManager()
        self.llm = LLMRouter()
        self.emotional_state = EmotionalState()
        self.compressor: Optional[MemoryCompressor] = None
        self.chat_history = ChatHistoryStore()

        # Per-user working memory isolation
        self._working_memories: dict[str, 'WorkingMemory'] = {}

        # Current session state
        self._current_person_id: Optional[str] = None
        self._session_start: float = time.time()
        self._initialized = False

    async def initialize(self):
        """Initialize all subsystems."""
        if self._initialized:
            return

        logger.info("═" * 60)
        logger.info("  MAXIS — Initializing...")
        logger.info("═" * 60)

        # Initialize memory
        await self.memory.initialize()

        # Initialize chat history
        await self.chat_history.initialize()

        # Initialize LLM
        await self.llm.initialize()

        # Load previous emotional state if it exists
        await self._load_emotional_state()

        # Start memory compressor
        config = get_config()
        self.compressor = MemoryCompressor(self.memory)
        await self.compressor.start(
            interval_hours=config.memory.compression_interval_hours
        )

        # Check for primary user
        primary = await self.memory.persons.get_primary_user()
        if primary:
            self._current_person_id = primary["id"]
            logger.info(f"Primary user loaded: {primary['name']}")
        else:
            logger.info("No primary user registered. First-run setup pending.")

        self._initialized = True
        logger.info("═" * 60)
        logger.info("  MAXIS — Online and ready.")
        logger.info("═" * 60)

    async def process_message(
        self,
        message: str,
        person_id: str | None = None,
        is_voice: bool = False,
        is_creator: bool = False,
    ) -> str:
        """
        Process a text message through the full pipeline.

        This is the main entry point for all text-based interaction.
        """
        if not self._initialized:
            await self.initialize()

        active_person = person_id or self._current_person_id
        start_time = time.time()

        # ── 1. Get or create per-user working memory ────────────────────
        if active_person and active_person not in self._working_memories:
            from maxis.memory.working import WorkingMemory
            self._working_memories[active_person] = WorkingMemory()
        
        working = self._working_memories.get(active_person, self.memory.working)

        # ── 2. Add to working memory ────────────────────────────────────
        working.add_user_message(message, active_person)

        # ── 2. Retrieve relevant memories ────────────────────────────────
        memory_context = await self.memory.recall(
            query=message,
            person_id=active_person,
            is_creator=is_creator,
        )

        # ── 3. Build person context ──────────────────────────────────────
        person_context = ""
        if active_person:
            person_context = await self.memory.persons.get_context_for_person(active_person)

        # ── 4. Build time context ────────────────────────────────────────
        IST = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(IST)
        time_context = (
            f"Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')} IST. "
            f"Session has been active for {(time.time() - self._session_start) / 60:.0f} minutes."
        )

        # ── 5. Build system prompt ───────────────────────────────────────
        system_prompt = build_system_prompt(
            emotional_state=self.emotional_state,
            person_context=person_context,
            memory_context=memory_context,
            time_context=time_context,
        )
        
        if is_voice:
            system_prompt += "\n\n[SYSTEM DIRECTIVE]: The user just spoke to you via microphone instead of typing. Keep your response conversational, natural, and relatively brief so it sounds good when read aloud."

        # ── 6. Generate response ─────────────────────────────────────────
        messages = working.get_messages()
        response = await self.llm.generate(
            messages=messages,
            system_prompt=system_prompt,
        )

        # ── 7. Add response to working memory ───────────────────────────
        working.add_assistant_message(response)

        # ── 8. Store interaction in episodic memory ──────────────────────
        await self.memory.store_interaction(
            user_message=message,
            assistant_response=response,
            person_id=active_person,
        )

        # ── 9. Update emotional state (stub for Phase 1) ────────────────
        # Phase 4 will add the causal reasoning engine here
        self.emotional_state.cognitive_engagement = min(
            1.0, self.emotional_state.cognitive_engagement + 0.05
        )

        elapsed = time.time() - start_time
        logger.info(f"Response generated in {elapsed:.2f}s ({len(response)} chars)")

        return response

    async def register_primary_user(self, name: str) -> str:
        """Register the primary user (first-run setup)."""
        person_id = await self.memory.persons.create_person(
            name=name,
            is_primary_user=True,
        )
        self._current_person_id = person_id

        # Store as a semantic fact
        await self.memory.semantic.store_fact(
            subject=person_id,
            predicate="is_primary_user",
            obj="true",
        )
        await self.memory.semantic.store_fact(
            subject=person_id,
            predicate="name",
            obj=name,
        )

        logger.info(f"Primary user registered: {name} ({person_id[:8]})")
        return person_id

    async def register_user(self, name: str) -> str:
        """Register a secondary user (friend/guest)."""
        person_id = await self.memory.persons.create_person(
            name=name,
            is_primary_user=False,
        )
        self._current_person_id = person_id

        await self.memory.semantic.store_fact(
            subject=person_id,
            predicate="name",
            obj=name,
        )

        logger.info(f"User registered: {name} ({person_id[:8]})")
        return person_id

    async def set_current_person(self, person_id: str):
        """Set who Maxis is currently talking to."""
        self._current_person_id = person_id

    async def login_user(self, username: str, password: str) -> tuple[dict | None, bool]:
        """
        Authenticate a user via username/password.
        Returns (person_dict, is_creator) or (None, False) on failure.
        """
        person, is_creator = await self.memory.persons.authenticate(username, password)

        if person:
            self._current_person_id = person["id"]

            # Store semantic facts
            await self.memory.semantic.store_fact(
                subject=person["id"],
                predicate="name",
                obj=person["name"],
            )
            if is_creator:
                await self.memory.semantic.store_fact(
                    subject=person["id"],
                    predicate="is_primary_user",
                    obj="true",
                )
                logger.info(f"Creator authenticated: {username}")
            else:
                logger.info(f"User authenticated: {username} ({person['id'][:8]})")

        return person, is_creator

    async def _load_emotional_state(self):
        """Load the last saved emotional state."""
        # For Phase 1, start with defaults
        # Phase 4 will persist and restore state
        self.emotional_state = EmotionalState()

    async def _save_emotional_state(self):
        """Save current emotional state for persistence."""
        # Phase 4 implementation
        pass

    def get_status(self) -> dict:
        """Get full system status."""
        return {
            "online": self._initialized,
            "emotional_state": self.emotional_state.summary(),
            "current_person": self._current_person_id,
            "session_duration_minutes": (time.time() - self._session_start) / 60,
            "memory": self.memory.get_status(),
            "llm": self.llm.get_status(),
        }

    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down Maxis...")

        await self._save_emotional_state()

        if self.compressor:
            await self.compressor.stop()

        await self.llm.shutdown()

        logger.info("Maxis offline. Goodnight.")
