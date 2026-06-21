"""Archive/Compress tools — zipfile, tarfile, gzip (all stdlib, no extra deps).
   All operations are sandboxed to the data/ directory.
"""
import gzip
import os
import shutil
import tarfile
import zipfile
from mcp.server.fastmcp import FastMCP

_BASE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE, "data")


def _safe(filename: str) -> str | None:
    target = os.path.normpath(os.path.join(DATA_DIR, filename))
    return target if target.startswith(DATA_DIR) else None


def _safe_member(member_path: str, dest_dir: str) -> bool:
    """Zip-slip guard — ensure extracted path stays inside dest_dir."""
    full = os.path.normpath(os.path.join(dest_dir, member_path))
    return full.startswith(os.path.normpath(dest_dir))


def register_archive_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def zip_files(filenames: str, output: str) -> str:
        """
        Create a ZIP archive from one or more files in the data/ directory.
        filenames: comma-separated list of filenames in data/, e.g. 'a.txt,b.csv,report.pdf'.
        output: output ZIP filename in data/, e.g. 'bundle.zip'.
        Returns confirmation with total compressed size and compression ratio.
        """
        out_path = _safe(output)
        if not out_path: return "Error: invalid output path."
        if not output.lower().endswith(".zip"):
            return "Error: output filename must end with .zip"
        file_list = [f.strip() for f in filenames.split(",") if f.strip()]
        if not file_list:
            return "Error: no filenames provided."
        total_original = 0
        added = []
        try:
            with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for fname in file_list:
                    path = _safe(fname)
                    if not path: return f"Error: invalid path '{fname}'"
                    if not os.path.exists(path): return f"File not found: {fname}"
                    total_original += os.path.getsize(path)
                    zf.write(path, arcname=fname)
                    added.append(fname)
            compressed = os.path.getsize(out_path)
            ratio = (1 - compressed / max(total_original, 1)) * 100
            return (
                f"Created     : {output}\n"
                f"Files       : {len(added)} → {added}\n"
                f"Original    : {total_original/1024:.1f} KB\n"
                f"Compressed  : {compressed/1024:.1f} KB\n"
                f"Ratio       : {ratio:.1f}% saved"
            )
        except Exception as e:
            return f"Error creating ZIP: {e}"

    @mcp.tool()
    def unzip_files(filename: str, dest_dir: str = "") -> str:
        """
        Extract a ZIP archive into a subdirectory of data/.
        filename: ZIP file in data/, e.g. 'bundle.zip'.
        dest_dir: extraction target subdirectory name in data/ (default: zip name without extension).
        Returns list of extracted files and total size.
        """
        path = _safe(filename)
        if not path: return "Error: path traversal not allowed."
        if not os.path.exists(path): return f"File not found: {filename}"
        if not dest_dir:
            dest_dir = os.path.splitext(filename)[0]
        dest_path = _safe(dest_dir)
        if not dest_path: return "Error: invalid destination directory."
        try:
            with zipfile.ZipFile(path, "r") as zf:
                members = zf.namelist()
                # zip-slip guard
                for m in members:
                    if not _safe_member(m, dest_path):
                        return f"Error: dangerous path in archive: '{m}'"
                os.makedirs(dest_path, exist_ok=True)
                zf.extractall(dest_path)
                total_size = sum(
                    os.path.getsize(os.path.join(dest_path, m))
                    for m in members
                    if os.path.isfile(os.path.join(dest_path, m))
                )
            return (
                f"Extracted   : {filename} → {dest_dir}/\n"
                f"Files       : {len(members)}\n"
                f"Total size  : {total_size/1024:.1f} KB\n"
                f"Contents    : {members[:20]}{'...' if len(members)>20 else ''}"
            )
        except zipfile.BadZipFile:
            return "Error: not a valid ZIP file."
        except Exception as e:
            return f"Error extracting ZIP: {e}"

    @mcp.tool()
    def list_archive(filename: str) -> str:
        """
        List the contents of a ZIP or TAR archive without extracting it.
        filename: archive file in data/, e.g. 'bundle.zip' or 'backup.tar.gz'.
        Returns file names, sizes, and compression info for each member.
        """
        path = _safe(filename)
        if not path: return "Error: path traversal not allowed."
        if not os.path.exists(path): return f"File not found: {filename}"
        name_lower = filename.lower()
        try:
            if name_lower.endswith(".zip"):
                with zipfile.ZipFile(path, "r") as zf:
                    lines = [f"ZIP archive: {filename} ({len(zf.namelist())} files)\n"]
                    total_orig = total_comp = 0
                    for info in zf.infolist():
                        orig = info.file_size
                        comp = info.compress_size
                        ratio = (1 - comp/max(orig,1))*100 if orig else 0
                        total_orig += orig
                        total_comp += comp
                        lines.append(
                            f"  {info.filename:<40} {orig/1024:7.1f} KB → {comp/1024:7.1f} KB ({ratio:.0f}% saved)"
                        )
                    ratio_total = (1 - total_comp/max(total_orig,1))*100
                    lines.append(f"\nTotal: {total_orig/1024:.1f} KB → {total_comp/1024:.1f} KB ({ratio_total:.0f}% saved)")
                    return "\n".join(lines)
            elif any(name_lower.endswith(e) for e in (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
                with tarfile.open(path, "r:*") as tf:
                    members = tf.getmembers()
                    lines = [f"TAR archive: {filename} ({len(members)} files)\n"]
                    total = 0
                    for m in members:
                        total += m.size
                        lines.append(f"  {m.name:<50} {m.size/1024:7.1f} KB")
                    lines.append(f"\nTotal uncompressed: {total/1024:.1f} KB")
                    return "\n".join(lines)
            else:
                return "Error: unsupported archive type. Use .zip, .tar, .tar.gz, .tgz, .tar.bz2, or .tar.xz"
        except Exception as e:
            return f"Error reading archive: {e}"

    @mcp.tool()
    def tar_files(filenames: str, output: str, compress: str = "gz") -> str:
        """
        Create a TAR archive from files in data/.
        filenames: comma-separated filenames in data/, e.g. 'a.txt,b.csv'.
        output: output TAR filename in data/, e.g. 'backup.tar.gz'.
        compress: compression — 'gz' (gzip, default), 'bz2' (bzip2), 'xz', or '' (none).
        Returns confirmation with file count and size.
        """
        compress = compress.strip().lower()
        mode_map = {"gz": "w:gz", "bz2": "w:bz2", "xz": "w:xz", "": "w"}
        if compress not in mode_map:
            return f"Error: compress must be 'gz', 'bz2', 'xz', or '' (none)."
        out_path = _safe(output)
        if not out_path: return "Error: invalid output path."
        file_list = [f.strip() for f in filenames.split(",") if f.strip()]
        if not file_list: return "Error: no filenames provided."
        try:
            total_orig = 0
            with tarfile.open(out_path, mode_map[compress]) as tf:
                for fname in file_list:
                    path = _safe(fname)
                    if not path: return f"Error: invalid path '{fname}'"
                    if not os.path.exists(path): return f"File not found: {fname}"
                    total_orig += os.path.getsize(path)
                    tf.add(path, arcname=fname)
            compressed = os.path.getsize(out_path)
            ratio = (1 - compressed / max(total_orig, 1)) * 100
            return (
                f"Created     : {output}\n"
                f"Files       : {len(file_list)}\n"
                f"Compression : {compress.upper() or 'none'}\n"
                f"Original    : {total_orig/1024:.1f} KB\n"
                f"Archive     : {compressed/1024:.1f} KB\n"
                f"Ratio       : {ratio:.1f}% saved"
            )
        except Exception as e:
            return f"Error creating TAR: {e}"

    @mcp.tool()
    def compress_file(filename: str, output: str = "") -> str:
        """
        Compress a single file with gzip (.gz).
        filename: source file in data/, e.g. 'log.txt'.
        output: output .gz filename in data/ (default: adds '.gz' extension).
        Returns before/after size comparison.
        Use zip_files or tar_files to bundle multiple files.
        """
        path = _safe(filename)
        if not path: return "Error: path traversal not allowed."
        if not os.path.exists(path): return f"File not found: {filename}"
        if not output:
            output = filename + ".gz"
        out_path = _safe(output)
        if not out_path: return "Error: invalid output path."
        try:
            with open(path, "rb") as f_in, gzip.open(out_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            before = os.path.getsize(path)
            after  = os.path.getsize(out_path)
            ratio  = (1 - after / max(before, 1)) * 100
            return (
                f"Compressed  : {filename} → {output}\n"
                f"Before      : {before/1024:.1f} KB\n"
                f"After       : {after/1024:.1f} KB\n"
                f"Saved       : {ratio:.1f}%"
            )
        except Exception as e:
            return f"Error: {e}"
