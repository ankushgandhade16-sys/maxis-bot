"""
Face Recognition Service.

Handles face matching logic (cosine similarity) using embeddings generated
by the frontend (e.g. MediaPipe).
"""

from __future__ import annotations

import json
from loguru import logger
import numpy as np

# Threshold for cosine similarity to consider a match.
# MediaPipe embeddings are 128-dimensional.
# Similarity > 0.6 is generally a good match, but we can tune it.
MATCH_THRESHOLD = 0.65

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    a = np.array(v1)
    b = np.array(v2)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

class FaceRecognitionManager:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    async def match_face(self, embedding: list[float]) -> dict | None:
        """
        Find the person matching this embedding.
        Returns the person dict if found, else None.
        """
        persons = await self.orchestrator.memory.persons.get_all_persons()
        
        best_match = None
        best_score = -1.0
        
        for p_info in persons:
            person = await self.orchestrator.memory.persons.get_person(p_info["id"])
            if not person or not person.get("face_embedding"):
                continue
                
            score = cosine_similarity(embedding, person["face_embedding"])
            if score > best_score:
                best_score = score
                best_match = person
                
        if best_match and best_score >= MATCH_THRESHOLD:
            logger.info(f"Face matched: {best_match['name']} (score={best_score:.2f})")
            return best_match
            
        logger.debug(f"No face match. Best score: {best_score:.2f}")
        return None

    async def enroll_face(self, person_id: str, embedding: list[float]):
        """Associate a face embedding with an existing person."""
        await self.orchestrator.memory.persons.update_face_embedding(person_id, embedding)
        logger.info(f"Enrolled new face for person_id: {person_id}")
