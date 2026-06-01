"""
WebSocket handler — Real-time chat interface.

Handles bidirectional text (and later voice) communication
between clients and the Maxis orchestrator.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Active: {len(self.active_connections)}")

    async def send_json(self, websocket: WebSocket, data: dict):
        await websocket.send_json(data)

    async def broadcast(self, data: dict):
        for conn in self.active_connections:
            try:
                await conn.send_json(data)
            except Exception:
                pass


# Global connection manager
manager = ConnectionManager()


async def websocket_chat_handler(websocket: WebSocket, orchestrator):
    """
    Handle a WebSocket chat session.

    Protocol:
    Client sends: {"type": "message", "content": "...", "person_id": "..."}
    Server sends: {"type": "response", "content": "...", "emotional_state": "..."}
    Server sends: {"type": "status", "data": {...}}
    Server sends: {"type": "error", "message": "..."}
    """
    await manager.connect(websocket)

    try:
        # Send initial status
        await manager.send_json(websocket, {
            "type": "status",
            "data": orchestrator.get_status(),
            "timestamp": time.time(),
        })

        while True:
            # Receive message
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # Treat raw text as a simple message
                data = {"type": "message", "content": raw}

            msg_type = data.get("type", "message")

            if msg_type == "message":
                content = data.get("content", "").strip()
                person_id = data.get("person_id")

                if not content:
                    continue

                # Send thinking indicator
                await manager.send_json(websocket, {
                    "type": "thinking",
                    "timestamp": time.time(),
                })

                # Process through orchestrator
                try:
                    response = await orchestrator.process_message(
                        message=content,
                        person_id=person_id,
                    )

                    await manager.send_json(websocket, {
                        "type": "response",
                        "content": response,
                        "emotional_state": orchestrator.emotional_state.summary(),
                        "timestamp": time.time(),
                    })

                except Exception as e:
                    logger.error(f"Processing error: {e}")
                    await manager.send_json(websocket, {
                        "type": "error",
                        "message": str(e),
                    })

            elif msg_type == "register_user":
                name = data.get("name", "User")
                
                # Check if a primary user exists
                primary = await orchestrator.memory.persons.get_primary_user()
                if not primary:
                    # First ever user
                    person_id = await orchestrator.register_primary_user(name)
                else:
                    # A friend / secondary user
                    person_id = await orchestrator.register_user(name)

                await manager.send_json(websocket, {
                    "type": "user_registered",
                    "person_id": person_id,
                    "name": name,
                })

            elif msg_type == "status":
                await manager.send_json(websocket, {
                    "type": "status",
                    "data": orchestrator.get_status(),
                    "timestamp": time.time(),
                })

            elif msg_type == "ping":
                await manager.send_json(websocket, {"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
