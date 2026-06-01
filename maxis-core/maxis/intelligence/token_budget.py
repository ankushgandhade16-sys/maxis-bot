"""
Token Budget — Rolling usage tracker for API providers.

Maxis knows her daily and monthly allocation. She makes intelligent
decisions about which model to use based on available budget.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from loguru import logger

from maxis.config import get_config, SQLITE_DIR


class TokenBudget:
    """
    Tracks token usage across API providers with daily/monthly rolling windows.
    """

    def __init__(self):
        self._config = get_config()
        self._usage_file = SQLITE_DIR / "token_usage.json"
        self._usage: dict = {
            "groq": {
                "daily": [],   # list of (timestamp, token_count) tuples
                "monthly": [],
            }
        }

    async def load(self):
        """Load usage data from disk."""
        if self._usage_file.exists():
            try:
                with open(self._usage_file, "r") as f:
                    self._usage = json.load(f)
                # Clean old entries
                self._prune_old_entries()
                logger.debug(f"Token budget loaded. Daily remaining: {self.remaining_daily}")
            except Exception as e:
                logger.warning(f"Failed to load token budget: {e}")

    async def save(self):
        """Persist usage data to disk."""
        try:
            self._prune_old_entries()
            with open(self._usage_file, "w") as f:
                json.dump(self._usage, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save token budget: {e}")

    async def record_usage(self, provider: str, tokens: int):
        """Record token usage for a provider."""
        now = time.time()

        if provider not in self._usage:
            self._usage[provider] = {"daily": [], "monthly": []}

        self._usage[provider]["daily"].append([now, tokens])
        self._usage[provider]["monthly"].append([now, tokens])

        # Auto-save periodically
        await self.save()

    def has_budget(self, provider: str = "gemini") -> bool:
        """Check if there's remaining budget for a provider."""
        return self.remaining_daily > 0

    @property
    def remaining_daily(self) -> int:
        """Remaining daily tokens for Gemini."""
        max_daily = self._config.gemini.max_daily_tokens
        used = self._get_daily_usage("gemini")
        return max(0, max_daily - used)

    @property
    def remaining_monthly(self) -> int:
        """Remaining monthly tokens."""
        max_monthly = self._config.gemini.max_daily_tokens * 30
        used = self._get_monthly_usage("gemini")
        return max(0, max_monthly - used)

    def _get_daily_usage(self, provider: str) -> int:
        """Total tokens used today."""
        if provider not in self._usage:
            return 0

        cutoff = time.time() - 86400  # 24 hours
        return sum(
            tokens for ts, tokens in self._usage[provider].get("daily", [])
            if ts > cutoff
        )

    def _get_monthly_usage(self, provider: str) -> int:
        """Total tokens used this month."""
        if provider not in self._usage:
            return 0

        cutoff = time.time() - (30 * 86400)  # ~30 days
        return sum(
            tokens for ts, tokens in self._usage[provider].get("monthly", [])
            if ts > cutoff
        )

    def _prune_old_entries(self):
        """Remove entries older than their window."""
        now = time.time()
        day_cutoff = now - 86400
        month_cutoff = now - (30 * 86400)

        for provider in self._usage:
            self._usage[provider]["daily"] = [
                entry for entry in self._usage[provider].get("daily", [])
                if entry[0] > day_cutoff
            ]
            self._usage[provider]["monthly"] = [
                entry for entry in self._usage[provider].get("monthly", [])
                if entry[0] > month_cutoff
            ]

    def get_usage_summary(self) -> str:
        """Human-readable usage summary."""
        daily_used = self._get_daily_usage("gemini")
        daily_max = self._config.gemini.max_daily_tokens
        
        return (
            f"Gemini API usage — "
            f"Today: {daily_used:,}/{daily_max:,} tokens ({daily_used/daily_max*100:.0f}%)"
        )
