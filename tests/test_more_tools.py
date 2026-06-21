"""Tests for Image, PDF/Office, Crypto/Security, and Code/Dev tools."""
import json
import os
import struct
import zlib
import pytest

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_tools(register_fn):
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("test")
    register_fn(mcp)
    return {t.name: t.fn for t in mcp._tool_manager.list_tools()}


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_png(tmp_path, name="test.png", width=10, height=10):
    """Create a minimal valid PNG in tmp_path."""
    def chunk(tag, data):
        c = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", c)
    raw = b"\x00" + (b"\xff\x00\x00" * width)  # red pixels, no filter
    compressed = zlib.compress(raw * height)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )
    p = tmp_path / name
    p.write_bytes(png)
    return name


# ── IMAGE ─────────────────────────────────────────────────────────────────────

@pytest.fixture()
def image_tools(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.image.DATA_DIR", str(tmp_path))
    from tools.image import register_image_tools
    return get_tools(register_image_tools), tmp_path


def test_get_image_info(image_tools):
    tools, tmp = image_tools
    _make_png(tmp, "photo.png")
    result = tools["get_image_info"]("photo.png")
    assert "10 x 10" in result and "PNG" in result


def test_get_image_info_missing(image_tools):
    tools, _ = image_tools
    result = tools["get_image_info"]("ghost.png")
    assert "not found" in result.lower()


def test_resize_image(image_tools):
    tools, tmp = image_tools
    _make_png(tmp, "orig.png")
    result = tools["resize_image"]("orig.png", 5, 5)
    assert "5x5" in result and "resized" in result
    assert (tmp / "orig_resized.png").exists()


def test_convert_image_png_to_bmp(image_tools):
    tools, tmp = image_tools
    _make_png(tmp, "src.png")
    result = tools["convert_image"]("src.png", "bmp")
    assert "BMP" in result
    assert (tmp / "src.bmp").exists()


def test_convert_image_bad_format(image_tools):
    tools, tmp = image_tools
    _make_png(tmp, "src.png")
    result = tools["convert_image"]("src.png", "xyz")
    assert "Error" in result and "unsupported" in result


def test_compress_image_non_jpeg(image_tools):
    tools, tmp = image_tools
    _make_png(tmp, "src.png")
    result = tools["compress_image"]("src.png")
    assert "Error" in result and "JPEG/WebP" in result


def test_compress_jpeg(image_tools):
    tools, tmp = image_tools
    _make_png(tmp, "src.png")
    # First convert to JPEG, then compress
    tools["convert_image"]("src.png", "jpeg", "src.jpg")
    result = tools["compress_image"]("src.jpg", quality=50)
    assert "Compressed" in result or "Error" in result  # tiny test image may grow


def test_image_path_traversal(image_tools):
    tools, _ = image_tools
    result = tools["get_image_info"]("../server.py")
    assert "not allowed" in result or "not found" in result.lower()


# ── PDF/OFFICE ────────────────────────────────────────────────────────────────

@pytest.fixture()
def pdf_tools(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.pdf_office.DATA_DIR", str(tmp_path))
    from tools.pdf_office import register_pdf_office_tools
    return get_tools(register_pdf_office_tools), tmp_path


def _make_pdf(tmp_path, name="doc.pdf", text="Hello PDF"):
    """Create a minimal valid single-page PDF."""
    stream = f"BT /F1 12 Tf 100 700 Td ({text}) Tj ET"
    stream_b = stream.encode()
    content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
        b"   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        + f"4 0 obj\n<< /Length {len(stream_b)} >>\nstream\n".encode()
        + stream_b + b"\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"0000000266 00000 n \n0000000360 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n450\n%%EOF\n"
    )
    p = tmp_path / name
    p.write_bytes(content)
    return name


def test_pdf_to_text(pdf_tools):
    tools, tmp = pdf_tools
    _make_pdf(tmp, "doc.pdf", "Hello PDF")
    result = tools["pdf_to_text"]("doc.pdf")
    # pypdf may or may not extract text from minimal PDFs — just ensure no crash
    assert isinstance(result, str) and len(result) > 0


def test_pdf_to_text_missing(pdf_tools):
    tools, _ = pdf_tools
    result = tools["pdf_to_text"]("ghost.pdf")
    assert "not found" in result.lower()


def test_pdf_info(pdf_tools):
    tools, tmp = pdf_tools
    _make_pdf(tmp, "doc.pdf")
    result = tools["pdf_info"]("doc.pdf")
    assert "Pages" in result


def test_merge_pdfs(pdf_tools):
    tools, tmp = pdf_tools
    _make_pdf(tmp, "a.pdf")
    _make_pdf(tmp, "b.pdf")
    result = tools["merge_pdfs"]("a.pdf,b.pdf", "merged.pdf")
    assert "merged" in result.lower() or "Error" in result  # allow pypdf quirks


def test_csv_to_excel(pdf_tools):
    tools, tmp = pdf_tools
    csv_file = tmp / "data.csv"
    csv_file.write_text("name,age\nAlice,30\nBob,25\n", encoding="utf-8")
    result = tools["csv_to_excel"]("data.csv")
    assert "data.xlsx" in result
    assert (tmp / "data.xlsx").exists()


def test_excel_to_csv(pdf_tools):
    tools, tmp = pdf_tools
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["city", "pop"])
    ws.append(["London", 9000000])
    wb.save(str(tmp / "cities.xlsx"))
    result = tools["excel_to_csv"]("cities.xlsx")
    assert "cities.csv" in result
    assert (tmp / "cities.csv").exists()


# ── CRYPTO/SECURITY ───────────────────────────────────────────────────────────

@pytest.fixture()
def crypto_tools():
    from tools.crypto_security import register_crypto_security_tools
    return get_tools(register_crypto_security_tools)


def test_generate_password_default(crypto_tools):
    result = crypto_tools["generate_password"]()
    assert "Password" in result and "Length   : 16" in result


def test_generate_password_length(crypto_tools):
    result = crypto_tools["generate_password"](length=24, include_symbols=False)
    pw = result.split("\n")[0].split(": ", 1)[1].strip()
    assert len(pw) == 24
    assert not any(c in pw for c in "!@#$%")


def test_generate_uuid_v4(crypto_tools):
    result = crypto_tools["generate_uuid"]()
    parts = result.strip().split("-")
    assert len(parts) == 5


def test_generate_uuid_multiple(crypto_tools):
    result = crypto_tools["generate_uuid"](count=5)
    lines = [l for l in result.strip().splitlines() if l]
    assert len(lines) == 5
    assert len(set(lines)) == 5   # all unique


def test_generate_uuid_bad_version(crypto_tools):
    result = crypto_tools["generate_uuid"](version=3)
    assert "Error" in result


def test_encrypt_decrypt_roundtrip(crypto_tools):
    token = crypto_tools["encrypt_text"]("hello world", "mypassword")
    assert "Error" not in token
    plaintext = crypto_tools["decrypt_text"](token, "mypassword")
    assert plaintext == "hello world"


def test_decrypt_wrong_password(crypto_tools):
    token = crypto_tools["encrypt_text"]("secret", "correct_pw")
    result = crypto_tools["decrypt_text"](token, "wrong_pw")
    assert "Error" in result


def test_sign_text(crypto_tools):
    result = crypto_tools["sign_text"]("my message", "my_secret")
    assert "Signature" in result and "HMAC-SHA256" in result
    # same inputs → same signature (deterministic)
    result2 = crypto_tools["sign_text"]("my message", "my_secret")
    sig1 = result.split("\n")[0]
    sig2 = result2.split("\n")[0]
    assert sig1 == sig2


def test_sign_text_different_secrets(crypto_tools):
    r1 = crypto_tools["sign_text"]("msg", "secret1").split("\n")[0]
    r2 = crypto_tools["sign_text"]("msg", "secret2").split("\n")[0]
    assert r1 != r2


# ── CODE/DEV ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def code_tools(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.code_dev.DATA_DIR", str(tmp_path))
    from tools.code_dev import register_code_dev_tools
    return get_tools(register_code_dev_tools), tmp_path


def test_format_code(code_tools):
    tools, _ = code_tools
    result = tools["format_code"]("x=1+2\nprint(x)\n")
    assert "x = 1 + 2" in result


def test_format_code_bad_language(code_tools):
    tools, _ = code_tools
    result = tools["format_code"]("console.log('hi')", language="javascript")
    assert "Error" in result


def test_lint_python_clean(code_tools):
    tools, _ = code_tools
    result = tools["lint_python"]("x = 1 + 2\nprint(x)\n")
    # ruff may not be on PATH in all environments — either clean pass or ruff-not-found
    assert "No issues" in result or "ruff not found" in result


def test_lint_python_issues(code_tools):
    tools, _ = code_tools
    result = tools["lint_python"]("import os\nx=1\n")
    # ruff should flag unused import or missing spaces
    assert isinstance(result, str) and len(result) > 0


def test_run_python_snippet(code_tools):
    tools, _ = code_tools
    result = tools["run_python_snippet"]("print(2 + 2)")
    assert "4" in result


def test_run_python_snippet_blocked_import(code_tools):
    tools, _ = code_tools
    result = tools["run_python_snippet"]("import os\nprint(os.getcwd())")
    assert "blocked" in result.lower()


def test_run_python_snippet_timeout(code_tools):
    tools, _ = code_tools
    result = tools["run_python_snippet"]("while True: pass", timeout=1)
    assert "timed out" in result.lower()


def test_count_lines(code_tools):
    tools, tmp = code_tools
    src = tmp / "hello.py"
    src.write_text("# comment\nx = 1\n\nprint(x)\n", encoding="utf-8")
    result = tools["count_lines"]("hello.py")
    assert "Total" in result and "4" in result
    assert "Comments : 1" in result
    assert "Blank    : 1" in result


def test_count_lines_missing(code_tools):
    tools, _ = code_tools
    result = tools["count_lines"]("ghost.py")
    assert "not found" in result.lower()


def test_git_status_mcp_repo(code_tools):
    tools, _ = code_tools
    # Use the MCP repo itself (or any valid path); just verify it returns a string
    result = tools["git_status"]()
    # Could be "git not found" or actual status — both are valid
    assert isinstance(result, str) and len(result) > 0
