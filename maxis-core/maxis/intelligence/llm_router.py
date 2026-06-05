"""
LLM Router — Intelligent routing between local Ollama and cloud Groq API.

Routes queries based on complexity, urgency, and available token budget.
Simple questions go local. Complex multi-step reasoning goes to the API
only when necessary. Maxis is transparent about this if asked.
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import AsyncIterator, Optional

import httpx
from loguru import logger
from google import genai
from google.genai import types

from maxis.config import get_config
from maxis.intelligence.token_budget import TokenBudget


class ModelTier(str, Enum):
    LOCAL = "local"    # Ollama (Qwen2.5-7B)
    CLOUD = "cloud"    # Gemini API


class LLMRouter:
    """
    Routes LLM queries to the best available model.

    Decision factors:
    - Complexity: simple → local, complex → cloud
    - Token budget: if cloud budget is low, force local
    - Availability: if Ollama is down, try cloud (and vice versa)
    """

    def __init__(self):
        self._config = get_config()
        self._token_budget = TokenBudget()
        self._ollama_client: Optional[httpx.AsyncClient] = None
        self._gemini_client: Optional[genai.Client] = None
        self._ollama_available = False
        self._cloud_available = False
        self._active_cloud_model: str = self._config.gemini.model

    async def initialize(self):
        """Set up HTTP clients and check availability."""
        self._ollama_client = httpx.AsyncClient(
            base_url=self._config.ollama.base_url,
            timeout=120.0,
        )

        # Initialize Gemini API
        if self._config.gemini.api_key:
            try:
                self._gemini_client = genai.Client(api_key=self._config.gemini.api_key)
                self._cloud_available = True
            except Exception as e:
                logger.error(f"Failed to initialize Gemini API: {e}")

        # Check Ollama availability
        await self._check_ollama()

        # Load token budget
        await self._token_budget.load()

        logger.info(
            f"LLM Router initialized — "
            f"Ollama: {'✓' if self._ollama_available else '✗'}, "
            f"Cloud API: {'✓' if self._cloud_available else '✗'}"
        )

    async def _check_ollama(self):
        """Check if Ollama is running and the model is available."""
        try:
            resp = await self._ollama_client.get("/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                target = self._config.ollama.model
                self._ollama_available = any(
                    target.split(":")[0] in m for m in models
                ) or len(models) > 0
            else:
                self._ollama_available = False
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            self._ollama_available = False

    def classify_complexity(self, messages: list[dict]) -> ModelTier:
        """
        Determine which model tier to use based on the query complexity.
        """
        import os
        is_cloud_env = os.getenv("MAXIS_ENV") == "cloud"
        
        # If deployed on the cloud, always use Gemini to avoid hitting local hardware
        if is_cloud_env and self._cloud_available and self._token_budget.has_budget():
            return ModelTier.CLOUD

        # If running locally, but no cloud is available, force local
        if not self._cloud_available or not self._token_budget.has_budget():
            return ModelTier.LOCAL

        # --- LOCAL MODE HEURISTICS ---
        # Get the last user message
        last_msg = ""
        for m in reversed(messages):
            if m["role"] == "user":
                last_msg = m["content"]
                break

        if not last_msg:
            return ModelTier.LOCAL

        # Short messages are almost always fine locally
        word_count = len(last_msg.split())
        if word_count < 30:
            return ModelTier.LOCAL

        # Complex indicators
        complex_keywords = [
            "analyze", "explain in detail", "compare", "write code",
            "debug", "implement", "step by step", "research",
            "comprehensive", "elaborate", "design", "architecture",
        ]
        is_complex = any(kw in last_msg.lower() for kw in complex_keywords)

        if is_complex and self._token_budget.has_budget():
            return ModelTier.CLOUD

        return ModelTier.LOCAL

    async def generate(
        self,
        messages: list[dict],
        system_prompt: str = "",
        temperature: float | None = None,
        force_tier: ModelTier | None = None,
    ) -> str:
        """
        Generate a response using the appropriate model.
        """
        tier = force_tier or self.classify_complexity(messages)

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        try:
            if tier == ModelTier.LOCAL and self._ollama_available:
                return await self._generate_ollama(full_messages, temperature)
            elif tier == ModelTier.CLOUD and self._cloud_available:
                return await self._generate_gemini(full_messages, temperature)
            elif self._ollama_available:
                return await self._generate_ollama(full_messages, temperature)
            elif self._cloud_available:
                return await self._generate_gemini(full_messages, temperature)
            else:
                return "I'm having trouble connecting to my language models right now. Neither local nor cloud are available."
        except Exception as e:
            error_str = str(e)
            logger.error(f"LLM generation failed on {tier} (model={self._active_cloud_model}): {error_str}")
            try:
                if tier == ModelTier.LOCAL and self._cloud_available:
                    return await self._generate_gemini(full_messages, temperature)
                elif tier == ModelTier.CLOUD and self._ollama_available:
                    return await self._generate_ollama(full_messages, temperature)
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")

            if "503" in error_str or "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                return "*Sigh* The cloud servers are completely jammed up right now and my brain is lagging hard. Can you give me like ten seconds and ask that again?"
            elif "404" in error_str or "not found" in error_str.lower() or "deprecated" in error_str.lower():
                return f"*Confused buzzing* The model I was using seems to have been retired... Let the creator know to check the model settings. (Error: {error_str[:120]})"
            else:
                return f"*Glitches slightly* Whoa, something just short-circuited in my core processing... give me a second and try again?"

    async def _generate_ollama(
        self,
        messages: list[dict],
        temperature: float | None = None,
    ) -> str:
        """Generate via local Ollama."""
        config = self._config.ollama

        payload = {
            "model": config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature or config.temperature,
                "top_p": config.top_p,
                "num_ctx": config.context_length,
            },
        }

        resp = await self._ollama_client.post("/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    async def _generate_gemini(
        self,
        messages: list[dict],
        temperature: float | None = None,
    ) -> str:
        """Generate via Gemini API."""
        config = self._config.gemini
        
        # Convert standard OpenAI format messages to Gemini format
        gemini_messages = []
        system_instruction = None
        for m in messages:
            if m["role"] == "system":
                system_instruction = m["content"]
            elif m["role"] == "user":
                gemini_messages.append(types.Content(role="user", parts=[types.Part.from_text(text=m["content"])]))
            elif m["role"] == "assistant":
                gemini_messages.append(types.Content(role="model", parts=[types.Part.from_text(text=m["content"])]))

        logger.debug(f"Generating via Gemini ({self._active_cloud_model})...")
        
        # Call API asynchronously using asyncio.to_thread since the genai client might be sync
        active_model = self._active_cloud_model
        def call_gemini():
            return self._gemini_client.models.generate_content(
                model=active_model,
                contents=gemini_messages,
                config=types.GenerateContentConfig(
                    temperature=temperature or config.temperature,
                    system_instruction=system_instruction,
                )
            )

        import asyncio
        resp = None
        for attempt in range(4):
            try:
                resp = await asyncio.to_thread(call_gemini)
                break
            except Exception as e:
                last_error = e
                if "503" in str(e) or "429" in str(e):
                    if attempt < 3:
                        await asyncio.sleep(2 ** attempt)  # exponential backoff: 1s, 2s, 4s
                        continue
                raise last_error

        if resp and getattr(resp, "usage_metadata", None):
            total_tokens = resp.usage_metadata.total_token_count
            await self._token_budget.record_usage("gemini", total_tokens)

        return resp.text

    def set_model(self, model_name: str):
        """Switch the active cloud model at runtime."""
        self._active_cloud_model = model_name
        logger.info(f"Cloud model switched to: {model_name}")

    @property
    def active_cloud_model(self) -> str:
        return self._active_cloud_model

    def get_status(self) -> dict:
        """Get router status info."""
        return {
            "ollama_available": self._ollama_available,
            "cloud_available": self._cloud_available,
            "daily_remaining": self._token_budget.remaining_daily,
            "local_model": self._config.ollama.model,
            "cloud_model": self._active_cloud_model,
        }

    async def shutdown(self):
        """Clean up HTTP clients."""
        if self._ollama_client:
            await self._ollama_client.aclose()
        await self._token_budget.save()
