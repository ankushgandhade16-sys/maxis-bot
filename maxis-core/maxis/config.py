"""
Global configuration for the MAXIS system.

All paths, model names, hardware limits, and API keys are managed here.
Loaded from maxis_config.yaml with environment variable overrides.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
CHROMA_DIR = DATA_DIR / "chroma"
SQLITE_DIR = DATA_DIR / "sqlite"
FACES_DIR = DATA_DIR / "faces"
MODELS_DIR = DATA_DIR / "models"
LOGS_DIR = DATA_DIR / "logs"

# Ensure data directories exist
for d in [DATA_DIR, CHROMA_DIR, SQLITE_DIR, FACES_DIR, MODELS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ── Configuration Models ─────────────────────────────────────────────────────

class OllamaConfig(BaseSettings):
    """Local LLM via Ollama."""
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b-instruct-q4_K_M"
    context_length: int = 8192
    temperature: float = 0.7
    top_p: float = 0.9


class GroqConfig(BaseSettings):
    """Cloud LLM fallback via Groq."""
    api_key: str = Field(default="", description="Groq API key")
    model: str = "llama-3.3-70b-versatile"
    max_daily_tokens: int = 100_000
    max_monthly_tokens: int = 3_000_000
    temperature: float = 0.7


class MemoryConfig(BaseSettings):
    """Memory system settings."""
    # Working memory
    max_working_turns: int = 20  # conversation turns to keep in active context
    max_working_tokens: int = 4096  # max tokens for working memory injection

    # Episodic memory
    episodic_collection: str = "maxis_episodes"
    episodic_top_k: int = 10  # results per retrieval query

    # Semantic memory
    knowledge_db: str = "knowledge.db"

    # Compression
    compression_interval_hours: int = 6
    min_episode_age_hours: int = 24  # don't compress recent episodes
    compression_batch_size: int = 50

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384


class VoiceConfig(BaseSettings):
    """Voice I/O settings (Phase 2)."""
    stt_model: str = "medium.en"  # faster-whisper model size
    stt_device: str = "cuda"
    stt_compute_type: str = "float16"

    tts_voice: str = "af_heart"  # Kokoro voice style
    tts_speed: float = 1.0

    vad_threshold: float = 0.5
    sample_rate: int = 16000
    chunk_duration_ms: int = 30


class VisionConfig(BaseSettings):
    """Vision system settings (Phase 3+)."""
    camera_index: int = 0
    active_fps: float = 2.0  # during conversation
    idle_fps: float = 0.2  # motion detection only
    face_match_threshold: float = 0.45  # cosine similarity

    yolo_model: str = "yolo11n.pt"
    clip_model: str = "ViT-B/32"


class SecurityConfig(BaseSettings):
    """Security monitoring settings (Phase 6)."""
    enabled: bool = False  # opt-in, requires admin
    poll_interval_seconds: int = 5
    baseline_learning_hours: int = 48
    alert_on_unknown_outbound: bool = True


class HardwareConfig(BaseSettings):
    """Hardware limits and thermal management."""
    gpu_vram_total_mb: int = 8192
    gpu_vram_reserved_mb: int = 512  # OS/driver overhead
    gpu_temp_throttle_c: float = 85.0
    gpu_temp_critical_c: float = 95.0
    cpu_temp_throttle_c: float = 90.0
    max_ram_usage_mb: int = 6144  # Maxis's own RAM budget


class ServerConfig(BaseSettings):
    """API server settings."""
    host: str = "0.0.0.0"
    port: int = 8420
    cors_origins: list[str] = ["*"]
    log_level: str = "info"


class GeminiConfig(BaseSettings):
    """Configuration for Google Gemini API."""
    api_key: str = Field(default="", description="Gemini API key")
    model: str = "gemini-3.5-flash"
    temperature: float = 0.7
    max_daily_tokens: int = 1_000_000


class CloudConfig(BaseSettings):
    """Cloud infrastructure settings (Supabase & Pinecone)."""
    database_url: str = Field(default="", description="PostgreSQL connection string")
    pinecone_api_key: str = Field(default="", description="Pinecone API key")
    pinecone_index: str = "maxis"


class MaxisConfig(BaseSettings):
    """Root configuration combining all subsystems."""
    ollama: OllamaConfig = OllamaConfig()
    groq: GroqConfig = GroqConfig()
    gemini: GeminiConfig = GeminiConfig()
    memory: MemoryConfig = MemoryConfig()
    voice: VoiceConfig = VoiceConfig()
    vision: VisionConfig = VisionConfig()
    security: SecurityConfig = SecurityConfig()
    hardware: HardwareConfig = HardwareConfig()
    server: ServerConfig = ServerConfig()
    cloud: CloudConfig = CloudConfig()

    class Config:
        env_prefix = "MAXIS_"
        env_nested_delimiter = "__"


def load_config() -> MaxisConfig:
    """Load configuration from YAML file with env var overrides."""
    config_path = PROJECT_ROOT / "maxis_config.yaml"

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f) or {}

        # Build nested config from YAML, env vars override
        return MaxisConfig(**yaml_data)

    return MaxisConfig()


# ── Singleton ────────────────────────────────────────────────────────────────

_config: Optional[MaxisConfig] = None


def get_config() -> MaxisConfig:
    """Get the global config singleton."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
