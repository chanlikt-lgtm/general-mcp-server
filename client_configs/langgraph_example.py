"""
Wire general-mcp-server into a LangGraph ReAct agent using DeepSeek.
Supports both stdio (local) and HTTP (production) transport.

Install: pip install langgraph langchain-openai langchain-mcp-adapters
Requires: DEEPSEEK_API_KEY in E:\claude\MCP\.env
"""
import asyncio
import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

try:
    from dotenv import load_dotenv
    load_dotenv(r"E:\claude\MCP\.env")
except ImportError:
    pass

PYTHON   = r"C:\Users\User\AppData\Local\Programs\Python\Python311\python.exe"
SERVER   = r"E:\claude\MCP\server.py"
HTTP_URL = "http://localhost:8080/mcp"
USE_HTTP = False   # set True to use running HTTP server instead of stdio


def get_server_config():
    if USE_HTTP:
        return {"url": HTTP_URL, "transport": "streamable_http"}
    return {"command": PYTHON, "args": [SERVER], "transport": "stdio"}


async def main():
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("ERROR: Set DEEPSEEK_API_KEY in E:\\claude\\MCP\\.env")
        return

    # v0.3.0 API — no longer a context manager
    client = MultiServerMCPClient({"general-mcp-server": get_server_config()})
    tools = await client.get_tools()
    print(f"Tools available to LangGraph ({len(tools)}): {[t.name for t in tools]}\n")

    model = ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )
    agent = create_react_agent(model, tools)

    tests = [
        "Calculate: sqrt(256) + 2**8. Show your working.",
        "Write a file called langgraph_test.txt with content 'LangGraph + MCP works!', then read it back.",
        "Fetch https://httpbin.org/uuid and tell me the UUID you got.",
    ]

    for i, question in enumerate(tests, 1):
        print(f"=== Test {i} ===")
        result = await agent.ainvoke({"messages": [{"role": "user", "content": question}]})
        print(result["messages"][-1].content)
        print()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main())
