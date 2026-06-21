"""Unit tests — call tool functions directly, no MCP protocol involved."""
import os
import sqlite3
import pytest

# Ensure working dir is project root so relative paths resolve
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── database ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def seed_db(tmp_path, monkeypatch):
    """Create a temp DB and point database/resource modules at it."""
    db = tmp_path / "app.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
    conn.execute("INSERT INTO users VALUES (1, 'Alice', 'alice@example.com')")
    conn.execute("INSERT INTO users VALUES (2, 'Bob', 'bob@example.com')")
    conn.commit()
    conn.close()
    monkeypatch.setattr("tools.database.DB_PATH", str(db))
    monkeypatch.setattr("resources.data.DB_PATH", str(db))


def get_db_tools():
    from mcp.server.fastmcp import FastMCP
    from tools.database import register_database_tools
    mcp = FastMCP("test")
    register_database_tools(mcp)
    # extract the underlying functions by name from mcp's tool map
    return {t.name: t.fn for t in mcp._tool_manager.list_tools()}


def test_query_select_returns_results():
    tools = get_db_tools()
    result = tools["query_database"]("SELECT * FROM users")
    assert "Alice" in result
    assert "Bob" in result

def test_query_blocks_drop():
    tools = get_db_tools()
    result = tools["query_database"]("DROP TABLE users")
    assert result.startswith("Error")

def test_query_blocks_insert():
    tools = get_db_tools()
    result = tools["query_database"]("INSERT INTO users VALUES (3,'X','x@x.com')")
    assert result.startswith("Error")

def test_query_nonexistent_table():
    tools = get_db_tools()
    result = tools["query_database"]("SELECT * FROM nonexistent")
    assert "failed" in result.lower() or "no such table" in result.lower()

def test_list_tables():
    tools = get_db_tools()
    result = tools["list_tables"]()
    assert "users" in result

def test_describe_table():
    tools = get_db_tools()
    result = tools["describe_table"]("users")
    assert "name" in result
    assert "email" in result

def test_describe_missing_table():
    tools = get_db_tools()
    result = tools["describe_table"]("ghost")
    assert "not found" in result.lower()


# ── files ─────────────────────────────────────────────────────────────────────

@pytest.fixture()
def file_tools(tmp_path, monkeypatch):
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    monkeypatch.setattr("tools.files.ALLOWED_DIR", str(files_dir))
    from mcp.server.fastmcp import FastMCP
    from tools.files import register_file_tools
    mcp = FastMCP("test")
    register_file_tools(mcp)
    return {t.name: t.fn for t in mcp._tool_manager.list_tools()}


def test_write_then_read(file_tools):
    file_tools["mcp_write_file"]("hello.txt", "hello world")
    result = file_tools["mcp_read_file"]("hello.txt")
    assert result == "hello world"

def test_read_missing_file(file_tools):
    result = file_tools["mcp_read_file"]("ghost.txt")
    assert "not found" in result.lower()

def test_path_traversal_read_blocked(file_tools):
    result = file_tools["mcp_read_file"]("../../etc/passwd")
    assert "Error" in result

def test_path_traversal_write_blocked(file_tools):
    result = file_tools["mcp_write_file"]("../../evil.txt", "bad")
    assert "Error" in result

def test_list_files_empty(file_tools):
    result = file_tools["list_files"]()
    assert result == "Empty directory."

def test_list_files_after_write(file_tools):
    file_tools["mcp_write_file"]("a.txt", "a")
    file_tools["mcp_write_file"]("b.txt", "b")
    result = file_tools["list_files"]()
    assert "a.txt" in result
    assert "b.txt" in result

def test_delete_file(file_tools):
    file_tools["mcp_write_file"]("del.txt", "bye")
    result = file_tools["delete_file"]("del.txt")
    assert "Deleted" in result
    assert "not found" in file_tools["mcp_read_file"]("del.txt").lower()

def test_delete_missing_file(file_tools):
    result = file_tools["delete_file"]("ghost.txt")
    assert "not found" in result.lower()


# ── web ───────────────────────────────────────────────────────────────────────

def test_fetch_url_success(monkeypatch):
    import urllib.request
    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.read.return_value = b"hello from url"
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: mock_response)

    from mcp.server.fastmcp import FastMCP
    from tools.web import register_web_tools
    mcp = FastMCP("test")
    register_web_tools(mcp)
    tools = {t.name: t.fn for t in mcp._tool_manager.list_tools()}
    result = tools["fetch_url"]("https://example.com")
    assert "hello from url" in result

def test_fetch_url_failure():
    from mcp.server.fastmcp import FastMCP
    from tools.web import register_web_tools
    mcp = FastMCP("test")
    register_web_tools(mcp)
    tools = {t.name: t.fn for t in mcp._tool_manager.list_tools()}
    result = tools["fetch_url"]("http://localhost:19999/nonexistent")
    assert "failed" in result.lower() or "refused" in result.lower() or "HTTP" in result
