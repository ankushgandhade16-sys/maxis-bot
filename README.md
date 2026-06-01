# MAXIS — Modular Autonomous eXperiential Intelligence System

> A persistent, self-aware AI agent that lives inside your computing environment.

## Quick Start

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.ai) installed and running
- NVIDIA GPU with CUDA support (RTX 5050 or compatible)

### 1. Install Ollama & Pull the Model
```bash
# Install Ollama from https://ollama.ai
# Then pull the model:
ollama pull qwen2.5:7b-instruct-q4_K_M
```

### 2. Set Up the Python Environment
```powershell
cd maxis-core
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

### 3. Configure (Optional)
Edit `maxis_config.yaml` to customize settings. Key options:
- `groq.api_key`: Add your Groq API key for cloud LLM fallback
- `server.port`: Change the API port (default: 8420)

### 4. Start Maxis
```powershell
python -m maxis.main
```

### 5. Connect
- **REST API**: `http://localhost:8420/api/status`
- **WebSocket**: `ws://localhost:8420/ws/chat`
- **Interactive Chat**: Open `http://localhost:8420` (web UI coming soon)

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  MAXIS CORE                      │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Identity  │  │ Emotion  │  │  Intelligence │   │
│  │   Core    │  │  Engine  │  │   (LLM Router)│   │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
│       │              │               │            │
│  ┌────▼──────────────▼───────────────▼───────┐   │
│  │           ORCHESTRATOR                     │   │
│  │  (perceive → remember → think → respond)   │   │
│  └────┬──────────────┬───────────────┬───────┘   │
│       │              │               │            │
│  ┌────▼─────┐  ┌────▼─────┐  ┌─────▼────────┐   │
│  │  Memory   │  │  Voice   │  │   Vision     │   │
│  │ (5 layers)│  │  (STT/   │  │ (Face/Object)│   │
│  │           │  │   TTS)   │  │              │   │
│  └──────────┘  └──────────┘  └──────────────┘   │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Security  │  │  System  │  │   Ambient    │   │
│  │  Daemon   │  │  Access  │  │ Intelligence │   │
│  └──────────┘  └──────────┘  └──────────────┘   │
└──────────────────────┬──────────────────────────┘
                       │
              FastAPI + WebSocket
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    Web Client    Mobile App    Other Clients
```

## Memory Layers

| Layer | Purpose | Storage |
|-------|---------|---------|
| **Working** | Active conversation context | In-memory |
| **Episodic** | Timestamped interaction records | ChromaDB |
| **Semantic** | Structured knowledge graph | NetworkX + SQLite |
| **Procedural** | Learned task patterns | SQLite |
| **Emotional** | Significant emotional events | SQLite |

## Build Phases

- [x] **Phase 1**: Memory + Identity + Text Chat
- [ ] **Phase 2**: Voice I/O (STT + TTS)
- [ ] **Phase 3**: Face Recognition
- [ ] **Phase 4**: Emotion Engine
- [ ] **Phase 5**: Screen + OS Access
- [ ] **Phase 6**: Security Daemon
- [ ] **Phase 7**: Network + Tools
- [ ] **Phase 8**: Mobile App

## License

Private project.
