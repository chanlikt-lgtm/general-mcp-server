"""
Connect the general-mcp-server to OpenAI Agents SDK.
OpenAI added native MCP support in March 2026 via MCPServerStdio.

Install: pip install openai
Requires: OPENAI_API_KEY in environment or .env file
"""
import asyncio
import os
from agents import Agent, Runner
from agents.mcp import MCPServerStdio

PYTHON = r"C:\Users\User\AppData\Local\Programs\Python\Python311\python.exe"
SERVER = r"E:\claude\MCP\server.py"

# Load API key from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(r"E:\claude\MCP\.env")
except ImportError:
    pass

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


async def main():
    if not OPENAI_API_KEY:
        print("ERROR: Set OPENAI_API_KEY in E:\\claude\\MCP\\.env or as env var")
        return

    # Wire MCP server into OpenAI agent
    async with MCPServerStdio(
        name="general-mcp-server",
        params={
            "command": PYTHON,
            "args": [SERVER],
        }
    ) as mcp_server:

        # List tools discovered from MCP
        tools = await mcp_server.list_tools()
        print(f"Tools discovered: {[t.name for t in tools]}\n")

        # Create OpenAI agent with MCP tools attached
        agent = Agent(
            name="MCP Assistant",
            instructions="You are a helpful assistant. Use the available tools to answer questions.",
            mcp_servers=[mcp_server],
            model="gpt-4o",
        )

        # Run a query
        result = await Runner.run(
            agent,
            input="Write a file called hello.txt with the content 'Hello from OpenAI + MCP!', then read it back."
        )
        print("Agent response:")
        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
