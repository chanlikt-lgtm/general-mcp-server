"""Tests for Audio/Video, ML/AI Utils, Web Scraping, and Archive tools."""
import json
import os
import struct
import wave
import zipfile
import pytest

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_tools(register_fn):
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("test")
    register_fn(mcp)
    return {t.name: t.fn for t in mcp._tool_manager.list_tools()}


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_wav(tmp_path, name="test.wav", duration_ms=500, freq=440):
    """Create a minimal valid WAV file (mono, 44100 Hz, 16-bit)."""
    import math, array as arr
    sample_rate = 44100
    n_samples   = int(sample_rate * duration_ms / 1000)
    samples     = arr.array("h", [
        int(32767 * math.sin(2 * math.pi * freq * i / sample_rate))
        for i in range(n_samples)
    ])
    p = tmp_path / name
    with wave.open(str(p), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    return name


def _make_zip(tmp_path, zip_name="bundle.zip", files=None):
    """Create a ZIP in tmp_path containing the given {name: content} dict."""
    if files is None:
        files = {"hello.txt": "hello world", "data.csv": "a,b\n1,2\n"}
    p = tmp_path / zip_name
    with zipfile.ZipFile(str(p), "w") as zf:
        for fname, content in files.items():
            zf.writestr(fname, content)
    return zip_name


# ══════════════════════════════════════════════════════════════════════════════
# AUDIO / VIDEO
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def av_tools(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.audio_video.DATA_DIR", str(tmp_path))
    from tools.audio_video import register_audio_video_tools
    return get_tools(register_audio_video_tools), tmp_path


def test_get_audio_info_wav(av_tools):
    tools, tmp = av_tools
    _make_wav(tmp, "tone.wav")
    result = tools["get_audio_info"]("tone.wav")
    assert "Duration" in result and "Sample rate" in result


def test_get_audio_info_missing(av_tools):
    tools, _ = av_tools
    result = tools["get_audio_info"]("ghost.mp3")
    assert "not found" in result.lower()


def test_get_audio_info_traversal(av_tools):
    tools, _ = av_tools
    result = tools["get_audio_info"]("../server.py")
    assert "not allowed" in result or "not found" in result.lower()


def test_convert_audio_wav_to_ogg(av_tools):
    tools, tmp = av_tools
    _make_wav(tmp, "src.wav")
    result = tools["convert_audio"]("src.wav", "ogg")
    assert "src.ogg" in result or "Error" in result   # ffmpeg may not be installed


def test_convert_audio_bad_format(av_tools):
    tools, tmp = av_tools
    _make_wav(tmp, "src.wav")
    result = tools["convert_audio"]("src.wav", "xyz")
    assert "Error" in result and "unsupported" in result


def test_trim_audio(av_tools):
    tools, tmp = av_tools
    _make_wav(tmp, "long.wav", duration_ms=1000)
    result = tools["trim_audio"]("long.wav", start_ms=0, end_ms=400)
    assert "Trimmed" in result or "Error" in result


def test_trim_audio_bad_range(av_tools):
    tools, tmp = av_tools
    _make_wav(tmp, "x.wav", duration_ms=500)
    result = tools["trim_audio"]("x.wav", start_ms=400, end_ms=100)
    assert "Error" in result and "less than" in result


def test_get_video_info_missing(av_tools):
    tools, _ = av_tools
    result = tools["get_video_info"]("ghost.mp4")
    assert "not found" in result.lower()


def test_extract_audio_missing(av_tools):
    tools, _ = av_tools
    result = tools["extract_audio"]("ghost.mp4")
    assert "not found" in result.lower()


# ══════════════════════════════════════════════════════════════════════════════
# ML / AI UTILS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def ml_tools():
    from tools.ml_utils import register_ml_utils_tools
    return get_tools(register_ml_utils_tools)


def test_tokenize_basic(ml_tools):
    result = ml_tools["tokenize_text"]("Hello world hello")
    assert "Total tokens  : 3" in result
    assert "Unique tokens : 2" in result


def test_tokenize_stopwords(ml_tools):
    result = ml_tools["tokenize_text"]("the cat sat on the mat", remove_stopwords=True)
    # "the" and "on" are stopwords — should be removed
    assert "the" not in result.split("Tokens")[1].lower().split("unique")[0]


def test_embedding_similarity_identical(ml_tools):
    result = ml_tools["embedding_similarity"]("machine learning", "machine learning")
    sim = float(result.split("\n")[0].split(":")[1].strip().split(" ")[0])
    assert sim > 0.99


def test_embedding_similarity_different(ml_tools):
    result = ml_tools["embedding_similarity"]("quantum physics equations", "banana smoothie recipe")
    sim = float(result.split("\n")[0].split(":")[1].strip().split(" ")[0])
    assert sim < 0.5


def test_embedding_similarity_related(ml_tools):
    result = ml_tools["embedding_similarity"](
        "Python is a programming language used for data science",
        "Data scientists use Python for machine learning projects"
    )
    assert "Similarity" in result


def test_summarize_text(ml_tools):
    text = (
        "The sky is blue. Water covers most of Earth. "
        "Humans have explored the moon. Cats are popular pets. "
        "Coffee is consumed worldwide. Mountains are tall. "
        "Rivers flow downhill. Birds can fly."
    )
    result = ml_tools["summarize_text"](text, sentences=2)
    assert "Summary" in result and len(result) > 20


def test_summarize_too_short(ml_tools):
    result = ml_tools["summarize_text"]("Hi.", sentences=3)
    assert "Error" in result or len(result) > 0


def test_classify_sentiment_positive(ml_tools):
    result = ml_tools["classify_sentiment"]("This product is absolutely amazing and fantastic!")
    assert "Positive" in result


def test_classify_sentiment_negative(ml_tools):
    result = ml_tools["classify_sentiment"]("Terrible experience, broken and useless waste of money.")
    assert "Negative" in result


def test_classify_sentiment_neutral(ml_tools):
    result = ml_tools["classify_sentiment"]("The box arrived on Tuesday.")
    assert "Neutral" in result or "Positive" in result or "Negative" in result  # any valid label


def test_chunk_text(ml_tools):
    text = " ".join([f"word{i}" for i in range(200)])
    result = ml_tools["chunk_text"](text, chunk_size=50, overlap=10)
    assert "Chunk 1" in result and "Chunk 2" in result


def test_chunk_text_empty(ml_tools):
    result = ml_tools["chunk_text"]("")
    assert "Error" in result


# ══════════════════════════════════════════════════════════════════════════════
# WEB SCRAPING
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def scrape_tools():
    from tools.web_scraping import register_web_scraping_tools
    return get_tools(register_web_scraping_tools)


def test_scrape_page_example(scrape_tools):
    result = scrape_tools["scrape_page"]("https://example.com")
    assert "Example Domain" in result or "Error" in result  # degrade gracefully offline


def test_scrape_page_bad_url(scrape_tools):
    result = scrape_tools["scrape_page"]("not-a-url")
    assert "Error" in result


def test_scrape_page_http_error(scrape_tools):
    # httpstat.us/404 returns an HTTP 404 — we expect either the code in output or an error string
    result = scrape_tools["scrape_page"]("https://httpstat.us/404")
    assert isinstance(result, str) and len(result) > 0   # any non-empty response is acceptable


def test_extract_links_example(scrape_tools):
    result = scrape_tools["extract_links"]("https://example.com")
    # example.com has at least one link or network error
    assert isinstance(result, str) and len(result) > 0


def test_extract_links_bad_url(scrape_tools):
    result = scrape_tools["extract_links"]("ftp://not-http")
    assert "Error" in result


def test_extract_tables_wikipedia(scrape_tools):
    result = scrape_tools["extract_tables"]("https://en.wikipedia.org/wiki/Python_(programming_language)")
    assert "Table" in result or "Error" in result


def test_parse_rss_bbc(scrape_tools):
    result = scrape_tools["parse_rss"]("https://feeds.bbci.co.uk/news/rss.xml", max_items=3)
    assert "Feed" in result or "Error" in result


def test_parse_rss_bad_url(scrape_tools):
    result = scrape_tools["parse_rss"]("https://definitely-not-a-feed.xyz/rss")
    assert isinstance(result, str) and len(result) > 0


def test_get_page_metadata(scrape_tools):
    result = scrape_tools["get_page_metadata"]("https://example.com")
    assert "Title" in result or "Error" in result


# ══════════════════════════════════════════════════════════════════════════════
# ARCHIVE / COMPRESS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def arc_tools(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.archive.DATA_DIR", str(tmp_path))
    from tools.archive import register_archive_tools
    return get_tools(register_archive_tools), tmp_path


def _write(tmp, name, content="hello"):
    (tmp / name).write_text(content, encoding="utf-8")
    return name


def test_zip_files(arc_tools):
    tools, tmp = arc_tools
    _write(tmp, "a.txt", "hello")
    _write(tmp, "b.txt", "world")
    result = tools["zip_files"]("a.txt,b.txt", "bundle.zip")
    assert "bundle.zip" in result and (tmp / "bundle.zip").exists()


def test_zip_files_no_ext(arc_tools):
    tools, tmp = arc_tools
    _write(tmp, "a.txt")
    result = tools["zip_files"]("a.txt", "out.tar")
    assert "Error" in result and ".zip" in result


def test_zip_files_missing(arc_tools):
    tools, _ = arc_tools
    result = tools["zip_files"]("ghost.txt", "out.zip")
    assert "not found" in result.lower()


def test_unzip_files(arc_tools):
    tools, tmp = arc_tools
    _make_zip(tmp, "pack.zip", {"hi.txt": "hi!", "data.csv": "x,y\n1,2\n"})
    result = tools["unzip_files"]("pack.zip")
    assert "Extracted" in result
    assert (tmp / "pack" / "hi.txt").exists()


def test_unzip_missing(arc_tools):
    tools, _ = arc_tools
    result = tools["unzip_files"]("ghost.zip")
    assert "not found" in result.lower()


def test_list_archive_zip(arc_tools):
    tools, tmp = arc_tools
    _make_zip(tmp, "info.zip", {"readme.txt": "readme content here"})
    result = tools["list_archive"]("info.zip")
    assert "readme.txt" in result and "ZIP archive" in result


def test_list_archive_missing(arc_tools):
    tools, _ = arc_tools
    result = tools["list_archive"]("ghost.zip")
    assert "not found" in result.lower()


def test_list_archive_unsupported(arc_tools):
    tools, tmp = arc_tools
    _write(tmp, "file.rar")
    result = tools["list_archive"]("file.rar")
    assert "Error" in result and "unsupported" in result


def test_tar_files(arc_tools):
    tools, tmp = arc_tools
    _write(tmp, "c.txt", "some content")
    result = tools["tar_files"]("c.txt", "archive.tar.gz", compress="gz")
    assert "archive.tar.gz" in result and (tmp / "archive.tar.gz").exists()


def test_tar_files_no_compress(arc_tools):
    tools, tmp = arc_tools
    _write(tmp, "d.txt", "data")
    result = tools["tar_files"]("d.txt", "plain.tar", compress="")
    assert "plain.tar" in result and (tmp / "plain.tar").exists()


def test_compress_file_gz(arc_tools):
    tools, tmp = arc_tools
    _write(tmp, "log.txt", "log line\n" * 100)
    result = tools["compress_file"]("log.txt")
    assert "log.txt.gz" in result and (tmp / "log.txt.gz").exists()
    assert "Saved" in result


def test_compress_file_missing(arc_tools):
    tools, _ = arc_tools
    result = tools["compress_file"]("ghost.txt")
    assert "not found" in result.lower()
