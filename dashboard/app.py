"""
MCP Server Dashboard — FastAPI on port 8081.

Provides:
  GET  /             → HTML dashboard UI
  GET  /api/status   → MCP server health + uptime + tool count
  GET  /api/tools    → full list of tools with schema
  POST /api/call     → call a tool (proxied to MCP HTTP server)
  GET  /api/log      → recent call log (last 100)
  GET  /api/stats    → aggregate statistics

Run: py -m uvicorn dashboard.app:app --port 8081 --reload
  or: py dashboard/app.py
"""

import json
import os
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ── config ────────────────────────────────────────────────────────────────────
MCP_BASE     = "http://localhost:8080"
MCP_ENDPOINT = f"{MCP_BASE}/mcp"
DASHBOARD_PORT = 8081
_START_TIME  = time.time()
_BASE        = Path(__file__).resolve().parent.parent   # E:\claude\MCP

# ── in-memory call log ────────────────────────────────────────────────────────
_log: deque[dict] = deque(maxlen=200)
_stats = {"total": 0, "success": 0, "error": 0, "total_ms": 0.0}
_session_id: str | None = None

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="MCP Dashboard", docs_url=None, redoc_url=None)


# ── helpers ───────────────────────────────────────────────────────────────────

async def _collect_sse(response: httpx.Response) -> dict:
    """Read an SSE stream and return the first data: JSON payload."""
    text = ""
    async for chunk in response.aiter_text():
        text += chunk
        for line in text.splitlines():
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    try:
                        return json.loads(data)
                    except json.JSONDecodeError:
                        pass
    return {}


async def _mcp_init() -> str | None:
    """Initialize MCP session, return session-id."""
    global _session_id
    body = {
        "jsonrpc": "2.0", "id": 0, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcp-dashboard", "version": "1.0"},
        },
    }
    hdrs = {"Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
        async with client.stream("POST", MCP_ENDPOINT, json=body, headers=hdrs) as r:
            r.raise_for_status()
            sid = r.headers.get("mcp-session-id")
            if sid:
                _session_id = sid
            await _collect_sse(r)   # consume init response
    return _session_id


async def _mcp_request(method: str, payload: dict) -> dict:
    """Send a JSON-RPC request to the MCP HTTP server, managing session."""
    global _session_id
    if not _session_id:
        await _mcp_init()

    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": payload}
    hdrs = {"Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"}
    if _session_id:
        hdrs["mcp-session-id"] = _session_id

    async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
        async with client.stream("POST", MCP_ENDPOINT, json=body, headers=hdrs) as r:
            if r.status_code == 400:
                # session expired — reinit
                _session_id = None
                await _mcp_init()
                if _session_id:
                    hdrs["mcp-session-id"] = _session_id
                # rebuild request with new session
            else:
                r.raise_for_status()
                return await _collect_sse(r)

    # retry after reinit
    async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
        async with client.stream("POST", MCP_ENDPOINT, json=body, headers=hdrs) as r:
            r.raise_for_status()
            return await _collect_sse(r)


# ── API routes ────────────────────────────────────────────────────────────────

@app.get("/api/status")
async def api_status():
    uptime_s = int(time.time() - _START_TIME)
    h, rem   = divmod(uptime_s, 3600)
    m, s     = divmod(rem, 60)
    uptime   = f"{h:02d}:{m:02d}:{s:02d}"
    try:
        data  = await _mcp_request("tools/list", {})
        tools = data.get("result", {}).get("tools", [])
        return {"mcp_online": True, "tool_count": len(tools),
                "dashboard_uptime": uptime, "mcp_url": MCP_BASE}
    except Exception as e:
        return {"mcp_online": False, "tool_count": 0,
                "dashboard_uptime": uptime, "mcp_url": MCP_BASE,
                "error": str(e)}


@app.get("/api/tools")
async def api_tools():
    try:
        data  = await _mcp_request("tools/list", {})
        tools = data.get("result", {}).get("tools", [])
        return {"tools": tools, "count": len(tools)}
    except Exception as e:
        raise HTTPException(502, f"Cannot reach MCP server: {e}")


@app.post("/api/call")
async def api_call(request: Request):
    body = await request.json()
    tool_name = body.get("tool")
    args      = body.get("args", {})
    if not tool_name:
        raise HTTPException(400, "Missing 'tool' field")

    t0 = time.time()
    ts = datetime.now().strftime("%H:%M:%S")
    try:
        data   = await _mcp_request("tools/call", {"name": tool_name, "arguments": args})
        result = data.get("result", {})
        content = result.get("content", [])
        # extract text from content blocks
        text = "\n".join(
            c.get("text", json.dumps(c)) for c in content
            if isinstance(c, dict)
        ) if isinstance(content, list) else str(content)
        elapsed = round((time.time() - t0) * 1000)
        entry = {"ts": ts, "tool": tool_name, "args": args,
                 "result": text, "elapsed_ms": elapsed, "ok": True}
        _log.appendleft(entry)
        _stats["total"]   += 1
        _stats["success"] += 1
        _stats["total_ms"] += elapsed
        return {"ok": True, "result": text, "elapsed_ms": elapsed}
    except Exception as e:
        elapsed = round((time.time() - t0) * 1000)
        err_str = str(e)
        entry = {"ts": ts, "tool": tool_name, "args": args,
                 "result": err_str, "elapsed_ms": elapsed, "ok": False}
        _log.appendleft(entry)
        _stats["total"] += 1
        _stats["error"] += 1
        return {"ok": False, "result": err_str, "elapsed_ms": elapsed}


@app.get("/api/log")
async def api_log(limit: int = 100):
    return {"log": list(_log)[:limit], "total_recorded": len(_log)}


@app.get("/api/stats")
async def api_stats():
    total = _stats["total"]
    avg   = round(_stats["total_ms"] / total) if total else 0
    rate  = round(_stats["success"] / total * 100) if total else 0
    return {
        "total_calls": total,
        "success":     _stats["success"],
        "errors":      _stats["error"],
        "success_rate": f"{rate}%",
        "avg_latency_ms": avg,
    }


# ── Dashboard HTML (single-file SPA) ─────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(_HTML)


# ── HTML ──────────────────────────────────────────────────────────────────────
_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MCP Server Dashboard</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3e;
    --accent: #7c6af7; --accent2: #5eead4; --text: #e2e8f0;
    --muted: #64748b; --green: #4ade80; --red: #f87171; --yellow: #fbbf24;
    --radius: 10px; --font: 'Segoe UI', system-ui, sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: var(--font);
         font-size: 14px; min-height: 100vh; }

  /* ── top bar ── */
  header { background: var(--surface); border-bottom: 1px solid var(--border);
           padding: 0 24px; height: 56px; display: flex; align-items: center;
           gap: 16px; position: sticky; top: 0; z-index: 100; }
  header h1 { font-size: 18px; font-weight: 700; color: var(--accent);
              letter-spacing: -.3px; }
  header h1 span { color: var(--accent2); }
  .badge { padding: 3px 10px; border-radius: 20px; font-size: 12px;
           font-weight: 600; }
  .badge.online { background: #14532d; color: var(--green); }
  .badge.offline { background: #450a0a; color: var(--red); }
  .hdr-meta { margin-left: auto; display: flex; gap: 20px; color: var(--muted);
              font-size: 12px; }
  .hdr-meta span b { color: var(--text); }

  /* ── layout ── */
  .layout { display: grid; grid-template-columns: 280px 1fr; min-height: calc(100vh - 56px); }

  /* ── sidebar ── */
  aside { background: var(--surface); border-right: 1px solid var(--border);
          padding: 16px 0; display: flex; flex-direction: column; }
  .search-wrap { padding: 0 14px 12px; }
  input[type=search] { width: 100%; background: var(--bg); border: 1px solid var(--border);
    border-radius: 8px; padding: 7px 12px; color: var(--text); font-size: 13px;
    outline: none; }
  input[type=search]:focus { border-color: var(--accent); }
  .tool-count { padding: 0 14px 8px; font-size: 11px; color: var(--muted); }
  .tool-list { overflow-y: auto; flex: 1; }
  .tool-item { padding: 9px 14px; cursor: pointer; border-left: 3px solid transparent;
               transition: all .15s; }
  .tool-item:hover { background: rgba(124,106,247,.08); }
  .tool-item.active { border-left-color: var(--accent);
                      background: rgba(124,106,247,.12); }
  .tool-item .name { font-weight: 600; font-size: 13px; }
  .tool-item .desc { font-size: 11px; color: var(--muted); margin-top: 2px;
                     white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* ── main area ── */
  main { padding: 20px; display: flex; flex-direction: column; gap: 20px;
         overflow-y: auto; }

  /* ── stat cards ── */
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
  .card { background: var(--surface); border: 1px solid var(--border);
          border-radius: var(--radius); padding: 16px; }
  .card .label { font-size: 11px; color: var(--muted); text-transform: uppercase;
                 letter-spacing: .5px; margin-bottom: 6px; }
  .card .value { font-size: 26px; font-weight: 700; }
  .card .value.green { color: var(--green); }
  .card .value.accent { color: var(--accent); }
  .card .value.yellow { color: var(--yellow); }
  .card .value.accent2 { color: var(--accent2); }

  /* ── tool tester ── */
  .tester { background: var(--surface); border: 1px solid var(--border);
             border-radius: var(--radius); padding: 20px; }
  .tester h2 { font-size: 15px; font-weight: 700; margin-bottom: 4px; }
  .tester .hint { font-size: 12px; color: var(--muted); margin-bottom: 16px; }
  .tool-schema { margin-bottom: 16px; }
  .tool-schema .tool-title { font-size: 17px; font-weight: 700;
                              color: var(--accent); margin-bottom: 6px; }
  .tool-schema .tool-desc { font-size: 12px; color: var(--muted); line-height: 1.6;
                             margin-bottom: 14px; }
  .fields { display: flex; flex-direction: column; gap: 10px; }
  .field { display: flex; flex-direction: column; gap: 4px; }
  .field label { font-size: 12px; font-weight: 600; color: var(--accent2); }
  .field label .req { color: var(--red); margin-left: 2px; }
  .field label .type { color: var(--muted); font-weight: 400;
                       font-size: 11px; margin-left: 6px; }
  .field input, .field textarea {
    background: var(--bg); border: 1px solid var(--border);
    border-radius: 7px; padding: 8px 12px; color: var(--text);
    font-size: 13px; font-family: var(--font); outline: none; width: 100%; }
  .field input:focus, .field textarea:focus { border-color: var(--accent); }
  .field textarea { resize: vertical; min-height: 80px; }
  .field .fdesc { font-size: 11px; color: var(--muted); }
  .btn-row { margin-top: 14px; display: flex; gap: 10px; align-items: center; }
  button { padding: 9px 22px; border-radius: 8px; border: none; cursor: pointer;
           font-size: 13px; font-weight: 600; transition: opacity .15s; }
  button:hover { opacity: .85; }
  .btn-run { background: var(--accent); color: #fff; }
  .btn-clear { background: var(--border); color: var(--muted); }
  .elapsed { font-size: 12px; color: var(--muted); }

  /* ── result box ── */
  .result-box { margin-top: 16px; }
  .result-box .result-hdr { font-size: 12px; color: var(--muted);
                             margin-bottom: 6px; display: flex; gap: 8px;
                             align-items: center; }
  .result-box .result-hdr .ok   { color: var(--green); font-weight: 700; }
  .result-box .result-hdr .fail { color: var(--red); font-weight: 700; }
  pre.result { background: var(--bg); border: 1px solid var(--border);
               border-radius: 8px; padding: 14px; font-size: 12px; line-height: 1.6;
               overflow-x: auto; white-space: pre-wrap; word-break: break-word;
               max-height: 360px; overflow-y: auto; }

  /* ── call log ── */
  .log-panel { background: var(--surface); border: 1px solid var(--border);
               border-radius: var(--radius); padding: 20px; }
  .log-panel h2 { font-size: 15px; font-weight: 700; margin-bottom: 14px;
                  display: flex; align-items: center; gap: 10px; }
  .log-panel h2 .refresh-dot { width: 8px; height: 8px; border-radius: 50%;
    background: var(--green); animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th { text-align: left; color: var(--muted); font-weight: 600; padding: 6px 10px;
       border-bottom: 1px solid var(--border); text-transform: uppercase;
       font-size: 11px; letter-spacing: .4px; }
  td { padding: 7px 10px; border-bottom: 1px solid rgba(42,45,62,.6);
       vertical-align: top; }
  tr:hover td { background: rgba(255,255,255,.02); }
  .ok-dot   { display: inline-block; width: 7px; height: 7px; border-radius: 50%;
              background: var(--green); margin-right: 5px; }
  .fail-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%;
              background: var(--red); margin-right: 5px; }
  td.mono { font-family: monospace; color: var(--muted); font-size: 11px;
            max-width: 340px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .empty-log { text-align: center; padding: 32px; color: var(--muted); }
  .no-tool { text-align: center; padding: 60px 20px; color: var(--muted); }
  .no-tool .icon { font-size: 48px; margin-bottom: 12px; }
</style>
</head>
<body>

<header>
  <h1>MCP <span>Dashboard</span></h1>
  <span id="status-badge" class="badge offline">● OFFLINE</span>
  <div class="hdr-meta">
    <span>Uptime <b id="hdr-uptime">--</b></span>
    <span>Tools <b id="hdr-tools">--</b></span>
    <span>MCP <b>localhost:8080</b></span>
  </div>
</header>

<div class="layout">
  <!-- sidebar -->
  <aside>
    <div class="search-wrap">
      <input type="search" id="tool-search" placeholder="Search tools…" oninput="filterTools()">
    </div>
    <div class="tool-count" id="tool-count-label">Loading…</div>
    <div class="tool-list" id="tool-list"></div>
  </aside>

  <!-- main -->
  <main>
    <!-- stats row -->
    <div class="stats">
      <div class="card">
        <div class="label">Total Calls</div>
        <div class="value accent" id="s-total">0</div>
      </div>
      <div class="card">
        <div class="label">Successful</div>
        <div class="value green" id="s-ok">0</div>
      </div>
      <div class="card">
        <div class="label">Errors</div>
        <div class="value" id="s-err" style="color:var(--red)">0</div>
      </div>
      <div class="card">
        <div class="label">Avg Latency</div>
        <div class="value accent2" id="s-lat">— ms</div>
      </div>
    </div>

    <!-- tool tester -->
    <div class="tester">
      <h2>Tool Tester</h2>
      <p class="hint">Select a tool from the sidebar to test it.</p>
      <div id="tester-body">
        <div class="no-tool"><div class="icon">🔧</div>Select a tool on the left</div>
      </div>
    </div>

    <!-- call log -->
    <div class="log-panel">
      <h2><span class="refresh-dot"></span> Live Call Log</h2>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Tool</th>
            <th>Status</th>
            <th>Latency</th>
            <th>Result preview</th>
          </tr>
        </thead>
        <tbody id="log-body">
          <tr><td colspan="5" class="empty-log">No calls yet — test a tool above!</td></tr>
        </tbody>
      </table>
    </div>
  </main>
</div>

<script>
let allTools = [];
let selectedTool = null;

// ── boot ───────────────────────────────────────────────────────────────────
async function boot() {
  await loadStatus();
  await loadTools();
  await loadStats();
  await loadLog();
  setInterval(loadStatus, 5000);
  setInterval(loadStats,  4000);
  setInterval(loadLog,    3000);
}

// ── status ──────────────────────────────────────────────────────────────────
async function loadStatus() {
  try {
    const d = await fetch('/api/status').then(r => r.json());
    const badge = document.getElementById('status-badge');
    if (d.mcp_online) {
      badge.textContent = '● ONLINE';
      badge.className = 'badge online';
    } else {
      badge.textContent = '● OFFLINE';
      badge.className = 'badge offline';
    }
    document.getElementById('hdr-uptime').textContent = d.dashboard_uptime;
    document.getElementById('hdr-tools').textContent  = d.tool_count;
  } catch(e) {}
}

// ── tools ────────────────────────────────────────────────────────────────────
async function loadTools() {
  try {
    const d = await fetch('/api/tools').then(r => r.json());
    allTools = d.tools || [];
    renderSidebar(allTools);
  } catch(e) {
    document.getElementById('tool-count-label').textContent = 'MCP offline';
  }
}

function renderSidebar(tools) {
  const list  = document.getElementById('tool-list');
  const label = document.getElementById('tool-count-label');
  label.textContent = `${tools.length} tool${tools.length !== 1 ? 's' : ''}`;
  if (!tools.length) {
    list.innerHTML = '<div class="tool-item"><div class="name" style="color:var(--muted)">No tools found</div></div>';
    return;
  }
  list.innerHTML = tools.map(t => `
    <div class="tool-item" data-name="${t.name}" onclick="selectTool('${t.name}')">
      <div class="name">${t.name}</div>
      <div class="desc">${shortDesc(t.description || '')}</div>
    </div>`).join('');
}

function shortDesc(desc) {
  const first = desc.split('\n')[0].trim();
  return first.length > 60 ? first.slice(0, 57) + '…' : first;
}

function filterTools() {
  const q = document.getElementById('tool-search').value.toLowerCase();
  const filtered = allTools.filter(t =>
    t.name.toLowerCase().includes(q) ||
    (t.description || '').toLowerCase().includes(q)
  );
  renderSidebar(filtered);
  // re-highlight selected
  if (selectedTool) {
    const el = document.querySelector(`.tool-item[data-name="${selectedTool}"]`);
    if (el) el.classList.add('active');
  }
}

// ── tester ───────────────────────────────────────────────────────────────────
function selectTool(name) {
  selectedTool = name;
  document.querySelectorAll('.tool-item').forEach(el => el.classList.remove('active'));
  const el = document.querySelector(`.tool-item[data-name="${name}"]`);
  if (el) el.classList.add('active');

  const tool = allTools.find(t => t.name === name);
  if (!tool) return;

  const schema = tool.inputSchema || {};
  const props  = schema.properties || {};
  const req    = schema.required || [];

  const fieldsHtml = Object.entries(props).map(([key, prop]) => {
    const isReq   = req.includes(key);
    const type    = prop.type || 'string';
    const desc    = prop.description || '';
    const isLong  = desc.toLowerCase().includes('code') || type === 'object' || type === 'array';
    const input   = isLong
      ? `<textarea id="arg-${key}" placeholder="${desc.slice(0,80)}"></textarea>`
      : `<input type="text" id="arg-${key}" placeholder="${desc.slice(0,80)}">`;
    return `<div class="field">
      <label>
        ${key}${isReq ? '<span class="req">*</span>' : ''}
        <span class="type">${type}</span>
      </label>
      ${input}
      ${desc ? `<div class="fdesc">${desc.slice(0,200)}</div>` : ''}
    </div>`;
  }).join('');

  const noProps = Object.keys(props).length === 0;

  document.getElementById('tester-body').innerHTML = `
    <div class="tool-schema">
      <div class="tool-title">${tool.name}</div>
      <div class="tool-desc">${(tool.description || '').replace(/\n/g,'<br>')}</div>
      <div class="fields">${fieldsHtml}</div>
    </div>
    <div class="btn-row">
      <button class="btn-run" onclick="runTool()">▶ Run</button>
      <button class="btn-clear" onclick="clearResult()">Clear</button>
      <span class="elapsed" id="elapsed-label"></span>
    </div>
    <div class="result-box" id="result-box" style="display:none">
      <div class="result-hdr" id="result-hdr"></div>
      <pre class="result" id="result-pre"></pre>
    </div>
  `;
}

async function runTool() {
  if (!selectedTool) return;
  const tool   = allTools.find(t => t.name === selectedTool);
  const props  = (tool.inputSchema || {}).properties || {};
  const args   = {};
  for (const key of Object.keys(props)) {
    const el  = document.getElementById(`arg-${key}`);
    if (!el) continue;
    let val = el.value.trim();
    if (!val) continue;
    const type = props[key].type;
    if (type === 'integer' || type === 'number') val = Number(val);
    else if (type === 'boolean') val = val === 'true' || val === '1';
    args[key] = val;
  }

  document.querySelector('.btn-run').textContent = '⏳ Running…';
  document.querySelector('.btn-run').disabled = true;
  document.getElementById('elapsed-label').textContent = '';

  const t0 = Date.now();
  try {
    const d = await fetch('/api/call', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tool: selectedTool, args}),
    }).then(r => r.json());

    const ms   = Date.now() - t0;
    const box  = document.getElementById('result-box');
    const hdr  = document.getElementById('result-hdr');
    const pre  = document.getElementById('result-pre');
    box.style.display = 'block';
    hdr.innerHTML = d.ok
      ? `<span class="ok">✓ Success</span> — ${d.elapsed_ms}ms`
      : `<span class="fail">✗ Error</span> — ${d.elapsed_ms}ms`;
    pre.textContent = d.result || '(no output)';
    document.getElementById('elapsed-label').textContent = `${ms}ms`;
    await loadLog();
    await loadStats();
  } finally {
    document.querySelector('.btn-run').textContent = '▶ Run';
    document.querySelector('.btn-run').disabled = false;
  }
}

function clearResult() {
  const box = document.getElementById('result-box');
  if (box) box.style.display = 'none';
  document.getElementById('elapsed-label').textContent = '';
}

// ── stats ────────────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const d = await fetch('/api/stats').then(r => r.json());
    document.getElementById('s-total').textContent = d.total_calls;
    document.getElementById('s-ok').textContent    = d.success;
    document.getElementById('s-err').textContent   = d.errors;
    document.getElementById('s-lat').textContent   = d.avg_latency_ms ? `${d.avg_latency_ms}ms` : '— ms';
  } catch(e) {}
}

// ── log ──────────────────────────────────────────────────────────────────────
async function loadLog() {
  try {
    const d    = await fetch('/api/log?limit=50').then(r => r.json());
    const body = document.getElementById('log-body');
    if (!d.log.length) {
      body.innerHTML = '<tr><td colspan="5" class="empty-log">No calls yet — test a tool above!</td></tr>';
      return;
    }
    body.innerHTML = d.log.map(e => `
      <tr>
        <td>${e.ts}</td>
        <td><b>${e.tool}</b></td>
        <td>${e.ok
          ? '<span class="ok-dot"></span>OK'
          : '<span class="fail-dot"></span>Error'}</td>
        <td>${e.elapsed_ms}ms</td>
        <td class="mono">${esc(String(e.result || '').split('\n')[0])}</td>
      </tr>`).join('');
  } catch(e) {}
}

function esc(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

boot();
</script>
</body>
</html>"""


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print(f"Starting MCP Dashboard on http://localhost:{DASHBOARD_PORT}")
    print(f"Monitoring MCP server at {MCP_BASE}")
    uvicorn.run("dashboard.app:app", host="0.0.0.0", port=DASHBOARD_PORT, reload=False)
