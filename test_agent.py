import asyncio
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

async def main():
    # Initialize the agent with your chosen client and instructions
    agent = Agent(
        client=OpenAIChatClient(),
        instructions="You are JARVIS. Give me the TLDR in exactly 5 words."
    )
    
    # Run the agent
    result = await agent.run("Summarize the Three Laws of Robotics")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())