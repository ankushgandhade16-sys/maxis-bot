"""
MAXIS — Main Application Entry Point.

FastAPI server that serves as the backbone of the Maxis system.
Initializes all subsystems on startup, handles graceful shutdown.

Run with: python -m uvicorn maxis.main:app --host 0.0.0.0 --port 8420
Or:       python -m maxis.main
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from maxis.config import get_config, LOGS_DIR
from maxis.core.orchestrator import Orchestrator
from maxis.api.routes import router as api_router, set_orchestrator
from maxis.api.websocket import websocket_chat_handler

# ── Logging Setup ────────────────────────────────────────────────────────────

# Remove default logger
logger.remove()

# Console output
logger.add(
    sys.stderr,
    format=(
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
        "<level>{message}</level>"
    ),
    level="INFO",
)

# File output
logger.add(
    str(LOGS_DIR / "maxis_{time:YYYY-MM-DD}.log"),
    rotation="10 MB",
    retention="30 days",
    level="DEBUG",
)


# ── Application ──────────────────────────────────────────────────────────────

# Global orchestrator instance
orchestrator = Orchestrator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan — initialize on startup, cleanup on shutdown.
    """
    # ── Startup ──────────────────────────────────────────────────────────
    logger.info("Starting MAXIS Core...")
    await orchestrator.initialize()
    set_orchestrator(orchestrator)

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    await orchestrator.shutdown()


app = FastAPI(
    title="MAXIS",
    description="Modular Autonomous eXperiential Intelligence System",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────

config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── REST Routes ──────────────────────────────────────────────────────────────

app.include_router(api_router, prefix="/api")


# ── WebSocket Endpoints ──────────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat."""
    await websocket_chat_handler(websocket, orchestrator)


# ── Static Files ─────────────────────────────────────────────────────────────

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Root ─────────────────────────────────────────────────────────────────────

@app.head("/")
async def root_head():
    """Handle HEAD requests (used by UptimeRobot and health checks)."""
    from fastapi import Response
    return Response(status_code=200)

@app.get("/")
async def root():
    """Serve the chat UI."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "name": "MAXIS",
        "version": "0.1.0",
        "status": "online" if orchestrator._initialized else "initializing",
    }


# ── Direct execution ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "maxis.main:app",
        host=config.server.host,
        port=config.server.port,
        log_level=config.server.log_level,
        reload=False,
    )
