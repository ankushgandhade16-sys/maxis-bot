# MAXIS / Eris — Project Handoff

> Paste this into a new conversation to bring the agent up to speed.

## What Is This Project?

**Eris** (formerly MAXIS) is an autonomous AI companion deployed at **https://maxis-bot.onrender.com**. It's a self-contained digital organism with:
- A living particle core (animated canvas entity with emotions, behaviors, autonomic systems)
- Multi-user authentication (creator vs regular users)
- Memory systems (episodic, semantic, working, emotional, procedural)
- LLM-powered conversation via Google Gemini API
- Chat history persistence with session management

**Project root**: `c:\Users\ankus\OneDrive\Desktop\MAXIS`
**Server code**: `c:\Users\ankus\OneDrive\Desktop\MAXIS\maxis-core\`
**Deployed on**: Render (auto-deploys from `main` branch)
**Repo**: `https://github.com/ankushgandhade16-sys/maxis-bot.git`
**Keep-alive**: A bot pings the server every 10 minutes to prevent Render free-tier spin-down.

## Architecture

```
maxis-core/
├── maxis/
│   ├── static/index.html      ← ENTIRE frontend (single file: HTML+CSS+JS+Canvas)
│   ├── main.py                ← FastAPI entry point
│   ├── config.py              ← All config (models, paths, API keys)
│   ├── api/
│   │   ├── websocket.py       ← WebSocket handler (login, chat, model switch)
│   │   └── routes.py          ← REST API routes
│   ├── core/
│   │   ├── orchestrator.py    ← Central pipeline: perceive→remember→think→respond→store
│   │   └── identity.py        ← System prompt builder (Eris personality)
│   ├── intelligence/
│   │   ├── llm_router.py      ← Routes to Gemini API (cloud) or Ollama (local)
│   │   └── token_budget.py    ← Daily token usage tracker
│   ├── memory/
│   │   ├── manager.py         ← Unified recall across all memory layers
│   │   ├── working.py         ← Short-term conversation context
│   │   ├── episodic.py        ← ChromaDB vector store for past interactions
│   │   ├── semantic.py        ← SQLite fact store (subject-predicate-object)
│   │   ├── emotional.py       ← Emotional event history
│   │   ├── chat_history.py    ← Persistent chat sessions (SQLite)
│   │   ├── compression.py     ← Background memory consolidation
│   │   └── procedural.py      ← Learned patterns/rules
│   └── emotion/
│       └── state.py           ← Emotional state model
├── data/                      ← Runtime databases (sqlite, chroma)
├── Dockerfile                 ← Render deployment config
└── maxis_config.yaml          ← Runtime YAML config (API keys via env vars)
```

## Current Models

| UI Name | Model ID | Status |
|---------|----------|--------|
| 🧠 Eris Pro | `gemini-3.5-flash` | ✅ Working perfectly |
| ⚡ Eris Swift | `gemini-3.1-flash-lite` | ✅ Just switched to this |

**IMPORTANT**: `gemini-2.0-flash` was **shut down June 1, 2026**. `gemini-2.5-flash` is flaky/legacy. Do NOT revert to these.

## What's Been Completed

### Phase 1: Foundation — Memory + Identity + Text Chat ✅ DONE
- Full memory architecture (5 layers: working, episodic, semantic, emotional, procedural)
- Multi-user auth with creator/user roles
- LLM routing (Gemini cloud + Ollama local fallback)
- Personality system (Eris identity prompt)
- WebSocket-based real-time chat
- Chat session persistence & history

### Post-Phase 1: UI & Deployment Work ✅ DONE
- Deployed to Render (Dockerfile, env vars, auto-deploy from GitHub)
- Complete frontend in single `index.html` (particle core, chat UI, login modal)
- Particle core rework: 800+ particles, 20+ autonomous behaviors, emotion-driven colors
- Gemini-style iridescent rainbow hue cycling
- Sidebar with chat history, toggle on desktop & mobile
- Mobile responsive (100dvh, safe-area-inset, close button)
- Account dropdown (sign out with cancel option, no accidental logout)
- Voice output via Web Speech API (browser TTS, not server-side)
- Creator omniscience (sees all users' chat history for context)
- All timestamps converted to IST (UTC+5:30) for Indian users

### Recent Bug Fixes (June 4-5, 2026)
- Fixed `Element.prototype.classList.toggle` Illegal Invocation crash
- Fixed missing `mainPanel` ID causing JS to crash on load
- Fixed negative canvas radius crash (core vanishing after 3 seconds)
- Upgraded from dead Gemini 2.0 to Gemini 3.5 Flash
- Added stale model cache clearing in localStorage
- Fixed all server timestamps from UTC to IST

## Known Issues / Things That Still Need Work
- **Voice INPUT** doesn't work yet (mic button exists but server-side STT is Phase 2)
- **Voice OUTPUT** uses browser's basic Web Speech API — sounds robotic
- Core animation can still freeze on very long-running tabs (rare)
- Memory compression runs but hasn't been stress-tested at scale

## Build Phases Roadmap

```
Phase 1: Memory + Identity + Text Chat     ✅ COMPLETE
Phase 2: Voice I/O (STT + TTS)             ← NEXT
Phase 3: Face Recognition                   
Phase 4: Emotion Engine                     
Phase 5: Screen + OS Access                
Phase 6: Security Daemon                   
Phase 7: Network + Tools                   
Phase 8: Mobile App                        
```

## Phase 2 Details (NEXT)

**Goal**: Talk to Eris and hear her respond with a natural voice.

The original plan (in `docs/implementation_plan.md`) calls for:
1. **VAD** (Voice Activity Detection) — Silero VAD on CPU, continuous listening
2. **STT** (Speech-to-Text) — faster-whisper with `medium.en` model
3. **TTS** (Text-to-Speech) — Kokoro TTS with emotional prosody
4. **Audio streaming** — WebSocket `/ws/voice` for bidirectional audio
5. **GPU scheduler** — VRAM management for model loading

**HOWEVER**: Since this runs on Render (no GPU, limited resources), the approach needs adaptation:
- Consider using **Web Speech API** for STT (browser-side, free, no server resources)
- Consider using **a cloud TTS API** or **edge TTS** instead of local Kokoro
- The existing mic button in the frontend already has partial speech recognition code

## How to Run Locally

```bash
cd c:\Users\ankus\OneDrive\Desktop\MAXIS\maxis-core
.venv\Scripts\activate
python maxis/main.py
# Visit http://localhost:8420
```

## How to Deploy

```bash
cd c:\Users\ankus\OneDrive\Desktop\MAXIS\maxis-core
git add -A
git commit -m "your message"
git push
# Render auto-deploys from main branch in ~2-3 minutes
```

## Login Credentials
- Creator account: **Ankush** (has omniscience — sees all users' chats)
- Other users can sign up through the UI

## Environment Variables (on Render)
- `GEMINI_API_KEY` — Google AI Studio API key
- `MAXIS_ENV=cloud` — Forces cloud model routing
- `SECRET_KEY` — For password hashing
