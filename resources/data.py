import json
import os
import sqlite3
from mcp.server.fastmcp import FastMCP

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED_DIR = os.path.join(_BASE, "data")
DB_PATH = os.path.join(_BASE, "data", "app.db")


def register_resources(mcp: FastMCP) -> None:

    @mcp.resource("config://settings")
    def config_resource() -> str:
        """Return current server configuration as JSON."""
        return json.dumps({
            "server": "general-mcp-server",
            "version": "1.0.0",
            "db_path": DB_PATH,
            "data_dir": ALLOWED_DIR,
            "transport": "stdio"
        }, indent=2)

    @mcp.resource("db://schema")
    def db_schema_resource() -> str:
        """Return the full database schema (all CREATE TABLE statements)."""
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
            ).fetchall()
            conn.close()
            return "\n\n".join(r[0] for r in rows) if rows else "No tables found."
        except Exception as e:
            return f"Failed to read schema: {e}"

    @mcp.resource("file://{filename}")
    def file_resource(filename: str) -> str:
        """
        Read a file from the data/ directory as a resource.
        filename: relative path inside data/, e.g. 'notes.txt'.
        """
        target = os.path.normpath(os.path.join(ALLOWED_DIR, filename))
        if not target.startswith(ALLOWED_DIR):
            return "Error: path traversal is not allowed."
        if not os.path.exists(target):
            return f"File not found: {filename}"
        try:
            return open(target, encoding="utf-8").read()
        except Exception as e:
            return f"Failed to read: {e}"
