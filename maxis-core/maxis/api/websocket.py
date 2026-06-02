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
    Client sends: {"type": "login", "username": "...", "password": "..."}
    Client sends: {"type": "message", "content": "...", "is_voice": false}
    Server sends: {"type": "login_success", "name": "...", "is_creator": false}
    Server sends: {"type": "login_failed", "reason": "..."}
    Server sends: {"type": "response", "content": "...", "emotional_state": "..."}
    Server sends: {"type": "status", "data": {...}}
    Server sends: {"type": "error", "message": "..."}
    """
    await manager.connect(websocket)

    # Per-connection session state
    session_person_id = None

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
                data = {"type": "message", "content": raw}

            msg_type = data.get("type", "message")

            if msg_type == "login":
                username = data.get("username", "").strip()
                password = data.get("password", "")

                if not username or not password:
                    await manager.send_json(websocket, {
                        "type": "login_failed",
                        "reason": "Username and password are required.",
                    })
                    continue

                try:
                    person, is_creator = await orchestrator.login_user(username, password)

                    if person is None:
                        await manager.send_json(websocket, {
                            "type": "login_failed",
                            "reason": "Wrong password for this username.",
                        })
                        continue

                    session_person_id = person["id"]

                    await manager.send_json(websocket, {
                        "type": "login_success",
                        "person_id": person["id"],
                        "name": person["name"],
                        "is_creator": is_creator,
                    })

                except Exception as e:
                    logger.error(f"Login error: {e}")
                    await manager.send_json(websocket, {
                        "type": "login_failed",
                        "reason": "Something went wrong. Try again.",
                    })

            elif msg_type == "message":
                content = data.get("content", "").strip()
                is_voice = data.get("is_voice", False)

                if not content:
                    continue

                if not session_person_id:
                    await manager.send_json(websocket, {
                        "type": "error",
                        "message": "Please log in first.",
                    })
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
                        person_id=session_person_id,
                        is_voice=is_voice,
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


