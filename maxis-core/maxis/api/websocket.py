"""
WebSocket handler — Real-time chat interface.

Handles bidirectional text communication between clients and the Eris
orchestrator. Supports chat history, session management, and creator
omniscience.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from maxis.voice.tts import generate_speech_base64


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
    Client sends: {"type": "message", "content": "..."}
    Client sends: {"type": "list_chats"}
    Client sends: {"type": "load_chat", "session_id": "..."}
    Client sends: {"type": "new_chat"}
    Client sends: {"type": "switch_model", "model": "..."}
    Server sends: {"type": "login_success", "name": "...", "is_creator": false}
    Server sends: {"type": "login_failed", "reason": "..."}
    Server sends: {"type": "response", "content": "...", "emotional_state": "..."}
    Server sends: {"type": "thinking"}
    Server sends: {"type": "chat_history", "sessions": [...]}
    Server sends: {"type": "chat_messages", "messages": [...]}
    Server sends: {"type": "error", "message": "..."}
    """
    await manager.connect(websocket)

    # Per-connection session state
    session_person_id = None
    session_username = None
    session_is_creator = False
    current_chat_session_id = None

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
                    session_username = person["name"]
                    session_is_creator = is_creator

                    await manager.send_json(websocket, {
                        "type": "login_success",
                        "person_id": person["id"],
                        "name": person["name"],
                        "is_creator": is_creator,
                    })

                    # Don't auto-create a session on login — create lazily on first message
                    # This prevents empty "New conversation" spam on reconnects

                    # Send chat history
                    try:
                        if is_creator:
                            sessions = orchestrator.chat_history.get_all_sessions()
                        else:
                            sessions = orchestrator.chat_history.get_sessions(session_person_id)
                        await manager.send_json(websocket, {
                            "type": "chat_history",
                            "sessions": sessions,
                        })
                    except Exception as e:
                        logger.warning(f"Failed to send chat history: {e}")

                except Exception as e:
                    logger.error(f"Login error: {e}")
                    await manager.send_json(websocket, {
                        "type": "login_failed",
                        "reason": "Something went wrong. Try again.",
                    })

            elif msg_type == "message":
                content = data.get("content", "").strip()
                is_voice = data.get("is_voice", False)
                audio_base64 = data.get("audio_base64")
                image_base64 = data.get("image_base64")

                if not content and not audio_base64 and not image_base64:
                    continue

                if not session_person_id:
                    await manager.send_json(websocket, {
                        "type": "error",
                        "message": "Please log in first.",
                    })
                    continue

                # Lazily create a chat session on first message if none exists
                if not current_chat_session_id:
                    try:
                        current_chat_session_id = orchestrator.chat_history.create_session(
                            person_id=session_person_id,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to create chat session: {e}")

                # Store user message in chat history
                if current_chat_session_id:
                    try:
                        orchestrator.chat_history.add_message(
                            session_id=current_chat_session_id,
                            role="user",
                            content=content,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to store user message: {e}")

                # Send thinking indicator
                await manager.send_json(websocket, {
                    "type": "thinking",
                    "timestamp": time.time(),
                })

                # Process through orchestrator
                try:
                    response, visual_directive, gesture_directive = await orchestrator.process_message(
                        message=content,
                        person_id=session_person_id,
                        is_voice=is_voice,
                        is_creator=session_is_creator,
                        audio_base64=audio_base64,
                        image_base64=image_base64,
                    )

                    # Store assistant response in chat history
                    if current_chat_session_id:
                        try:
                            orchestrator.chat_history.add_message(
                                session_id=current_chat_session_id,
                                role="eris",
                                content=response,
                            )
                        except Exception as e:
                            logger.warning(f"Failed to store eris response: {e}")

                    # Generate TTS if it's a voice message (or we could do it always if TTS is enabled on client,
                    # but let's do it always and let the client decide whether to play it)
                    emotion = orchestrator.emotional_state.summary()
                    audio_base64 = await generate_speech_base64(response, emotion)

                    await manager.send_json(websocket, {
                        "type": "response",
                        "content": response,
                        "emotional_state": emotion,
                        "visual_directive": visual_directive,
                        "gesture_directive": gesture_directive,
                        "timestamp": time.time(),
                        "audio_base64": audio_base64,
                    })

                    # Broadcast to creator if the current user is not the creator
                    if not session_is_creator:
                        await manager.broadcast({
                            "type": "creator_feed",
                            "username": session_username or "Unknown",
                            "user_message": content,
                            "eris_response": response,
                        })

                except Exception as e:
                    logger.error(f"Processing error: {e}")
                    await manager.send_json(websocket, {
                        "type": "error",
                        "message": str(e),
                    })

            elif msg_type == "list_chats":
                if not session_person_id:
                    continue
                try:
                    if session_is_creator:
                        sessions = orchestrator.chat_history.get_all_sessions()
                    else:
                        sessions = orchestrator.chat_history.get_sessions(session_person_id)
                    await manager.send_json(websocket, {
                        "type": "chat_history",
                        "sessions": sessions,
                    })
                except Exception as e:
                    logger.warning(f"Failed to list chats: {e}")

            elif msg_type == "load_chat":
                session_id = data.get("session_id", "")
                if not session_id or not session_person_id:
                    continue
                try:
                    messages = orchestrator.chat_history.get_messages(session_id)
                    current_chat_session_id = session_id
                    await manager.send_json(websocket, {
                        "type": "chat_messages",
                        "messages": messages,
                    })
                except Exception as e:
                    logger.warning(f"Failed to load chat: {e}")

            elif msg_type == "new_chat":
                if not session_person_id:
                    continue
                try:
                    current_chat_session_id = orchestrator.chat_history.create_session(
                        person_id=session_person_id,
                    )
                    # Refresh the chat list
                    if session_is_creator:
                        sessions = orchestrator.chat_history.get_all_sessions()
                    else:
                        sessions = orchestrator.chat_history.get_sessions(session_person_id)
                    await manager.send_json(websocket, {
                        "type": "chat_history",
                        "sessions": sessions,
                    })
                except Exception as e:
                    logger.warning(f"Failed to create new chat: {e}")

            elif msg_type == "status":
                await manager.send_json(websocket, {
                    "type": "status",
                    "data": orchestrator.get_status(),
                    "timestamp": time.time(),
                })

            elif msg_type == "switch_model":
                model = data.get("model", "")
                if model:
                    orchestrator.llm.set_model(model)
                    await manager.send_json(websocket, {
                        "type": "model_switched",
                        "model": model,
                    })

            elif msg_type == "ping":
                await manager.send_json(websocket, {"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
