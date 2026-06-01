# MAXIS Build Tasks

## Phase 1: Foundation — Memory System & Identity Core
- `[x]` Project scaffolding (pyproject.toml, directory structure)
- `[x]` config.py — Global configuration & paths
- `[x]` identity.py — Maxis personality & system prompt
- `[x]` Memory Layer
  - `[x]` working.py — Active conversation context
  - `[x]` episodic.py — ChromaDB episodic memory
  - `[x]` semantic.py — Knowledge graph (NetworkX + SQLite)
  - `[x]` procedural.py — Learned workflows
  - `[x]` emotional.py — Emotional event log
  - `[x]` person.py — Per-person profiles
  - `[x]` manager.py — Unified memory retrieval
  - `[x]` compression.py — Background memory summarization
- `[x]` Intelligence
  - `[x]` llm_router.py — Local Ollama + Groq API routing
  - `[x]` token_budget.py — Token usage tracking
- `[x]` orchestrator.py — Main request pipeline
- `[x]` main.py — FastAPI app + WebSocket
- `[x]` API routes (routes.py, websocket.py)
- `[x]` Dependency installation
- `[x]` Phase 1 verification tests (Imports pass, server starts, model downloaded)

## Phase 2: Voice Input & Output
- `[ ]` vad.py — Silero VAD
- `[ ]` stt.py — faster-whisper streaming
- `[ ]` tts.py — Kokoro TTS
- `[ ]` audio_stream.py — WebSocket audio handler
- `[ ]` gpu_scheduler.py — VRAM management
- `[ ]` Phase 2 verification

## Phase 3: Face Recognition & User Identification
- `[ ]` camera.py — Webcam capture
- `[ ]` face_recognition.py — InsightFace pipeline
- `[ ]` auth.py — Face-based authentication
- `[ ]` Phase 3 verification

## Phase 4: Emotion Engine
- `[ ]` dimensions.py — Emotional dimension definitions
- `[ ]` state.py — EmotionalState class
- `[ ]` engine.py — Causal reasoning layer
- `[ ]` contagion.py — Emotional mirroring
- `[ ]` personality.py — Trait expression system
- `[ ]` face_emotion.py — HSEmotion integration
- `[ ]` Phase 4 verification

## Phase 5–8: Later phases
- `[ ]` Phase 5: Screen + OS Access
- `[ ]` Phase 6: Security Daemon
- `[ ]` Phase 7: Network + Tools
- `[ ]` Phase 8: Mobile App
