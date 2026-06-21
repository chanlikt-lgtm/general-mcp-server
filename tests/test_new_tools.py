"""Unit tests for system, data, datetime, and network tools."""
import csv
import json
import os
import pytest

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_tools(register_fn):
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("test")
    register_fn(mcp)
    return {t.name: t.fn for t in mcp._tool_manager.list_tools()}


# ── system ────────────────────────────────────────────────────────────────────

def test_system_info():
    from tools.system import register_system_tools
    tools = get_tools(register_system_tools)
    result = tools["system_info"]()
    assert "CPU" in result and "RAM" in result and "OS" in result

def test_run_command():
    from tools.system import register_system_tools
    tools = get_tools(register_system_tools)
    result = tools["run_command"]("echo hello")
    assert "hello" in result.lower()

def test_run_command_blocked():
    from tools.system import register_system_tools
    tools = get_tools(register_system_tools)
    result = tools["run_command"]("del important.txt")
    assert "blocked" in result.lower()

def test_get_env_specific():
    from tools.system import register_system_tools
    tools = get_tools(register_system_tools)
    result = tools["get_env"]("PATH")
    assert len(result) > 0 and "not set" not in result

def test_get_env_list():
    from tools.system import register_system_tools
    tools = get_tools(register_system_tools)
    result = tools["get_env"]()
    assert "PATH" in result

def test_list_processes():
    from tools.system import register_system_tools
    tools = get_tools(register_system_tools)
    result = tools["mcp_list_processes"]("python")
    assert "python" in result.lower() or "No matching" in result


# ── data ──────────────────────────────────────────────────────────────────────

@pytest.fixture()
def data_tools(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.data.DATA_DIR", str(tmp_path))
    from tools.data import register_data_tools
    return get_tools(register_data_tools)

def test_write_read_csv(data_tools, tmp_path):
    rows = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
    data_tools["write_csv"]("test.csv", json.dumps(rows))
    result = data_tools["read_csv"]("test.csv")
    assert "Alice" in result and "Bob" in result

def test_query_csv_eq(data_tools, tmp_path):
    rows = [{"city": "London", "pop": "9000000"}, {"city": "Paris", "pop": "2100000"}]
    data_tools["write_csv"]("cities.csv", json.dumps(rows))
    result = data_tools["query_csv"]("cities.csv", "city", "London", "eq")
    assert "London" in result and "Paris" not in result

def test_query_csv_contains(data_tools):
    rows = [{"name": "Alice Smith"}, {"name": "Bob Jones"}]
    data_tools["write_csv"]("names.csv", json.dumps(rows))
    result = data_tools["query_csv"]("names.csv", "name", "Alice", "contains")
    assert "Alice" in result and "Bob" not in result

def test_write_read_json(data_tools):
    payload = json.dumps({"key": "value", "num": 42})
    data_tools["write_json"]("test.json", payload)
    result = data_tools["read_json"]("test.json")
    parsed = json.loads(result)
    assert parsed["key"] == "value" and parsed["num"] == 42

def test_read_missing_csv(data_tools):
    result = data_tools["read_csv"]("ghost.csv")
    assert "not found" in result.lower()

def test_write_invalid_json(data_tools):
    result = data_tools["write_json"]("bad.json", "{not valid json}")
    assert "Error" in result


# ── datetime ──────────────────────────────────────────────────────────────────

def test_get_datetime_utc():
    from tools.datetime_tools import register_datetime_tools
    tools = get_tools(register_datetime_tools)
    result = tools["get_datetime"]("utc", "date")
    assert "2026" in result or "2025" in result  # valid year

def test_get_datetime_unknown_tz():
    from tools.datetime_tools import register_datetime_tools
    tools = get_tools(register_datetime_tools)
    result = tools["get_datetime"]("mars")
    assert "Unknown timezone" in result

def test_date_diff():
    from tools.datetime_tools import register_datetime_tools
    tools = get_tools(register_datetime_tools)
    result = tools["date_diff"]("2026-01-01", "2026-06-21")
    assert "Days" in result and "171" in result

def test_add_days():
    from tools.datetime_tools import register_datetime_tools
    tools = get_tools(register_datetime_tools)
    result = tools["add_days"]("2026-01-01", 30)
    assert "2026-01-31" in result

def test_add_days_negative():
    from tools.datetime_tools import register_datetime_tools
    tools = get_tools(register_datetime_tools)
    result = tools["add_days"]("2026-06-21", -7)
    assert "2026-06-14" in result

def test_format_date():
    from tools.datetime_tools import register_datetime_tools
    tools = get_tools(register_datetime_tools)
    result = tools["format_date"]("2026-06-21", "us")
    assert "06/21/2026" in result

def test_timezone_convert():
    from tools.datetime_tools import register_datetime_tools
    tools = get_tools(register_datetime_tools)
    result = tools["timezone_convert"]("09:00", "utc", "singapore")
    assert "17:00" in result   # UTC+8


# ── network ───────────────────────────────────────────────────────────────────

def test_dns_lookup():
    from tools.network import register_network_tools
    tools = get_tools(register_network_tools)
    result = tools["dns_lookup"]("localhost")
    assert "127.0.0.1" in result or "::1" in result

def test_dns_lookup_invalid():
    from tools.network import register_network_tools
    tools = get_tools(register_network_tools)
    # ISPs may hijack NXDOMAIN — just check it returns a non-empty string
    result = tools["dns_lookup"]("this.domain.does.not.exist.xyz")
    assert len(result) > 0

def test_check_port_open():
    from tools.network import register_network_tools
    tools = get_tools(register_network_tools)
    result = tools["check_port"]("localhost", 8080)
    assert "OPEN" in result   # our HTTP server is running

def test_check_port_closed():
    from tools.network import register_network_tools
    tools = get_tools(register_network_tools)
    result = tools["check_port"]("localhost", 19999)
    assert "CLOSED" in result

def test_send_email_no_config():
    from tools.network import register_network_tools
    tools = get_tools(register_network_tools)
    result = tools["send_email"]("test@test.com", "Test", "Body")
    assert "SMTP not configured" in result or "Failed" in result
