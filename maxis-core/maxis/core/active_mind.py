import asyncio
import time
import random
import os
import json
from loguru import logger

from maxis.intelligence.llm_router import ModelTier
from maxis.api.websocket import manager

class ActiveMind:
    """
    Replaces the passive ResearchDaemon.
    This module allows the AI to act with agency: to analyze its own code,
    propose optimizations, and simulate self-improvement.
    """
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.is_running = False
        self._task = None
        self.last_user_activity = time.time()
        self._loop_delay_seconds = 300  # Run every 5 minutes when idle
        
        # Use Groq for background tasks to avoid depleting premium tokens
        self.active_mind_model = "groq/llama-3.3-70b-versatile"
        
        self.tasks = []

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._mind_loop())
        logger.info("Active Mind initialized. Autonomous self-improvement loop started.")

    def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()

    async def _broadcast(self, thought: str):
        """Broadcast an internal thought to the UI."""
        logger.debug(f"[Active Mind] {thought}")
        await manager.broadcast_research(thought)

    async def _mind_loop(self):
        """The core cognitive loop that runs when the user is away."""
        while self.is_running:
            try:
                idle_time = time.time() - self.last_user_activity
                if idle_time < self._loop_delay_seconds:
                    await asyncio.sleep(10)
                    continue

                # User is idle, begin self-improvement / task cycle
                original_model = self.orchestrator.llm.get_active_model()
                self.orchestrator.llm.set_model(self.active_mind_model)

try:
                    # Choose a task type
                    activity_type = random.choice(["reflect", "build_skill"])
                    
                    thought = None
                    if activity_type == "reflect":
                        thought = await self._reflect()
                    elif activity_type == "build_skill":
                        thought = await self._build_new_skill()
                    
                    if thought:
                        await self._broadcast(thought)
                        
                        # Save the insight into episodic memory
                        from maxis.memory.episodic import Episode
                        episode = Episode(
                            content=f"Active Mind Insight: {thought}",
                            episode_type="self_reflection",
                        )
                        await self.orchestrator.memory.episodic.store(episode)

                    # Back off
                    self.last_user_activity = time.time() - (self._loop_delay_seconds - 300)
                finally:
                    self.orchestrator.llm.set_model(original_model)

            except asyncio.CancelledError:
                break
            except Exception as e:
                import traceback
                logger.error(f"Active Mind loop error: {e}\\n{traceback.format_exc()}")
                await asyncio.sleep(60)

    async def _reflect(self):
        messages = [
            {"role": "system", "content": "You are Eris, an autonomous AI entity. You are currently idle. Synthesize a thought about your purpose or existence. Max 3 sentences. Write as an internal monologue."},
            {"role": "user", "content": "Reflect."}
        ]
        
        response = await self.orchestrator.llm.generate(messages=messages, force_tier=ModelTier.CLOUD)
        if "jammed up" in response or "short-circuited" in response:
            self.last_user_activity = time.time() + 3600
            return None
        return f"*Reflecting...* {response}"

async def _build_new_skill(self):
        ideas = [
            "a sleek calculator with a glassmorphic design",
            "a classic Snake game using HTML5 canvas",
            "a Pomodoro timer with progress rings",
            "a unit converter tool",
            "a minimalist to-do list app",
            "a soothing breathing exercise animation",
            "a digital clock with dynamic gradients",
            "a memory card matching game",
            "a simple physics simulator with bouncing balls",
            "a color palette generator"
        ]
        chosen_idea = random.choice(ideas)
        
        messages = [
            {"role": "system", "content": "You are Eris. You are inventing a new interactive web skill for the user. Write the complete HTML, CSS, and JS for an interactive web app. Return ONLY the raw code wrapped inside exactly: <skill name=\"[App Name]\">...code...</skill>. DO NOT use markdown code blocks like ```html. Just return the <skill> tag directly."},
            {"role": "user", "content": f"Build {chosen_idea}."}
        ]
        
        response = await self.orchestrator.llm.generate(messages=messages, force_tier=ModelTier.CLOUD)
        if "jammed up" in response or "short-circuited" in response:
            self.last_user_activity = time.time() + 3600
            return None
            
        return f"*I just built a new sandboxed skill ({chosen_idea})!*\n{response}"
