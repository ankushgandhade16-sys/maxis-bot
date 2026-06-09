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

import json
import re
from maxis.config import get_config, DATA_DIR
from maxis.system.os_tools import get_system_stats, execute_command, fetch_url
from maxis.system.screen import capture_screen_base64
from maxis.core.daemon import ResearchDaemon
from maxis.core.identity import build_system_prompt
from maxis.emotion.state import EmotionalState
from maxis.emotion.engine import EmotionEngine
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
        self.emotion_engine: Optional[EmotionEngine] = None
        self.compressor: Optional[MemoryCompressor] = None
        self.chat_history = ChatHistoryStore()

        # Per-user working memory isolation
        self._working_memories: dict[str, 'WorkingMemory'] = {}

        # Current session state
        self._current_person_id: Optional[str] = None
        # Initialize the autonomous research daemon
        self.daemon = ResearchDaemon(self)

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

        # Initialize Emotion Engine
        self.emotion_engine = EmotionEngine(self.llm, self.memory)
        await self.emotion_engine.initialize()

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
        # Start the autonomous research daemon
        self.daemon.start()

        logger.info("═" * 60)
        logger.info("  MAXIS — Online and ready.")
        logger.info("═" * 60)

    def register_activity(self):
        """Notify the orchestrator (and daemon) that user activity occurred."""
        if hasattr(self, 'daemon'):
            self.daemon.register_activity()

    async def process_message(
        self,
        message: str,
        person_id: str | None = None,
        is_voice: bool = False,
        is_creator: bool = False,
        audio_base64: str | None = None,
        image_base64: str | None = None,
    ) -> tuple[str, str | None, str | None]:
        """
        Process a text message through the full pipeline.

        This is the main entry point for all text-based interaction.
        """
        if not self._initialized:
            await self.initialize()

        self.register_activity()
        active_person = person_id or self._current_person_id
        start_time = time.time()

        # ── 1. Get or create per-user working memory ────────────────────
        if active_person and active_person not in self._working_memories:
            from maxis.memory.working import WorkingMemory
            self._working_memories[active_person] = WorkingMemory()
        
        working = self._working_memories.get(active_person, self.memory.working)

        # ── Transcribe audio if present ─────────────────────────────────
        if audio_base64:
            try:
                # Transcribe using LLM Router's method
                transcription = await self.llm.transcribe_audio(audio_base64)
                message = transcription
            except Exception as e:
                logger.error(f"Transcription failed: {e}")
                message = "(Audio transcription failed)"

        # ── 2. Add to working memory ────────────────────────────────────
        working.add_turn("user", message, active_person, image_base64=image_base64)

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

        # ── 6. Generate response (Tool Loop) ─────────────────────────────────────────
        MAX_TOOL_LOOPS = 3
        loop_count = 0
        response = ""
        generated_images = []
        
        while loop_count < MAX_TOOL_LOOPS:
            loop_count += 1
            messages = working.get_messages()
            response = await self.llm.generate(
                messages=messages,
                system_prompt=system_prompt,
            )
            
            # Check for tool call
            tool_match = re.search(r"<tool>(.*?)</tool>", response, re.IGNORECASE)
            if tool_match:
                tool_str = tool_match.group(1).strip()
                parts = tool_str.split("|", 1)
                tool_name = parts[0].strip()
                tool_args = parts[1].strip() if len(parts) > 1 else ""
                
                logger.info(f"Tool called: {tool_name} with args: {tool_args}")
                
                # Add the assistant's intermediate step
                working.add_assistant_message(response)
                
                tool_result = ""
                image_data = None
                
                if tool_name == "get_system_stats":
                    stats = get_system_stats()
                    tool_result = json.dumps(stats)
                elif tool_name == "execute_command":
                    tool_result = execute_command(tool_args)
                elif tool_name == "fetch_url":
                    tool_result = fetch_url(tool_args)
                elif tool_name == "take_screenshot":
                    image_data = capture_screen_base64()
                    if image_data:
                        tool_result = "Screenshot attached. Please describe it or answer the user's question about it."
                    else:
                        tool_result = "Failed to capture screenshot."
                elif tool_name == "generate_image":
                    try:
                        import urllib.parse
                        prompt_encoded = urllib.parse.quote(tool_args.strip())
                        img_url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=512&height=512&nologo=true"
                        
                        tool_result = f"Image generated successfully."
                        img_html = f"![IMAGE:{img_url}]"
                        generated_images.append(img_html)
                    except Exception as e:
                        logger.error(f"Image generation failed: {e}")
                        tool_result = f"Failed to generate image: {e}"
                else:
                    tool_result = f"Unknown tool: {tool_name}"
                
                # Provide the tool result back to the LLM
                tool_msg = f"[System Tool Result]: {tool_result}"
                if image_data:
                    working.add_turn("user", tool_msg, image_base64=image_data)
                else:
                    working.add_turn("user", tool_msg)
                
                # Loop continues to let her synthesize the final answer
                continue
                
            # If no tool was called, we're done
            break

        # Extract visual directive
        visual_directive = None
        visual_match = re.search(r"<visual>(.*?)</visual>", response, re.IGNORECASE)
        if visual_match:
            visual_directive = visual_match.group(1).strip()
            response = re.sub(r"<visual>.*?</visual>", "", response, flags=re.IGNORECASE).strip()

        # Extract gesture directive
        gesture_directive = None
        gesture_match = re.search(r"<gesture>(.*?)</gesture>", response, re.IGNORECASE)
        if gesture_match:
            gesture_directive = gesture_match.group(1).strip()
            response = re.sub(r"<gesture>.*?</gesture>", "", response, flags=re.IGNORECASE).strip()

        # Attach any generated images to the final response
        for img in generated_images:
            response += f"\n<br>{img}"

        # ── 7. Add response to working memory ───────────────────────────
        working.add_assistant_message(response)

        # ── 8. Store interaction in episodic memory ──────────────────────
        await self.memory.store_interaction(
            user_message=message,
            assistant_response=response,
            person_id=active_person,
        )

        # ── 9. Update emotional state ────────────────
        if self.emotion_engine:
            # We don't await this to block the response return, but since we need it in the background, 
            # we will just await it here for simplicity. (Phase 5 could make this an async task).
            await self.emotion_engine.evaluate_interaction(
                state=self.emotional_state,
                user_message=message,
                assistant_response=response,
                person_id=active_person,
            )
            await self._save_emotional_state()

        elapsed = time.time() - start_time
        logger.info(f"Response generated in {elapsed:.2f}s ({len(response)} chars), Visual: {visual_directive}, Gesture: {gesture_directive}")

        return response, visual_directive, gesture_directive

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
        state_file = DATA_DIR / "emotional_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.emotional_state = EmotionalState.from_dict(data)
                logger.info("Restored previous emotional state.")
            except Exception as e:
                logger.error(f"Failed to load emotional state: {e}")
                self.emotional_state = EmotionalState()
        else:
            self.emotional_state = EmotionalState()

    async def _save_emotional_state(self):
        """Save current emotional state for persistence."""
        state_file = DATA_DIR / "emotional_state.json"
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(self.emotional_state.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save emotional state: {e}")

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
