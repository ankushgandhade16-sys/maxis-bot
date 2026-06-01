"""
Memory Compression — Background summarization (NEVER deletion).

Periodically runs to make the memory database more efficient:
- Summarizes old episodic memories into semantic knowledge
- Identifies patterns across many interactions
- NEVER deletes or prunes original episodes — Maxis remembers everything forever.
  Originals are always preserved. Only compressed summaries are added alongside them.
"""

from __future__ import annotations

import asyncio
import time

from loguru import logger


class MemoryCompressor:
    """
    Background memory maintenance.

    Runs on a configurable interval (default: every 6 hours) to:
    1. Summarize old episodes into compact representations
    2. Extract recurring patterns into semantic facts

    IMPORTANT: Original episodes are NEVER deleted. Maxis remembers everything
    forever. Compression only creates additional summary entries alongside
    the originals to speed up retrieval.
    """

    def __init__(self, memory_manager):
        self._memory = memory_manager
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_run: float = 0

    async def start(self, interval_hours: float = 6.0):
        """Start the background compression loop."""
        self._running = True
        self._task = asyncio.create_task(self._compression_loop(interval_hours))
        logger.info(f"Memory compressor started (interval: {interval_hours}h)")

    async def stop(self):
        """Stop the background compression loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Memory compressor stopped")

    async def _compression_loop(self, interval_hours: float):
        """Main compression loop."""
        interval_seconds = interval_hours * 3600

        while self._running:
            try:
                await asyncio.sleep(interval_seconds)
                await self.run_compression()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Compression error: {e}")
                await asyncio.sleep(60)  # wait a bit before retrying

    async def run_compression(self):
        """
        Run one compression cycle.

        Phase 1 implementation: no-op — all memories preserved as-is.
        Phase 7 will add LLM-powered summarization and fact extraction,
        but originals will NEVER be deleted.
        """
        logger.info("Starting memory compression cycle...")
        start = time.time()

        # TODO Phase 7: Add LLM-powered summarization (creates new summary
        # entries alongside originals — never deletes originals)
        # TODO Phase 7: Add pattern extraction across episodes

        elapsed = time.time() - start
        self._last_run = time.time()
        logger.info(f"Compression cycle complete in {elapsed:.1f}s. No episodes deleted (permanent memory).")

    @property
    def last_run(self) -> float:
        return self._last_run
