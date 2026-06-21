import ast
import os
import subprocess
import sys
import tempfile
from mcp.server.fastmcp import FastMCP

_BASE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE, "data")
PYTHON   = sys.executable

# Modules blocked in run_python_snippet
_BLOCKED_IMPORTS = {
    "os", "subprocess", "shutil", "socket", "requests",
    "urllib", "http", "ftplib", "smtplib", "paramiko",
    "ctypes", "cffi", "importlib", "builtins",
}


def _safe(filename: str) -> str | None:
    target = os.path.normpath(os.path.join(DATA_DIR, filename))
    return target if target.startswith(DATA_DIR) else None


def _check_imports(code: str) -> list[str]:
    """Return list of blocked imports found in code."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    blocked = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                root = name.split(".")[0]
                if root in _BLOCKED_IMPORTS:
                    blocked.append(root)
    return blocked


def register_code_dev_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def format_code(code: str, language: str = "python") -> str:
        """
        Format source code using Black (Python) or basic indent normalization (others).
        code: source code string to format.
        language: 'python' (default) — uses Black formatter.
        Returns the formatted code string.
        """
        if language.lower() != "python":
            return f"Error: only 'python' is supported for formatting."
        try:
            import black
            formatted = black.format_str(code, mode=black.Mode(line_length=88))
            return formatted
        except black.InvalidInput as e:
            return f"Format error: {e}"
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def lint_python(code: str) -> str:
        """
        Lint Python code using Ruff and report issues.
        code: Python source code string to lint.
        Returns a list of issues (line, column, rule, message) or 'No issues found.'
        """
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False,
                encoding="utf-8"
            ) as f:
                f.write(code)
                tmp = f.name
            result = subprocess.run(
                ["ruff", "check", "--output-format=text", tmp],
                capture_output=True, text=True, timeout=15
            )
            os.unlink(tmp)
            output = result.stdout.strip()
            if not output:
                return "No issues found. ✅"
            # strip temp file path from output
            return output.replace(tmp, "<code>")
        except FileNotFoundError:
            return "Error: ruff not found. Run: pip install ruff"
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def run_python_snippet(code: str, timeout: int = 10) -> str:
        """
        Run a small Python code snippet in a subprocess and return its output.
        Blocked imports: os, subprocess, shutil, socket, requests, urllib, http, smtplib, ctypes.
        timeout: max execution time in seconds (default 10, max 30).
        Returns stdout + stderr combined, or a timeout/error message.
        Use for calculations, data transformations, and algorithm testing.
        """
        blocked = _check_imports(code)
        if blocked:
            return f"Error: blocked import(s): {', '.join(blocked)}. Network/system access is not allowed."
        timeout = max(1, min(30, int(timeout)))
        try:
            result = subprocess.run(
                [PYTHON, "-c", code],
                capture_output=True, text=True,
                timeout=timeout, encoding="utf-8", errors="replace"
            )
            out = (result.stdout + result.stderr).strip()
            return out or f"(no output, exit code {result.returncode})"
        except subprocess.TimeoutExpired:
            return f"Error: snippet timed out after {timeout}s."
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def count_lines(filename: str) -> str:
        """
        Count lines, blank lines, comment lines, and code lines in a source file in data/.
        filename: relative path inside data/, e.g. 'script.py' or 'app.js'.
        Returns a breakdown of line types and total character count.
        """
        path = _safe(filename)
        if not path: return "Error: path traversal not allowed."
        if not os.path.exists(path): return f"File not found: {filename}"
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            total    = len(lines)
            blank    = sum(1 for l in lines if l.strip() == "")
            comments = sum(1 for l in lines if l.strip().startswith(("#", "//", "--", "/*", "*")))
            code     = total - blank - comments
            chars    = sum(len(l) for l in lines)
            return (
                f"File     : {filename}\n"
                f"Total    : {total} lines\n"
                f"Code     : {code} lines\n"
                f"Comments : {comments} lines\n"
                f"Blank    : {blank} lines\n"
                f"Chars    : {chars}"
            )
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def git_status(repo_path: str = "") -> str:
        """
        Run git status on a repository and return the current state.
        repo_path: absolute path to the git repo (default: E:\\claude\\MCP).
        Returns branch name, staged/unstaged changes, and untracked files.
        """
        path = repo_path.strip() or _BASE
        if not os.path.exists(path):
            return f"Path not found: {path}"
        try:
            def git(cmd):
                r = subprocess.run(
                    ["git"] + cmd, cwd=path,
                    capture_output=True, text=True, timeout=10,
                    encoding="utf-8", errors="replace"
                )
                return r.stdout.strip() or r.stderr.strip()

            branch  = git(["rev-parse", "--abbrev-ref", "HEAD"])
            status  = git(["status", "--short"])
            log     = git(["log", "--oneline", "-5"])
            return (
                f"Branch  : {branch}\n\n"
                f"Status:\n{status or '(clean)'}\n\n"
                f"Last 5 commits:\n{log or '(no commits)'}"
            )
        except FileNotFoundError:
            return "Error: git not found in PATH."
        except Exception as e:
            return f"Error: {e}"
