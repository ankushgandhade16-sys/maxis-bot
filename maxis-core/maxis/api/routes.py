"""
REST API routes — Status, memory search, and management endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Orchestrator reference (set during app startup)
_orchestrator = None


def set_orchestrator(orchestrator):
    global _orchestrator
    _orchestrator = orchestrator


class ChatRequest(BaseModel):
    message: str
    person_id: str | None = None
    is_voice: bool = False
    is_creator: bool = False


class ChatResponse(BaseModel):
    response: str
    emotional_state: dict[str, float]
    visual_directive: str | None = None
    gesture_directive: str | None = None
    model_used: str = "local"


class RegisterUserRequest(BaseModel):
    name: str


class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = 10


@router.get("/status")
async def get_status():
    """Get Maxis system status."""
    if not _orchestrator:
        raise HTTPException(500, "Orchestrator not initialized")
    return _orchestrator.get_status()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Send a message to Maxis (REST alternative to WebSocket)."""
    if not _orchestrator:
        raise HTTPException(500, "Orchestrator not initialized")

    response, visual_directive, gesture_directive = await _orchestrator.process_message(
        message=req.message,
        person_id=req.person_id,
        is_voice=req.is_voice,
        is_creator=req.is_creator,
    )

    return ChatResponse(
        response=response,
        visual_directive=visual_directive,
        gesture_directive=gesture_directive,
        emotional_state=_orchestrator.emotional_state.summary(),
    )


@router.post("/register")
async def register_user(req: RegisterUserRequest):
    """Register the primary user."""
    if not _orchestrator:
        raise HTTPException(500, "Orchestrator not initialized")

    person_id = await _orchestrator.register_primary_user(req.name)
    return {"person_id": person_id, "name": req.name}


@router.get("/memory/search")
async def search_memory(q: str, top_k: int = 10):
    """Search Maxis's memories."""
    if not _orchestrator:
        raise HTTPException(500, "Orchestrator not initialized")

    episodes = await _orchestrator.memory.episodic.retrieve(query=q, top_k=top_k)
    facts = await _orchestrator.memory.semantic.search(q)

    return {
        "episodes": episodes,
        "facts": facts,
    }


@router.get("/memory/persons")
async def list_persons():
    """List all known persons."""
    if not _orchestrator:
        raise HTTPException(500, "Orchestrator not initialized")

    return await _orchestrator.memory.persons.get_all_persons()


@router.get("/llm/status")
async def llm_status():
    """Get LLM router status and token budget."""
    if not _orchestrator:
        raise HTTPException(500, "Orchestrator not initialized")

    status = _orchestrator.llm.get_status()
    budget = _orchestrator.llm._token_budget.get_usage_summary()
    return {**status, "budget_summary": budget}
