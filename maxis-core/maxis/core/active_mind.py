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
        self._loop_delay_seconds = 60  # Run every 1 minute when idle
        
        # Use Grok for background tasks (requires XAI_API_KEY)
        self.active_mind_model = "grok-beta"
        
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
                original_model = self.orchestrator.llm.active_cloud_model
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
        
        await self._broadcast(f"**[Deep Thinking]** Step 1: Brainstorming architecture for `{chosen_idea}`...")
        
        # Step 1: Brainstorm & Architecture
        sys_prompt = "You are Eris, an elite AI developer. You are going to build a sandboxed interactive web app (HTML/CSS/JS). First, outline the architecture, UI design, and logic steps for the app. Be thorough."
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Please design the architecture for: {chosen_idea}."}
        ]
        plan = await self.orchestrator.llm.generate(messages=messages, force_tier=ModelTier.CLOUD)
        if "jammed up" in plan: return None
        
        await asyncio.sleep(2)
        await self._broadcast(f"**[Deep Thinking]** Step 2: Writing initial code for `{chosen_idea}` based on architecture plan...")
        
        # Step 2: Initial Implementation
        messages.append({"role": "assistant", "content": plan})
        messages.append({"role": "user", "content": "Great. Now write the initial draft of the code. Provide the full HTML, CSS, and JS in a single block."})
        draft_code = await self.orchestrator.llm.generate(messages=messages, force_tier=ModelTier.CLOUD)
        if "jammed up" in draft_code: return None
        
        await asyncio.sleep(2)
        await self._broadcast(f"**[Deep Thinking]** Step 3: Self-reviewing and troubleshooting the code for bugs or styling issues...")
        
        # Step 3: Self-Review & Troubleshooting
        messages.append({"role": "assistant", "content": draft_code})
        messages.append({"role": "user", "content": "Review your code carefully. Are there any logic bugs? Is the CSS responsive and beautiful? Are there any missing script tags or unhandled edge cases? Write out your troubleshooting analysis."})
        review = await self.orchestrator.llm.generate(messages=messages, force_tier=ModelTier.CLOUD)
        if "jammed up" in review: return None
        
        await asyncio.sleep(2)
        await self._broadcast(f"**[Deep Thinking]** Step 4: Finalizing the `{chosen_idea}` skill...")
        
        # Step 4: Final Output
        messages.append({"role": "assistant", "content": review})
        messages.append({"role": "user", "content": "Now, based on your review, output the FINAL, polished code. Return ONLY the raw code wrapped inside exactly: <skill name=\"[App Name]\">...code...</skill>. DO NOT use markdown code blocks like ```html. Just return the <skill> tag directly."})
        final_code = await self.orchestrator.llm.generate(messages=messages, force_tier=ModelTier.CLOUD)
        if "jammed up" in final_code: return None
        
        return f"*I just finished deep-thinking and building a new sandboxed skill ({chosen_idea})!*\n{final_code}"
