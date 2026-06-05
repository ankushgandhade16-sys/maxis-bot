"""
Face Recognition Service.

Handles face matching logic (cosine similarity) using embeddings generated
by the frontend (e.g. MediaPipe).
"""

from __future__ import annotations

import json
from loguru import logger
import numpy as np

# Threshold for euclidean distance to consider a match.
# MediaPipe/face-api.js embeddings are 128-dimensional.
# Distance < 0.65 is generally a good match.
MATCH_THRESHOLD = 0.65

def euclidean_distance(v1: list[float], v2: list[float]) -> float:
    """Calculate euclidean distance between two vectors."""
    a = np.array(v1)
    b = np.array(v2)
    return float(np.linalg.norm(a - b))

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
        best_score = float('inf')
        
        for p_info in persons:
            person = await self.orchestrator.memory.persons.get_person(p_info["id"])
            if not person or not person.get("face_embedding"):
                continue
                
            distance = euclidean_distance(embedding, person["face_embedding"])
            if distance < best_score:
                best_score = distance
                best_match = person
                
        if best_match and best_score <= MATCH_THRESHOLD:
            logger.info(f"Face matched: {best_match['name']} (distance={best_score:.2f})")
            return best_match
            
        logger.debug(f"No face match. Best distance: {best_score:.2f}")
        return None

    async def enroll_face(self, person_id: str, embedding: list[float]):
        """Associate a face embedding with an existing person."""
        await self.orchestrator.memory.persons.update_face_embedding(person_id, embedding)
        logger.info(f"Enrolled new face for person_id: {person_id}")
