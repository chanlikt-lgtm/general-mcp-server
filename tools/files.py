import os
from mcp.server.fastmcp import FastMCP

ALLOWED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _safe_path(filename: str) -> str | None:
    """Return absolute path only if it stays inside ALLOWED_DIR, else None."""
    target = os.path.normpath(os.path.join(ALLOWED_DIR, filename))
    if not target.startswith(ALLOWED_DIR + os.sep) and target != ALLOWED_DIR:
        return None
    return target


def register_file_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def mcp_read_file(filename: str) -> str:
        """
        Read the text content of a file inside the MCP server's data/ directory.
        filename: relative path, e.g. 'notes.txt' or 'reports/summary.md'.
        Path traversal (../) is blocked — only files inside data/ are accessible.
        Use DesktopCommanderMCP's read_file to read arbitrary files on the PC.
        Returns the full file content as a string.
        """
        path = _safe_path(filename)
        if path is None:
            return "Error: path traversal is not allowed."
        if not os.path.exists(path):
            return f"File not found: {filename}"
        if not os.path.isfile(path):
            return f"Not a file: {filename}"
        try:
            return open(path, encoding="utf-8").read()
        except Exception as e:
            return f"Failed to read file: {e}"

    @mcp.tool()
    def mcp_write_file(filename: str, content: str) -> str:
        """
        Write text content to a file inside the MCP server's data/ directory.
        filename: relative path, e.g. 'output.txt' or 'reports/result.md'.
        Creates parent directories if needed. Overwrites existing files.
        Path traversal (../) is blocked — only files inside data/ are writable.
        Use DesktopCommanderMCP's write_file to write to arbitrary paths on the PC.
        Returns a confirmation message.
        """
        path = _safe_path(filename)
        if path is None:
            return "Error: path traversal is not allowed."
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w", encoding="utf-8").write(content)
            return f"Written successfully: {filename}"
        except Exception as e:
            return f"Failed to write file: {e}"

    @mcp.tool()
    def list_files(subdir: str = "") -> str:
        """
        List files and folders inside the data/ directory.
        subdir: optional relative subdirectory to list, e.g. 'reports'.
        Leave empty to list the root data/ directory.
        Returns one entry per line with a trailing '/' for directories.
        """
        path = _safe_path(subdir) if subdir else ALLOWED_DIR
        if path is None:
            return "Error: path traversal is not allowed."
        if not os.path.exists(path):
            return f"Directory not found: {subdir or 'data/'}"
        entries = sorted(os.listdir(path))
        lines = []
        for e in entries:
            suffix = "/" if os.path.isdir(os.path.join(path, e)) else ""
            lines.append(f"{e}{suffix}")
        return "\n".join(lines) if lines else "Empty directory."

    @mcp.tool()
    def delete_file(filename: str) -> str:
        """
        Delete a file from the data/ directory.
        filename: relative path inside data/, e.g. 'tmp/old.txt'.
        Path traversal (../) is blocked. Directories are not deleted by this tool.
        Returns a confirmation message.
        """
        path = _safe_path(filename)
        if path is None:
            return "Error: path traversal is not allowed."
        if not os.path.exists(path):
            return f"File not found: {filename}"
        if not os.path.isfile(path):
            return "Error: only files can be deleted with this tool."
        try:
            os.remove(path)
            return f"Deleted: {filename}"
        except Exception as e:
            return f"Failed to delete: {e}"
