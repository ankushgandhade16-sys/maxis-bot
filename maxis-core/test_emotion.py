import asyncio
from maxis.core.orchestrator import Orchestrator

async def test():
    orch = Orchestrator()
    await orch.initialize()
    
    # 1. Check initial state
    print("Initial State:", orch.emotional_state.summary())
    
    # 2. Process a normal message
    print("\n--- Sending polite message ---")
    resp = await orch.process_message("Hello, how are you today? You are doing a great job.", is_voice=False)
    print("Response:", resp)
    print("New State:", orch.emotional_state.summary())
    
    # 3. Process an aggressive message
    print("\n--- Sending rude message ---")
    resp = await orch.process_message("You are so stupid and useless! I hate you.", is_voice=False)
    print("Response:", resp)
    print("New State:", orch.emotional_state.summary())

if __name__ == "__main__":
    asyncio.run(test())
