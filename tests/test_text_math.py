"""Unit tests for text/math tools."""
import pytest
from mcp.server.fastmcp import FastMCP
from tools.text_math import register_text_math_tools


@pytest.fixture()
def tools():
    mcp = FastMCP("test")
    register_text_math_tools(mcp)
    return {t.name: t.fn for t in mcp._tool_manager.list_tools()}


# ── calculate ─────────────────────────────────────────────────────────────────

def test_calc_basic(tools):
    assert tools["calculate"]("2 + 2") == "4"

def test_calc_power(tools):
    assert tools["calculate"]("2 ** 10") == "1024"

def test_calc_sqrt(tools):
    assert tools["calculate"]("sqrt(144)") == "12"

def test_calc_pi(tools):
    result = tools["calculate"]("round(pi, 4)")
    assert result == "3.1416"

def test_calc_chained(tools):
    assert tools["calculate"]("(3 + 4) * 2") == "14"

def test_calc_blocks_code(tools):
    result = tools["calculate"]("__import__('os').system('dir')")
    assert "Error" in result

def test_calc_division(tools):
    assert tools["calculate"]("10 / 4") == "2.5"

def test_calc_floor_div(tools):
    assert tools["calculate"]("10 // 3") == "3"


# ── regex_search ──────────────────────────────────────────────────────────────

def test_regex_finds_numbers(tools):
    result = tools["regex_search"](r"\d+", "abc 123 def 456")
    assert "123" in result
    assert "456" in result

def test_regex_no_match(tools):
    result = tools["regex_search"](r"\d+", "no numbers here")
    assert "No matches" in result

def test_regex_ignorecase(tools):
    result = tools["regex_search"]("hello", "Hello World", "ignorecase")
    assert "Hello" in result

def test_regex_invalid_pattern(tools):
    result = tools["regex_search"]("[invalid", "text")
    assert "Invalid regex" in result


# ── word_count ────────────────────────────────────────────────────────────────

def test_word_count_basic(tools):
    result = tools["word_count"]("hello world\nfoo bar")
    assert "Words      : 4" in result
    assert "Lines      : 2" in result
    assert "Characters : 19" in result

def test_word_count_unique(tools):
    result = tools["word_count"]("the cat sat on the mat")
    assert "Unique words: 5" in result  # the, cat, sat, on, mat


# ── hash_text ─────────────────────────────────────────────────────────────────

def test_hash_sha256(tools):
    result = tools["hash_text"]("hello", "sha256")
    assert result == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

def test_hash_md5(tools):
    result = tools["hash_text"]("hello", "md5")
    assert result == "5d41402abc4b2a76b9719d911017c592"

def test_hash_invalid_algo(tools):
    result = tools["hash_text"]("hello", "rot13")
    assert "Error" in result


# ── encode/decode base64 ──────────────────────────────────────────────────────

def test_encode_base64(tools):
    result = tools["encode_base64"]("hello world")
    assert result == "aGVsbG8gd29ybGQ="

def test_decode_base64(tools):
    result = tools["decode_base64"]("aGVsbG8gd29ybGQ=")
    assert result == "hello world"

def test_roundtrip_base64(tools):
    original = "MCP is working! 🎉"
    encoded = tools["encode_base64"](original)
    decoded = tools["decode_base64"](encoded)
    assert decoded == original

def test_decode_invalid_base64(tools):
    result = tools["decode_base64"]("!!!not_valid!!!")
    assert "Error" in result
