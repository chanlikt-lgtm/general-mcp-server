"""
Connect general-mcp-server to DeepSeek via OpenAI-compatible API.
DeepSeek V3/V4 supports OpenAI tool-calling format natively.

Requires: DEEPSEEK_API_KEY in E:\claude\MCP\.env
Get key:  https://platform.deepseek.com/api_keys
"""
import asyncio
import os
from agents import Agent, Runner
from agents.mcp import MCPServerStdio
from agents import set_tracing_disabled
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

PYTHON = r"C:\Users\User\AppData\Local\Programs\Python\Python311\python.exe"
SERVER = r"E:\claude\MCP\server.py"

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(r"E:\claude\MCP\.env")
except ImportError:
    pass

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"   # deepseek-chat = V3/V4, deepseek-reasoner = R1

set_tracing_disabled(True)  # disable OpenAI tracing — not needed for DeepSeek


async def main():
    if not DEEPSEEK_API_KEY:
        print("ERROR: Set DEEPSEEK_API_KEY in E:\\claude\\MCP\\.env")
        return

    # DeepSeek client (OpenAI-compatible)
    deepseek_client = AsyncOpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )

    async with MCPServerStdio(
        name="general-mcp-server",
        params={
            "command": PYTHON,
            "args": [SERVER],
        }
    ) as mcp_server:

        tools = await mcp_server.list_tools()
        print(f"Tools discovered: {[t.name for t in tools]}\n")

        agent = Agent(
            name="DeepSeek MCP Assistant",
            instructions=(
                "You are a helpful assistant with access to file, database, "
                "web, and math tools. Use them to answer questions accurately."
            ),
            mcp_servers=[mcp_server],
            model=OpenAIChatCompletionsModel(
                model=DEEPSEEK_MODEL,
                openai_client=deepseek_client,
            ),
        )

        # Test 1: math
        print("=== Test 1: calculate ===")
        r = await Runner.run(agent, input="What is sqrt(1764) + 2**8?")
        print(r.final_output)

        # Test 2: file write + read
        print("\n=== Test 2: file tools ===")
        r = await Runner.run(
            agent,
            input="Write a file called deepseek_test.txt with content 'DeepSeek + MCP works!' then read it back."
        )
        print(r.final_output)

        # Test 3: web fetch
        print("\n=== Test 3: web fetch ===")
        r = await Runner.run(
            agent,
            input="Fetch https://httpbin.org/json and summarize what you get."
        )
        print(r.final_output)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main())
