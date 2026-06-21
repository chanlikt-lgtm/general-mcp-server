"""
Cloud entry point for the MCP HTTP server.

Differences from server_http.py:
  - Port read from $PORT environment variable (Render / Railway / Fly.io set this)
  - HOST from $HOST env var (default 0.0.0.0)
  - Adds GET /health endpoint for Render health checks
  - Adds GET / endpoint with a simple status page
  - Optional API key auth via $MCP_API_KEY env var (if set, all /mcp requests must
    include header:  Authorization: Bearer <key>)
  - data/ directory writes are disabled in read-only cloud environments;
    file/db tools degrade gracefully

Usage:
    uvicorn cloud_server:app --host 0.0.0.0 --port $PORT
"""
import os
import sys
import time
from pathlib import Path

# ── resolve path so imports work from any cwd ─────────────────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from fastapi import Request
from fastapi.responses import JSONResponse, HTMLResponse
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse as StarletteJSON, HTMLResponse as StarletteHTML
from starlette.routing import Route

# ── tool registrations ────────────────────────────────────────────────────────
from tools.database        import register_database_tools
from tools.files           import register_file_tools
from tools.web             import register_web_tools
from tools.prompts         import register_prompts
from tools.text_math       import register_text_math_tools
from tools.system          import register_system_tools
from tools.data            import register_data_tools
from tools.datetime_tools  import register_datetime_tools
from tools.network         import register_network_tools
from tools.image           import register_image_tools
from tools.pdf_office      import register_pdf_office_tools
from tools.crypto_security import register_crypto_security_tools
from tools.code_dev        import register_code_dev_tools
from tools.audio_video     import register_audio_video_tools
from tools.ml_utils        import register_ml_utils_tools
from tools.web_scraping    import register_web_scraping_tools
from tools.archive         import register_archive_tools
from resources.data        import register_resources

# ── config ────────────────────────────────────────────────────────────────────
PORT        = int(os.environ.get("PORT", 8080))
HOST        = os.environ.get("HOST", "0.0.0.0")
MCP_API_KEY = os.environ.get("MCP_API_KEY", "")   # optional auth
_START      = time.time()

# ensure data/ directory exists for file/db tools
(Path(_HERE) / "data").mkdir(exist_ok=True)

# ── MCP server ────────────────────────────────────────────────────────────────
mcp = FastMCP(
    name="general-mcp-server",
    instructions=(
        "General-purpose MCP server with 50+ tools: "
        "database, files, web, math, system, data, datetime, network, "
        "image, PDF/office, crypto, code, audio, ML, web scraping, archive."
    ),
    host=HOST,
    port=PORT,
)

register_database_tools(mcp)
register_file_tools(mcp)
register_web_tools(mcp)
register_resources(mcp)
register_prompts(mcp)
register_text_math_tools(mcp)
register_system_tools(mcp)
register_data_tools(mcp)
register_datetime_tools(mcp)
register_network_tools(mcp)
register_image_tools(mcp)
register_pdf_office_tools(mcp)
register_crypto_security_tools(mcp)
register_code_dev_tools(mcp)
register_audio_video_tools(mcp)
register_ml_utils_tools(mcp)
register_web_scraping_tools(mcp)
register_archive_tools(mcp)

# ── build route handlers ──────────────────────────────────────────────────────

async def health(request):
    """Render health check endpoint."""
    uptime = int(time.time() - _START)
    return StarletteJSON({"status": "ok", "uptime_s": uptime, "server": "general-mcp-server"})


async def root(request):
    """Simple landing page."""
    tools = mcp._tool_manager.list_tools()
    n     = len(tools)
    names = ", ".join(t.name for t in tools[:10])
    html = f"""<!DOCTYPE html>
<html><head><title>MCP Server</title>
<style>body{{font-family:system-ui,sans-serif;max-width:700px;margin:60px auto;
padding:0 20px;background:#0f1117;color:#e2e8f0}}
h1{{color:#7c6af7}}a{{color:#5eead4}}.box{{background:#1a1d27;
border:1px solid #2a2d3e;border-radius:10px;padding:20px;margin:16px 0}}
code{{background:#0f1117;padding:2px 8px;border-radius:4px;font-size:13px}}</style>
</head><body>
<h1>&#9889; MCP Server</h1>
<p>General-purpose MCP server with <strong>{n} tools</strong> running on this endpoint.</p>
<div class="box">
  <b>MCP endpoint:</b><br>
  <code>[this-url]/mcp</code><br><br>
  <b>Health check:</b> <a href="/health">/health</a><br>
  <b>Protocol:</b> MCP streamable-http (JSON-RPC 2.0 over SSE)
</div>
<div class="box">
  <b>First 10 tools:</b><br>
  <code>{names}{'...' if n > 10 else ''}</code>
</div>
<div class="box">
  <b>Connect from Claude Desktop</b> &mdash; add to <code>claude_desktop_config.json</code>:<br><br>
  <code>{{"mcpServers":{{"general-mcp-server":{{"type":"http","url":"https://YOUR-URL/mcp"}}}}}}</code>
</div>
</body></html>"""
    return StarletteHTML(html)


# ── get MCP's Starlette app and inject our routes into it ────────────────────
# FastMCP's streamable_http_app() returns a Starlette app with /mcp already wired.
# We inject /health and / BEFORE the MCP route so they take priority.
_mcp_asgi = mcp.streamable_http_app()
_mcp_asgi.router.routes.insert(0, Route("/health", health))
_mcp_asgi.router.routes.insert(0, Route("/", root))

# ── optional API key middleware ────────────────────────────────────────────────
if MCP_API_KEY:
    from starlette.middleware.base import BaseHTTPMiddleware

    class AuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path in ("/", "/health"):
                return await call_next(request)
            auth = request.headers.get("Authorization", "")
            if auth != f"Bearer {MCP_API_KEY}":
                return StarletteJSON({"error": "Unauthorized"}, status_code=401)
            return await call_next(request)

    _mcp_asgi.add_middleware(AuthMiddleware)

# ── the final ASGI app ────────────────────────────────────────────────────────
app = _mcp_asgi


# ── local dev entry point ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print(f"Starting cloud MCP server on http://{HOST}:{PORT}")
    print(f"MCP endpoint : http://localhost:{PORT}/mcp")
    print(f"Health check : http://localhost:{PORT}/health")
    if MCP_API_KEY:
        print(f"Auth         : Bearer token required")
    uvicorn.run("cloud_server:app", host=HOST, port=PORT, reload=False)
