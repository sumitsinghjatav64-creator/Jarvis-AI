import asyncio
import json
import sys
from pathlib import Path

# Ensure absolute root is on path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from core.orchestrator import Orchestrator

async def main():
    print("=" * 70)
    print(" Jarvis / Friday Multi-Agent Local-First Architecture Demo")
    print("=" * 70)
    
    orchestrator = Orchestrator()
    
    # Example prompt combining IoT control and OS/Native API execution
    prompt = "Turn on the living room light and run a process status check"
    
    print(f"\nUser Prompt: '{prompt}'")
    print("-" * 70)
    
    # Run through the Perceive -> Plan -> Act -> Reflect cycle
    result = await orchestrator.run_workflow(prompt)
    
    print("\n" + "=" * 70)
    print(" Workflow Execution Summary")
    print("=" * 70)
    print(json.dumps(result, indent=2, default=str))
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
