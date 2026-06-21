"""Audio/Video tools — wraps pydub (audio) and ffprobe/ffmpeg (video via subprocess).
   ffmpeg is optional: audio info/conversion/trim work via pydub;
   video tools degrade gracefully when ffmpeg is not installed.
"""
import json
import os
import subprocess
import sys
from mcp.server.fastmcp import FastMCP

_BASE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE, "data")

AUDIO_FORMATS = {"mp3", "wav", "ogg", "flac", "aac", "m4a", "wma", "opus"}
VIDEO_FORMATS = {"mp4", "mkv", "avi", "mov", "webm", "flv", "wmv"}


def _safe(filename: str) -> str | None:
    target = os.path.normpath(os.path.join(DATA_DIR, filename))
    return target if target.startswith(DATA_DIR) else None


def _ffprobe(path: str) -> dict | None:
    """Run ffprobe and return parsed JSON, or None if unavailable."""
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", path,
            ],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
        )
        return json.loads(r.stdout) if r.returncode == 0 else None
    except (FileNotFoundError, Exception):
        return None


def register_audio_video_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def get_audio_info(filename: str) -> str:
        """
        Get metadata about an audio file in the data/ directory.
        filename: relative path, e.g. 'song.mp3'.
        Returns: format, duration, channels, sample rate, bitrate, file size.
        Supports: mp3, wav, ogg, flac, aac, m4a, wma, opus.
        """
        path = _safe(filename)
        if not path: return "Error: path traversal not allowed."
        if not os.path.exists(path): return f"File not found: {filename}"
        try:
            from pydub import AudioSegment
            ext = os.path.splitext(filename)[1].lstrip(".").lower()
            audio = AudioSegment.from_file(path, format=ext)
            dur_s = len(audio) / 1000
            file_kb = os.path.getsize(path) / 1024
            return (
                f"File       : {filename}\n"
                f"Duration   : {dur_s:.2f} s ({int(dur_s//60)}m {int(dur_s%60)}s)\n"
                f"Channels   : {audio.channels} ({'stereo' if audio.channels==2 else 'mono'})\n"
                f"Sample rate: {audio.frame_rate} Hz\n"
                f"Bit depth  : {audio.sample_width * 8} bit\n"
                f"File size  : {file_kb:.1f} KB"
            )
        except Exception as e:
            return f"Error reading audio: {e}"

    @mcp.tool()
    def convert_audio(filename: str, output_format: str, output: str = "") -> str:
        """
        Convert an audio file to a different format.
        filename: source audio in data/, e.g. 'song.wav'.
        output_format: target format — mp3, wav, ogg, flac, aac, opus.
        output: output filename in data/ (default: same name, new extension).
        Returns confirmation with output path.
        """
        fmt = output_format.lower().strip().lstrip(".")
        if fmt not in AUDIO_FORMATS:
            return f"Error: unsupported format '{fmt}'. Choose: {', '.join(AUDIO_FORMATS)}"
        path = _safe(filename)
        if not path: return "Error: path traversal not allowed."
        if not os.path.exists(path): return f"File not found: {filename}"
        if not output:
            output = os.path.splitext(filename)[0] + f".{fmt}"
        out_path = _safe(output)
        if not out_path: return "Error: invalid output path."
        try:
            from pydub import AudioSegment
            ext = os.path.splitext(filename)[1].lstrip(".").lower()
            audio = AudioSegment.from_file(path, format=ext)
            audio.export(out_path, format=fmt)
            before_kb = os.path.getsize(path) / 1024
            after_kb  = os.path.getsize(out_path) / 1024
            return (
                f"Converted  : {filename} → {output}\n"
                f"Format     : {fmt.upper()}\n"
                f"Before     : {before_kb:.1f} KB\n"
                f"After      : {after_kb:.1f} KB"
            )
        except Exception as e:
            return f"Error converting audio: {e}"

    @mcp.tool()
    def trim_audio(filename: str, start_ms: int, end_ms: int, output: str = "") -> str:
        """
        Trim an audio file to a specific time range.
        filename: source audio in data/, e.g. 'podcast.mp3'.
        start_ms: start position in milliseconds (e.g. 5000 = 5 seconds in).
        end_ms: end position in milliseconds (0 = until end of file).
        output: output filename in data/ (default: adds '_trimmed' suffix).
        Returns confirmation with new duration.
        """
        path = _safe(filename)
        if not path: return "Error: path traversal not allowed."
        if not os.path.exists(path): return f"File not found: {filename}"
        if not output:
            name, ext = os.path.splitext(filename)
            output = f"{name}_trimmed{ext}"
        out_path = _safe(output)
        if not out_path: return "Error: invalid output path."
        try:
            from pydub import AudioSegment
            ext = os.path.splitext(filename)[1].lstrip(".").lower()
            audio = AudioSegment.from_file(path, format=ext)
            total_ms = len(audio)
            end = end_ms if end_ms > 0 else total_ms
            end = min(end, total_ms)
            start = max(0, start_ms)
            if start >= end:
                return f"Error: start ({start}ms) must be less than end ({end}ms)."
            trimmed = audio[start:end]
            trimmed.export(out_path, format=ext)
            dur = (end - start) / 1000
            return (
                f"Trimmed    : {filename}\n"
                f"Range      : {start}ms → {end}ms\n"
                f"Duration   : {dur:.2f}s\n"
                f"Output     : {output}"
            )
        except Exception as e:
            return f"Error trimming audio: {e}"

    @mcp.tool()
    def get_video_info(filename: str) -> str:
        """
        Get metadata about a video file using ffprobe.
        filename: relative path in data/, e.g. 'clip.mp4'.
        Returns: duration, resolution, codec, framerate, audio info, file size.
        Requires ffmpeg/ffprobe to be installed and on PATH.
        """
        path = _safe(filename)
        if not path: return "Error: path traversal not allowed."
        if not os.path.exists(path): return f"File not found: {filename}"
        info = _ffprobe(path)
        if info is None:
            return (
                "Error: ffprobe not found or failed. "
                "Install ffmpeg from https://ffmpeg.org/download.html and add to PATH."
            )
        fmt    = info.get("format", {})
        dur    = float(fmt.get("duration", 0))
        size   = int(fmt.get("size", 0)) / 1024
        fmtname = fmt.get("format_long_name", "unknown")
        streams = info.get("streams", [])
        video_lines, audio_lines = [], []
        for s in streams:
            if s.get("codec_type") == "video":
                fps_raw = s.get("r_frame_rate", "0/1").split("/")
                fps = round(int(fps_raw[0]) / int(fps_raw[1]), 2) if len(fps_raw) == 2 and int(fps_raw[1]) else 0
                video_lines.append(
                    f"  Codec: {s.get('codec_name','?')} | "
                    f"{s.get('width','?')}x{s.get('height','?')} | {fps} fps"
                )
            elif s.get("codec_type") == "audio":
                audio_lines.append(
                    f"  Codec: {s.get('codec_name','?')} | "
                    f"{s.get('sample_rate','?')} Hz | ch: {s.get('channels','?')}"
                )
        lines = [
            f"File    : {filename}",
            f"Format  : {fmtname}",
            f"Duration: {dur:.2f}s ({int(dur//60)}m {int(dur%60)}s)",
            f"Size    : {size:.1f} KB",
            "Video streams:",
        ] + (video_lines or ["  (none)"]) + ["Audio streams:"] + (audio_lines or ["  (none)"])
        return "\n".join(lines)

    @mcp.tool()
    def extract_audio(filename: str, output: str = "") -> str:
        """
        Extract the audio track from a video file as mp3.
        filename: source video in data/, e.g. 'lecture.mp4'.
        output: output audio filename in data/ (default: same name with .mp3 extension).
        Requires ffmpeg to be installed and on PATH.
        Returns confirmation with output path and duration.
        """
        path = _safe(filename)
        if not path: return "Error: path traversal not allowed."
        if not os.path.exists(path): return f"File not found: {filename}"
        if not output:
            output = os.path.splitext(filename)[0] + ".mp3"
        out_path = _safe(output)
        if not out_path: return "Error: invalid output path."
        try:
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", path, "-vn", "-acodec", "libmp3lame", "-q:a", "2", out_path],
                capture_output=True, text=True, timeout=120,
                encoding="utf-8", errors="replace",
            )
            if result.returncode != 0:
                return f"ffmpeg error:\n{result.stderr[-800:]}"
            size_kb = os.path.getsize(out_path) / 1024
            return f"Extracted audio → {output} ({size_kb:.1f} KB)"
        except FileNotFoundError:
            return (
                "Error: ffmpeg not found. "
                "Install from https://ffmpeg.org/download.html and add to PATH."
            )
        except Exception as e:
            return f"Error: {e}"
