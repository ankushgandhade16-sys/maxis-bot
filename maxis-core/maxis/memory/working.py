"""
Working Memory — Active conversation context.

The rolling buffer of recent exchanges that gets fed directly into the LLM
context window. This is Maxis's "short-term memory" — what she's currently
thinking about and immediately aware of.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Turn:
    """A single conversation turn."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    person_id: Optional[str] = None  # who said this (for multi-person)
    metadata: dict = field(default_factory=dict)

    def to_message(self) -> dict:
        """Convert to LLM message format."""
        msg = {"role": self.role, "content": self.content}
        if "image_base64" in self.metadata:
            msg["image_base64"] = self.metadata["image_base64"]
        return msg

    def token_estimate(self) -> int:
        """Rough token count estimate (~4 chars per token for English)."""
        return len(self.content) // 4 + 1


class WorkingMemory:
    """
    Rolling conversation buffer.

    Maintains the most recent N turns of conversation, respecting a token
    budget so we never blow out the LLM context window. Oldest turns are
    dropped first when the budget is exceeded.
    """

    def __init__(self, max_turns: int = 20, max_tokens: int = 4096):
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self._turns: list[Turn] = []
        self._active_task: Optional[str] = None  # current task description

    def add_turn(self, role: str, content: str, person_id: str | None = None, **metadata) -> Turn:
        """Add a new turn to working memory."""
        turn = Turn(
            role=role,
            content=content,
            person_id=person_id,
            metadata=metadata,
        )
        self._turns.append(turn)
        self._enforce_limits()
        return turn

    def add_user_message(self, content: str, person_id: str | None = None) -> Turn:
        """Convenience: add a user message."""
        return self.add_turn("user", content, person_id)

    def add_assistant_message(self, content: str) -> Turn:
        """Convenience: add Maxis's response."""
        return self.add_turn("assistant", content)

    def get_messages(self) -> list[dict]:
        """Get all turns as LLM message dicts."""
        return [t.to_message() for t in self._turns]

    def get_recent_text(self, n: int = 5) -> str:
        """Get recent conversation as readable text (for memory queries)."""
        recent = self._turns[-n:]
        lines = []
        for t in recent:
            speaker = "User" if t.role == "user" else "Maxis"
            lines.append(f"{speaker}: {t.content}")
        return "\n".join(lines)

    def get_last_user_message(self) -> str | None:
        """Get the most recent user message content."""
        for t in reversed(self._turns):
            if t.role == "user":
                return t.content
        return None

    def set_active_task(self, task: str | None):
        """Track what Maxis is currently working on."""
        self._active_task = task

    @property
    def active_task(self) -> str | None:
        return self._active_task

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    @property
    def total_tokens(self) -> int:
        return sum(t.token_estimate() for t in self._turns)

    def clear(self):
        """Clear all working memory (e.g., on session end)."""
        self._turns.clear()
        self._active_task = None

    def _enforce_limits(self):
        """Drop oldest turns to stay within limits."""
        # Enforce turn count
        while len(self._turns) > self.max_turns:
            self._turns.pop(0)

        # Enforce token budget
        while self.total_tokens > self.max_tokens and len(self._turns) > 2:
            self._turns.pop(0)
