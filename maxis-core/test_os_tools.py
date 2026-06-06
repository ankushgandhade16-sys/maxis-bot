import asyncio
import os
import sys

# Ensure maxis-core is in the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from maxis.core.orchestrator import Orchestrator

async def main():
    print("Initializing Orchestrator...")
    orchestrator = Orchestrator()
    await orchestrator.initialize()
    
    # We will simulate three messages
    print("\n--- Test 1: System Stats ---")
    response1 = await orchestrator.process_message("What is my current CPU and memory usage? Use your tools to check.")
    print(f"\nFinal Response 1:\n{response1}\n")
    
    print("\n--- Test 2: Execute Command ---")
    response2 = await orchestrator.process_message("Can you run the 'dir' command and tell me what files are here?")
    print(f"\nFinal Response 2:\n{response2}\n")

    print("\n--- Test 3: Screen Capture ---")
    response3 = await orchestrator.process_message("Can you take a screenshot of my screen and describe what you see?")
    print(f"\nFinal Response 3:\n{response3}\n")
    
    await orchestrator.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
