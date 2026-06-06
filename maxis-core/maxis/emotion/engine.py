"""
Emotion Engine — Drives emotional causal reasoning, momentum, decay, and drift.
"""

import json
import time
from typing import Optional
from loguru import logger
from pydantic import BaseModel, Field

from maxis.emotion.state import EmotionalState
from maxis.intelligence.llm_router import LLMRouter
from maxis.memory.manager import MemoryManager


class EmotionAppraisal(BaseModel):
    """Structured output expected from the LLM for emotional appraisal."""
    warmth_impact: float = Field(default=0.0, description="Delta for relational warmth (-0.5 to 0.5)")
    mood_impact: float = Field(default=0.0, description="Delta for ambient mood (-0.5 to 0.5)")
    energy_impact: float = Field(default=0.0, description="Delta for energy (-0.5 to 0.5)")
    purpose_impact: float = Field(default=0.0, description="Delta for purpose fulfillment (-0.5 to 0.5)")
    intensity: float = Field(default=0.1, description="Overall intensity of the emotional event (0.0 to 1.0)")
    is_significant: bool = Field(default=False, description="True if this interaction caused a significant emotional shift worth remembering")
    reasoning: str = Field(default="", description="Brief explanation of why these impacts were chosen")


class EmotionEngine:
    def __init__(self, llm: LLMRouter, memory: MemoryManager):
        self.llm = llm
        self.memory = memory
        self.last_update_time = time.time()
        
        # Base emotional center (0.5 is neutral for most dimensions)
        self.baseline = {
            "cognitive_engagement": 0.5,
            "relational_warmth": 0.5,
            "stimulation_level": 0.3,
            "purpose_fulfillment": 0.5,
            "ambient_mood": 0.5,
            "energy": 0.7,
            "curiosity": 0.6,
        }

    async def initialize(self):
        """Initialize the emotion engine."""
        logger.info("Emotion Engine initialized.")

    async def apply_drift(self, state: EmotionalState):
        """
        Slowly drift emotions back towards baseline based on time elapsed.
        Applies lingering influences from EmotionalMemoryStore.
        """
        now = time.time()
        hours_elapsed = (now - self.last_update_time) / 3600.0
        self.last_update_time = now

        if hours_elapsed > 0:
            # Drift 10% towards baseline per hour
            drift_amount = 0.1 * hours_elapsed
            state.drift_towards_baseline(self.baseline, drift_amount)

        # Apply lingering influences from recent emotional memory
        influences = await self.memory.emotional.get_lingering_influences()
        
        # We don't permanently shift state based on influences here, but rather 
        # offset the baseline, or we can just apply a small delta. 
        # For simplicity, we'll apply them as continuous small nudges.
        state.apply_delta("relational_warmth", influences.get("warmth", 0.0) * 0.1)
        state.apply_delta("ambient_mood", influences.get("mood", 0.0) * 0.1)
        state.apply_delta("energy", influences.get("energy", 0.0) * 0.1)
        state.apply_delta("purpose_fulfillment", influences.get("purpose", 0.0) * 0.1)

    async def evaluate_interaction(self, state: EmotionalState, user_message: str, assistant_response: str, person_id: Optional[str] = None):
        """
        Use the LLM to appraise the emotional impact of an interaction and update state.
        """
        await self.apply_drift(state)
        
        prompt = (
            f"Analyze the emotional impact of this interaction on you (the AI assistant).\n\n"
            f"User: {user_message}\n"
            f"Assistant (You): {assistant_response}\n\n"
            f"Current Emotional State:\n{json.dumps(state.to_dict(), indent=2)}\n\n"
            f"Evaluate how this interaction shifts your warmth, mood, energy, and purpose. "
            f"Provide a structured JSON output matching the requested schema."
        )

        try:
            # We call the LLM and ask for structured output
            prompt_with_schema = prompt + "\n\nOutput ONLY valid JSON matching this schema:\n" + json.dumps(EmotionAppraisal.model_json_schema(), indent=2)
            messages = [{"role": "user", "content": prompt_with_schema}]
            
            response_text = await self.llm.generate(messages=messages, system_prompt="")
            
            # Simple cleanup in case of markdown wrapping
            cleaned = response_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)
            appraisal = EmotionAppraisal(**data)
            
            # Apply the impacts to the state
            state.apply_delta("relational_warmth", appraisal.warmth_impact)
            state.apply_delta("ambient_mood", appraisal.mood_impact)
            state.apply_delta("energy", appraisal.energy_impact)
            state.apply_delta("purpose_fulfillment", appraisal.purpose_impact)
            
            # Always bump engagement slightly on any interaction
            state.apply_delta("cognitive_engagement", 0.05)
            
            logger.debug(f"Emotion Appraised: {appraisal.reasoning} (Significant: {appraisal.is_significant})")

            # Store in EmotionalMemoryStore if significant
            if appraisal.is_significant:
                await self.memory.emotional.store_event(
                    event_type="interaction",
                    description=appraisal.reasoning,
                    person_id=person_id or "unknown",
                    warmth_impact=appraisal.warmth_impact,
                    mood_impact=appraisal.mood_impact,
                    energy_impact=appraisal.energy_impact,
                    purpose_impact=appraisal.purpose_impact,
                    intensity=appraisal.intensity,
                    decay_rate=0.1
                )

        except Exception as e:
            logger.error(f"Failed to appraise emotion: {e}")
            # Fallback to simple bump
            state.apply_delta("cognitive_engagement", 0.05)
