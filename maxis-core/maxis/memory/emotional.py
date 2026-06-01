"""
Emotional Memory — Record of significant emotional events.

This is what makes Maxis remember that last Tuesday you seemed stressed,
or that a particular topic tends to frustrate you. Emotional events have
intensity, decay, and lingering effects that influence her behavior.
"""

from __future__ import annotations

import time
from typing import Optional

from loguru import logger
from sqlalchemy import create_engine, Column, String, Float, Text, Integer
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from maxis.config import SQLITE_DIR


class Base(DeclarativeBase):
    pass


class EmotionalEvent(Base):
    """A significant emotional event stored for long-term recall."""
    __tablename__ = "emotional_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Float, nullable=False, index=True)
    person_id = Column(String, default="unknown", index=True)
    event_type = Column(String, nullable=False)  # interaction, observation, task, system
    description = Column(Text, default="")

    # Emotional impact across key dimensions
    warmth_impact = Column(Float, default=0.0)  # how it affected relational warmth
    mood_impact = Column(Float, default=0.0)  # how it affected ambient mood
    energy_impact = Column(Float, default=0.0)  # how it affected energy
    purpose_impact = Column(Float, default=0.0)  # how it affected purpose/fulfillment

    intensity = Column(Float, default=0.5)  # 0 trivial ... 1 profound
    decay_rate = Column(Float, default=0.1)  # how fast this memory fades in influence
    resolved = Column(Integer, default=0)  # 1 if the emotional thread was resolved


class EmotionalMemoryStore:
    """
    Stores and retrieves significant emotional events.

    Unlike episodic memory (which stores everything), emotional memory
    only stores events that had meaningful emotional impact. These events
    influence Maxis's ongoing emotional state through their lingering
    effects.
    """

    def __init__(self):
        self._engine = None
        self._session_factory = None
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return

        db_path = SQLITE_DIR / "emotional_events.db"
        self._engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine)

        with self._session_factory() as session:
            count = session.query(EmotionalEvent).count()
        logger.info(f"Emotional memory loaded: {count} events")
        self._initialized = True

    async def store_event(
        self,
        event_type: str,
        description: str,
        person_id: str = "unknown",
        warmth_impact: float = 0.0,
        mood_impact: float = 0.0,
        energy_impact: float = 0.0,
        purpose_impact: float = 0.0,
        intensity: float = 0.5,
        decay_rate: float = 0.1,
    ):
        """Store a new emotional event."""
        if not self._initialized:
            await self.initialize()

        event = EmotionalEvent(
            timestamp=time.time(),
            person_id=person_id,
            event_type=event_type,
            description=description,
            warmth_impact=warmth_impact,
            mood_impact=mood_impact,
            energy_impact=energy_impact,
            purpose_impact=purpose_impact,
            intensity=intensity,
            decay_rate=decay_rate,
        )

        with self._session_factory() as session:
            session.add(event)
            session.commit()

        logger.debug(f"Stored emotional event: {description[:60]}... (intensity={intensity})")

    async def get_recent_events(
        self,
        hours: float = 24.0,
        person_id: str | None = None,
        min_intensity: float = 0.0,
    ) -> list[dict]:
        """Get recent emotional events, optionally filtered."""
        if not self._initialized:
            await self.initialize()

        cutoff = time.time() - (hours * 3600)

        with self._session_factory() as session:
            query = session.query(EmotionalEvent).filter(
                EmotionalEvent.timestamp >= cutoff,
                EmotionalEvent.intensity >= min_intensity,
            )
            if person_id:
                query = query.filter(EmotionalEvent.person_id == person_id)

            events = query.order_by(EmotionalEvent.timestamp.desc()).all()

            return [
                {
                    "timestamp": e.timestamp,
                    "person_id": e.person_id,
                    "event_type": e.event_type,
                    "description": e.description,
                    "warmth_impact": e.warmth_impact,
                    "mood_impact": e.mood_impact,
                    "energy_impact": e.energy_impact,
                    "purpose_impact": e.purpose_impact,
                    "intensity": e.intensity,
                    "current_influence": self._compute_current_influence(e),
                }
                for e in events
            ]

    def _compute_current_influence(self, event: EmotionalEvent) -> float:
        """
        Compute how much influence an emotional event still has NOW.

        Influence decays exponentially over time, but high-intensity events
        decay more slowly.
        """
        age_hours = (time.time() - event.timestamp) / 3600

        # Effective decay rate: intense events decay more slowly
        effective_decay = event.decay_rate * (1.0 - event.intensity * 0.5)

        # Exponential decay
        influence = event.intensity * (2.0 ** (-age_hours * effective_decay))

        return max(0.0, influence)

    async def get_person_emotional_summary(self, person_id: str) -> str:
        """Get a summary of emotional history with a specific person."""
        if not self._initialized:
            await self.initialize()

        with self._session_factory() as session:
            events = session.query(EmotionalEvent).filter_by(
                person_id=person_id
            ).order_by(EmotionalEvent.timestamp.desc()).limit(20).all()

            if not events:
                return f"No significant emotional history with {person_id}."

            # Aggregate
            avg_warmth = sum(e.warmth_impact for e in events) / len(events)
            total_interactions = len(events)

            recent = events[0]
            recent_desc = recent.description[:100]

            summary = (
                f"Emotional history with {person_id}: "
                f"{total_interactions} significant events. "
                f"Average warmth trend: {'positive' if avg_warmth > 0 else 'negative' if avg_warmth < 0 else 'neutral'}. "
                f"Most recent: {recent_desc}"
            )
            return summary

    async def get_lingering_influences(self) -> dict[str, float]:
        """
        Get the total lingering emotional influence across all recent events.

        Returns a dict of dimension impacts that should be applied to
        the current emotional state.
        """
        if not self._initialized:
            await self.initialize()

        influences = {
            "warmth": 0.0,
            "mood": 0.0,
            "energy": 0.0,
            "purpose": 0.0,
        }

        # Look at events from the last 72 hours
        events = await self.get_recent_events(hours=72.0, min_intensity=0.2)

        for e in events:
            inf = e["current_influence"]
            influences["warmth"] += e["warmth_impact"] * inf
            influences["mood"] += e["mood_impact"] * inf
            influences["energy"] += e["energy_impact"] * inf
            influences["purpose"] += e["purpose_impact"] * inf

        return influences
