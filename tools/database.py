import os
import sqlite3
from mcp.server.fastmcp import FastMCP

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_BASE, "data", "app.db")


def register_database_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def query_database(sql: str) -> str:
        """
        Execute a read-only SELECT query on the SQLite database at data/app.db.
        Returns results as pipe-separated rows with a header line.
        Only SELECT statements are permitted — all others are blocked for safety.
        Example: SELECT * FROM users LIMIT 10
        """
        if not sql.strip().upper().startswith("SELECT"):
            return "Error: only SELECT queries are permitted."
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            rows = cursor.fetchall()
            conn.close()
            if not rows:
                return "No results found."
            headers = list(rows[0].keys())
            lines = [" | ".join(headers), "-" * 60]
            for row in rows:
                lines.append(" | ".join(str(v) for v in row))
            return "\n".join(lines)
        except Exception as e:
            return f"Query failed: {e}"

    @mcp.tool()
    def list_tables() -> str:
        """
        List all tables in the SQLite database at data/app.db.
        Returns one table name per line.
        """
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            conn.close()
            return "\n".join(r[0] for r in rows) if rows else "No tables found."
        except Exception as e:
            return f"Failed to list tables: {e}"

    @mcp.tool()
    def describe_table(table: str) -> str:
        """
        Show the column names and types for a given table in data/app.db.
        table: exact table name (use list_tables to discover names).
        Returns one 'column_name | type' line per column.
        """
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            conn.close()
            if not rows:
                return f"Table '{table}' not found or has no columns."
            return "\n".join(f"{r[1]} | {r[2]}" for r in rows)
        except Exception as e:
            return f"Failed to describe table: {e}"
