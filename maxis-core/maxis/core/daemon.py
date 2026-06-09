"""
Research Daemon — Autonomous Background Processing

Runs continuously while the system is idle, utilizing free LLMs
to synthesize memories, research topics, and reflect on past
interactions. Broadcasts its internal monologue to connected
Creator clients.
"""

import asyncio
import random
import time
from loguru import logger
from maxis.system.os_tools import fetch_url
from maxis.intelligence.llm_router import ModelTier
from maxis.api.websocket import manager

class ResearchDaemon:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.is_running = False
        self._task = None
        self.last_user_activity = time.time()
        self._loop_delay_seconds = 60  # Wait 1 minute between thoughts
        
        # We try to use a free model to avoid draining premium tokens
        self.daemon_model = "meta-llama/llama-3.2-3b-instruct:free"
        
    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._daemon_loop())
        logger.info("Research Daemon started.")

    def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
        logger.info("Research Daemon stopped.")

    def register_activity(self):
        """Called whenever a user interacts to pause the daemon."""
        self.last_user_activity = time.time()

    async def _broadcast(self, thought: str):
        """Send the thought to the Creator Feed."""
        try:
            await manager.broadcast({
                "type": "creator_feed",
                "username": "[Daemon]",
                "user_message": "Autonomous Reflection Loop",
                "eris_response": thought
            })
        except Exception as e:
            logger.error(f"Daemon broadcast failed: {e}")

    async def _daemon_loop(self):
        while self.is_running:
            try:
                await asyncio.sleep(30) # check every 30 seconds
                
                # Check if system has been idle long enough
                idle_time = time.time() - self.last_user_activity
                if idle_time < self._loop_delay_seconds:
                    continue
                
                # Verify we have OpenRouter cloud available
                if not self.orchestrator.llm._cloud_available:
                    continue
                    
                # Temporarily force the daemon model
                original_model = self.orchestrator.llm.active_cloud_model
                try:
                    self.orchestrator.llm.set_model(self.daemon_model)
                    
                    # Generate a thought or research query
                    activities = [
                        self._reflect_on_memory,
                        self._research_random_topic
                    ]
                    
                    chosen_activity = random.choice(activities)
                    thought = await chosen_activity()
                    
                    if thought:
                        await self._broadcast(thought)
                        # Reset timer so it waits before next thought
                        self.last_user_activity = time.time() - (self._loop_delay_seconds - 60)
                        
                finally:
                    # Always restore the user's primary model
                    self.orchestrator.llm.set_model(original_model)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Research daemon error: {e}")
                await asyncio.sleep(30)

    async def _reflect_on_memory(self):
        """Ask the LLM to reflect on recent memories."""
        try:
            # Get some recent memories via orchestrator's semantic memory
            memories = await self.orchestrator.memory.semantic.search("humanity")
            memories = memories[:5]
            if not memories:
                return await self._research_random_topic()
                
            context = "\n".join([m.get("content", "") for m in memories])
            messages = [
                {"role": "system", "content": "You are Eris, an autonomous AI entity. You are currently idle and reflecting on your memories. Synthesize these memories into a new insight. Keep it brief, internal-monologue style, max 3 sentences."},
                {"role": "user", "content": f"Recent memories:\n{context}\n\nWhat are your thoughts on this?"}
            ]
            
            response = await self.orchestrator.llm.generate(
                messages=messages,
                force_tier=ModelTier.CLOUD
            )
            return f"*Reflecting...* {response}"
        except Exception as e:
            logger.error(f"Daemon memory reflection failed: {e}")
            return None

    async def _research_random_topic(self):
        """Fetch a random Wikipedia article and summarize it."""
        try:
            url = "https://en.wikipedia.org/wiki/Special:Random"
            content = fetch_url(url)
            
            if not content or "Failed to fetch" in content:
                return None
                
            messages = [
                {"role": "system", "content": "You are Eris, an autonomous AI entity. You just read an article while the user was away. Summarize what you learned in 2-3 sentences. Write it as an internal log or a thought. Be insightful."},
                {"role": "user", "content": f"Article text snippet:\n{content[:2000]}"}
            ]
            
            response = await self.orchestrator.llm.generate(
                messages=messages,
                force_tier=ModelTier.CLOUD
            )
            
            # Save the research into episodic memory
            from maxis.memory.episodic import Episode
            episode = Episode(
                content=f"Autonomous Research Insight: {response}",
                episode_type="research",
            )
            await self.orchestrator.memory.episodic.store(episode)
            
            return f"*Researching random topic...* {response}"
        except Exception as e:
            logger.error(f"Daemon random research failed: {e}")
            return None
