"""In-process MCP tests — call FastMCP methods directly (no subprocess)."""
import json
import os
import sqlite3
import pytest
import pytest_asyncio

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture()
async def mcp_server(tmp_path, monkeypatch):
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    db_path = str(tmp_path / "app.db")

    monkeypatch.setattr("tools.database.DB_PATH", db_path)
    monkeypatch.setattr("resources.data.DB_PATH", db_path)
    monkeypatch.setattr("tools.files.ALLOWED_DIR", str(files_dir))
    monkeypatch.setattr("resources.data.ALLOWED_DIR", str(files_dir))

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE products (id INTEGER, name TEXT, price REAL)")
    conn.execute("INSERT INTO products VALUES (1, 'Widget', 9.99)")
    conn.commit()
    conn.close()

    from mcp.server.fastmcp import FastMCP
    from tools.database import register_database_tools
    from tools.files import register_file_tools
    from tools.web import register_web_tools
    from resources.data import register_resources
    from tools.prompts import register_prompts

    mcp = FastMCP("test-server")
    register_database_tools(mcp)
    register_file_tools(mcp)
    register_web_tools(mcp)
    register_resources(mcp)
    register_prompts(mcp)
    return mcp


# ── Step 4: tools ──────────────────────────────────────────────────────────────

async def test_all_tools_registered(mcp_server):
    tools = await mcp_server.list_tools()
    names = [t.name for t in tools]
    for expected in ["query_database", "list_tables", "describe_table",
                     "mcp_read_file", "mcp_write_file", "list_files", "delete_file",
                     "fetch_url", "call_api"]:
        assert expected in names, f"Missing tool: {expected}"

async def test_all_tools_have_descriptions(mcp_server):
    tools = await mcp_server.list_tools()
    for t in tools:
        assert t.description and len(t.description) > 10, \
            f"Tool '{t.name}' has no meaningful description"

async def test_no_duplicate_tools(mcp_server):
    tools = await mcp_server.list_tools()
    names = [t.name for t in tools]
    assert len(names) == len(set(names))

async def test_tool_schema_has_required_args(mcp_server):
    tools = await mcp_server.list_tools()
    db_tool = next(t for t in tools if t.name == "query_database")
    assert "sql" in db_tool.inputSchema["properties"]

async def test_query_database_executes(mcp_server):
    result = await mcp_server.call_tool("query_database", {"sql": "SELECT * FROM products"})
    text = result[0].text if hasattr(result[0], "text") else str(result[0])
    assert "Widget" in text

async def test_query_blocked(mcp_server):
    result = await mcp_server.call_tool("query_database", {"sql": "DELETE FROM products"})
    text = result[0].text if hasattr(result[0], "text") else str(result[0])
    assert "Error" in text

async def test_write_then_read_via_mcp(mcp_server):
    await mcp_server.call_tool("mcp_write_file", {"filename": "test.txt", "content": "mcp works"})
    result = await mcp_server.call_tool("mcp_read_file", {"filename": "test.txt"})
    text = result[0].text if hasattr(result[0], "text") else str(result[0])
    assert "mcp works" in text

async def test_path_traversal_blocked(mcp_server):
    result = await mcp_server.call_tool("mcp_read_file", {"filename": "../../secret"})
    text = result[0].text if hasattr(result[0], "text") else str(result[0])
    assert "Error" in text

async def test_server_survives_bad_input(mcp_server):
    await mcp_server.call_tool("query_database", {"sql": "DROP TABLE products"})
    tools = await mcp_server.list_tools()
    assert len(tools) > 0


# ── Step 5: resources ─────────────────────────────────────────────────────────

async def test_config_resource_readable(mcp_server):
    content = await mcp_server.read_resource("config://settings")
    text = content[0].content if hasattr(content[0], "content") else str(content[0])
    assert "test-server" in text or "general-mcp-server" in text or "version" in text

async def test_config_resource_valid_json(mcp_server):
    content = await mcp_server.read_resource("config://settings")
    text = content[0].content if hasattr(content[0], "content") else str(content[0])
    parsed = json.loads(text)
    assert "version" in parsed

async def test_db_schema_resource(mcp_server):
    content = await mcp_server.read_resource("db://schema")
    text = content[0].content if hasattr(content[0], "content") else str(content[0])
    assert "products" in text

async def test_resources_listed(mcp_server):
    resources = await mcp_server.list_resources()
    uris = [str(r.uri) for r in resources]
    assert any("config" in u for u in uris)
    assert any("schema" in u or "db" in u for u in uris)

async def test_resource_templates_listed(mcp_server):
    templates = await mcp_server.list_resource_templates()
    uris = [t.uriTemplate for t in templates]
    assert any("file" in u for u in uris)


# ── Step 6: prompts ───────────────────────────────────────────────────────────

async def test_all_prompts_registered(mcp_server):
    prompts = await mcp_server.list_prompts()
    names = [p.name for p in prompts]
    for expected in ["analyze", "debug", "summarize"]:
        assert expected in names, f"Missing prompt: {expected}"

async def test_prompt_renders_with_args(mcp_server):
    result = await mcp_server.get_prompt("analyze", {"dataset": "sales", "goal": "find top products"})
    text = result.messages[0].content.text
    assert "sales" in text
    assert "top products" in text

async def test_prompt_args_declared(mcp_server):
    prompts = await mcp_server.list_prompts()
    analyze = next(p for p in prompts if p.name == "analyze")
    arg_names = [a.name for a in analyze.arguments]
    assert "dataset" in arg_names
    assert "goal" in arg_names
