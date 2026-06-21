import os
from mcp.server.fastmcp import FastMCP

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE, "data")

ALLOWED_FORMATS = {"jpeg", "jpg", "png", "gif", "bmp", "webp", "tiff", "ico"}


def _safe(filename: str) -> str | None:
    target = os.path.normpath(os.path.join(DATA_DIR, filename))
    return target if target.startswith(DATA_DIR) else None


def register_image_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def get_image_info(filename: str) -> str:
        """
        Get metadata about an image file in the data/ directory.
        filename: relative path, e.g. 'photo.jpg'.
        Returns: format, size (WxH), mode (RGB/RGBA), file size in KB.
        """
        from PIL import Image
        path = _safe(filename)
        if not path: return "Error: path traversal not allowed."
        if not os.path.exists(path): return f"File not found: {filename}"
        try:
            with Image.open(path) as img:
                file_kb = os.path.getsize(path) / 1024
                return (
                    f"File    : {filename}\n"
                    f"Format  : {img.format}\n"
                    f"Size    : {img.width} x {img.height} px\n"
                    f"Mode    : {img.mode}\n"
                    f"File KB : {file_kb:.1f} KB"
                )
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def resize_image(filename: str, width: int, height: int, output: str = "") -> str:
        """
        Resize an image to the given dimensions.
        filename: source image in data/, e.g. 'photo.jpg'.
        width, height: target dimensions in pixels.
        output: output filename in data/ (default: adds '_resized' suffix).
        Preserves aspect ratio is NOT forced — exact dimensions are used.
        Returns confirmation with new file path.
        """
        from PIL import Image
        path = _safe(filename)
        if not path: return "Error: path traversal not allowed."
        if not os.path.exists(path): return f"File not found: {filename}"
        try:
            with Image.open(path) as img:
                resized = img.resize((int(width), int(height)), Image.LANCZOS)
                if not output:
                    name, ext = os.path.splitext(filename)
                    output = f"{name}_resized{ext}"
                out_path = _safe(output)
                if not out_path: return "Error: invalid output path."
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                resized.save(out_path)
                return f"Resized to {width}x{height} → saved as {output}"
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def convert_image(filename: str, output_format: str, output: str = "") -> str:
        """
        Convert an image to a different format.
        filename: source image in data/, e.g. 'photo.png'.
        output_format: target format — jpeg, png, webp, bmp, gif, tiff, ico.
        output: output filename (default: same name with new extension).
        Returns confirmation with output path.
        """
        from PIL import Image
        fmt = output_format.lower().strip().lstrip(".")
        if fmt not in ALLOWED_FORMATS:
            return f"Error: unsupported format '{fmt}'. Choose: {', '.join(ALLOWED_FORMATS)}"
        path = _safe(filename)
        if not path: return "Error: path traversal not allowed."
        if not os.path.exists(path): return f"File not found: {filename}"
        try:
            with Image.open(path) as img:
                save_fmt = "JPEG" if fmt == "jpg" else fmt.upper()
                if not output:
                    output = os.path.splitext(filename)[0] + f".{fmt}"
                out_path = _safe(output)
                if not out_path: return "Error: invalid output path."
                # Convert RGBA → RGB for JPEG
                save_img = img
                if save_fmt == "JPEG" and img.mode in ("RGBA", "P"):
                    save_img = img.convert("RGB")
                save_img.save(out_path, format=save_fmt)
                return f"Converted {filename} → {output} ({save_fmt})"
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def compress_image(filename: str, quality: int = 75, output: str = "") -> str:
        """
        Compress a JPEG or WebP image by reducing quality.
        filename: source image in data/ (must be JPEG or WebP).
        quality: compression quality 1-95 (default 75; lower = smaller file).
        output: output filename (default: adds '_compressed' suffix).
        Returns before/after file size comparison.
        """
        from PIL import Image
        path = _safe(filename)
        if not path: return "Error: path traversal not allowed."
        if not os.path.exists(path): return f"File not found: {filename}"
        quality = max(1, min(95, int(quality)))
        try:
            with Image.open(path) as img:
                fmt = img.format or "JPEG"
                if fmt not in ("JPEG", "WEBP"):
                    return f"Error: compress_image only supports JPEG/WebP (got {fmt}). Use convert_image first."
                if not output:
                    name, ext = os.path.splitext(filename)
                    output = f"{name}_compressed{ext}"
                out_path = _safe(output)
                if not out_path: return "Error: invalid output path."
                save_img = img if img.mode != "RGBA" else img.convert("RGB")
                save_img.save(out_path, format=fmt, quality=quality, optimize=True)
            before_kb = os.path.getsize(path) / 1024
            after_kb  = os.path.getsize(out_path) / 1024
            saved_pct = (1 - after_kb / before_kb) * 100
            return (
                f"Compressed {filename} (quality={quality})\n"
                f"Before : {before_kb:.1f} KB\n"
                f"After  : {after_kb:.1f} KB\n"
                f"Saved  : {saved_pct:.1f}%\n"
                f"Output : {output}"
            )
        except Exception as e:
            return f"Error: {e}"
