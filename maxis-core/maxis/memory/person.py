"""
Person-Specific Memory — Individual profiles for everyone Maxis has met.

Every person has their own memory branch: interaction history, preferences,
relationship dynamics, face embeddings, and accumulated impressions.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Optional

from loguru import logger
from sqlalchemy import create_engine, Column, String, Float, Text, Integer, LargeBinary
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from maxis.config import SQLITE_DIR


class Base(DeclarativeBase):
    pass


class PersonProfile(Base):
    """A person Maxis has met and remembers."""
    __tablename__ = "person_profiles"

    id = Column(String, primary_key=True)  # UUID
    name = Column(String, nullable=False, index=True)
    is_primary_user = Column(Integer, default=0)  # 1 for the main user

    # Recognition
    face_embedding_json = Column(Text, default="[]")  # serialized numpy array
    voice_profile_json = Column(Text, default="{}")  # voice characteristics

    # Relationship
    first_met = Column(Float, default=0.0)
    last_seen = Column(Float, default=0.0)
    interaction_count = Column(Integer, default=0)
    relationship_label = Column(String, default="acquaintance")  # friend, family, colleague, etc.

    # Preferences & traits observed
    preferences_json = Column(Text, default="{}")  # {"communication_style": "direct", ...}
    traits_json = Column(Text, default="[]")  # observed traits
    topics_of_interest_json = Column(Text, default="[]")  # topics they care about

    # Emotional relationship
    warmth_baseline = Column(Float, default=0.3)  # default warmth toward this person
    trust_level = Column(Float, default=0.5)  # 0 untrusted ... 1 fully trusted

    notes = Column(Text, default="")  # free-form notes Maxis has made


class PersonMemory:
    """
    Manages person-specific profiles and memory branches.

    Each person Maxis interacts with gets their own profile that grows
    over time through passive observation and interaction history.
    """

    def __init__(self):
        self._engine = None
        self._session_factory = None
        self._initialized = False
        self._cache: dict[str, dict] = {}  # in-memory cache of active profiles

    async def initialize(self):
        if self._initialized:
            return

        db_path = SQLITE_DIR / "persons.db"
        self._engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine)

        with self._session_factory() as session:
            count = session.query(PersonProfile).count()
        logger.info(f"Person memory loaded: {count} known persons")
        self._initialized = True

    async def create_person(
        self,
        name: str,
        is_primary_user: bool = False,
        face_embedding: list[float] | None = None,
    ) -> str:
        """Create a new person profile. Returns the person ID."""
        if not self._initialized:
            await self.initialize()

        person_id = str(uuid.uuid4())
        now = time.time()

        profile = PersonProfile(
            id=person_id,
            name=name,
            is_primary_user=1 if is_primary_user else 0,
            face_embedding_json=json.dumps(face_embedding or []),
            first_met=now,
            last_seen=now,
            interaction_count=0,
            warmth_baseline=0.7 if is_primary_user else 0.3,
            trust_level=1.0 if is_primary_user else 0.5,
        )

        with self._session_factory() as session:
            session.add(profile)
            session.commit()

        logger.info(f"Created person profile: {name} (id={person_id[:8]})")
        return person_id

    async def get_person(self, person_id: str) -> Optional[dict]:
        """Get a person's full profile."""
        if not self._initialized:
            await self.initialize()

        # Check cache first
        if person_id in self._cache:
            return self._cache[person_id]

        with self._session_factory() as session:
            profile = session.query(PersonProfile).filter_by(id=person_id).first()
            if not profile:
                return None

            data = {
                "id": profile.id,
                "name": profile.name,
                "is_primary_user": bool(profile.is_primary_user),
                "first_met": profile.first_met,
                "last_seen": profile.last_seen,
                "interaction_count": profile.interaction_count,
                "relationship_label": profile.relationship_label,
                "preferences": json.loads(profile.preferences_json),
                "traits": json.loads(profile.traits_json),
                "topics_of_interest": json.loads(profile.topics_of_interest_json),
                "warmth_baseline": profile.warmth_baseline,
                "trust_level": profile.trust_level,
                "notes": profile.notes,
                "face_embedding": json.loads(profile.face_embedding_json),
            }

            self._cache[person_id] = data
            return data

    async def get_primary_user(self) -> Optional[dict]:
        """Get the primary user's profile."""
        if not self._initialized:
            await self.initialize()

        with self._session_factory() as session:
            profile = session.query(PersonProfile).filter_by(is_primary_user=1).first()
            if profile:
                return await self.get_person(profile.id)
        return None

    async def find_by_name(self, name: str) -> Optional[dict]:
        """Find a person by name (case-insensitive)."""
        if not self._initialized:
            await self.initialize()

        with self._session_factory() as session:
            profile = session.query(PersonProfile).filter(
                PersonProfile.name.ilike(f"%{name}%")
            ).first()
            if profile:
                return await self.get_person(profile.id)
        return None

    async def update_interaction(self, person_id: str):
        """Record that an interaction happened with this person."""
        if not self._initialized:
            await self.initialize()

        with self._session_factory() as session:
            profile = session.query(PersonProfile).filter_by(id=person_id).first()
            if profile:
                profile.last_seen = time.time()
                profile.interaction_count += 1
                session.commit()

        # Invalidate cache
        self._cache.pop(person_id, None)

    async def update_preference(self, person_id: str, key: str, value: str):
        """Update a person's observed preference."""
        if not self._initialized:
            await self.initialize()

        with self._session_factory() as session:
            profile = session.query(PersonProfile).filter_by(id=person_id).first()
            if profile:
                prefs = json.loads(profile.preferences_json)
                prefs[key] = value
                profile.preferences_json = json.dumps(prefs)
                session.commit()

        self._cache.pop(person_id, None)

    async def update_warmth(self, person_id: str, delta: float):
        """Adjust warmth baseline toward a person."""
        if not self._initialized:
            await self.initialize()

        with self._session_factory() as session:
            profile = session.query(PersonProfile).filter_by(id=person_id).first()
            if profile:
                profile.warmth_baseline = max(-0.5, min(1.0, profile.warmth_baseline + delta))
                session.commit()

        self._cache.pop(person_id, None)

    async def get_context_for_person(self, person_id: str) -> str:
        """
        Build a context string about a person for injection into the system prompt.
        This is what makes Maxis's responses personalized.
        """
        person = await self.get_person(person_id)
        if not person:
            return "Speaking with an unknown person. Be friendly but cautious."

        lines = [f"Name: {person['name']}"]

        if person["is_primary_user"]:
            lines.append("This is your primary user — be fully yourself.")
        else:
            lines.append(f"Relationship: {person['relationship_label']}")

        lines.append(f"You've interacted {person['interaction_count']} times.")

        if person["preferences"]:
            pref_str = ", ".join(f"{k}: {v}" for k, v in person["preferences"].items())
            lines.append(f"Known preferences: {pref_str}")

        if person["topics_of_interest"]:
            lines.append(f"Interested in: {', '.join(person['topics_of_interest'])}")

        if person["notes"]:
            lines.append(f"Notes: {person['notes']}")

        return "\n".join(lines)

    async def get_all_persons(self) -> list[dict]:
        """List all known persons."""
        if not self._initialized:
            await self.initialize()

        with self._session_factory() as session:
            profiles = session.query(PersonProfile).all()
            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "is_primary_user": bool(p.is_primary_user),
                    "interaction_count": p.interaction_count,
                    "last_seen": p.last_seen,
                }
                for p in profiles
            ]
