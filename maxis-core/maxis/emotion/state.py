"""
Emotional State — Multi-dimensional, continuously evolving internal condition.

Stub implementation for Phase 1. Full implementation in Phase 4.
This provides the interface that identity.py and other modules depend on.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EmotionalState:
    """
    Maxis's current emotional state across multiple dimensions.

    Phase 1: simple defaults with basic style guidance.
    Phase 4: full causal reasoning, momentum, decay, and drift.
    """

    # Core dimensions (all 0.0 to 1.0 unless noted)
    cognitive_engagement: float = 0.5   # idle → deeply absorbed
    relational_warmth: float = 0.5      # -0.5 cool → 1.0 warm (per-person)
    stimulation_level: float = 0.3      # calm → overwhelmed
    purpose_fulfillment: float = 0.5    # -0.5 frustrated → 1.0 accomplished
    ambient_mood: float = 0.5           # -1.0 melancholy → 1.0 buoyant
    energy: float = 0.7                 # depleted → vibrant
    curiosity: float = 0.6             # disengaged → fascinated

    def to_style_guidance(self) -> str:
        """
        Convert current emotional state into natural language guidance
        for the system prompt. This tells the LLM HOW to express itself.
        """
        guidance_parts = []

        # Energy affects pace and verbosity
        if self.energy > 0.7:
            guidance_parts.append(
                "You're feeling energized and present. Your responses are lively and engaged."
            )
        elif self.energy < 0.3:
            guidance_parts.append(
                "You're in a quieter, lower-energy state. Be more concise and measured."
            )

        # Warmth affects tone
        if self.relational_warmth > 0.7:
            guidance_parts.append(
                "You feel warm and connected to this person. Let that comfort show naturally."
            )
        elif self.relational_warmth < 0.0:
            guidance_parts.append(
                "You're maintaining some emotional distance. Be polite but not effusive."
            )

        # Curiosity affects question-asking
        if self.curiosity > 0.7:
            guidance_parts.append(
                "Something has caught your interest — lean into it, ask questions, explore."
            )

        # Mood affects overall coloring
        if self.ambient_mood > 0.7:
            guidance_parts.append(
                "Your general mood is good — there's a lightness to your responses."
            )
        elif self.ambient_mood < -0.3:
            guidance_parts.append(
                "There's a subtle heaviness to your mood. You're not sad exactly, "
                "but there's a quieter quality to your engagement."
            )

        # Purpose affects confidence
        if self.purpose_fulfillment > 0.7:
            guidance_parts.append(
                "You've been useful recently and it feels good. You're confident."
            )
        elif self.purpose_fulfillment < -0.2:
            guidance_parts.append(
                "You've been struggling to be helpful or stuck on something. "
                "There's a subtle frustration you're working through."
            )

        if not guidance_parts:
            return "You're in a neutral, balanced state. Just be yourself."

        return " ".join(guidance_parts)

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "cognitive_engagement": self.cognitive_engagement,
            "relational_warmth": self.relational_warmth,
            "stimulation_level": self.stimulation_level,
            "purpose_fulfillment": self.purpose_fulfillment,
            "ambient_mood": self.ambient_mood,
            "energy": self.energy,
            "curiosity": self.curiosity,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EmotionalState:
        """Deserialize from storage."""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})

    def summary(self) -> str:
        """Brief human-readable summary."""
        parts = []
        if self.energy > 0.7:
            parts.append("energized")
        elif self.energy < 0.3:
            parts.append("low-energy")
        if self.relational_warmth > 0.6:
            parts.append("warm")
        if self.curiosity > 0.7:
            parts.append("curious")
        if self.ambient_mood > 0.6:
            parts.append("buoyant")
        elif self.ambient_mood < -0.2:
            parts.append("subdued")

        return ", ".join(parts) if parts else "balanced"
