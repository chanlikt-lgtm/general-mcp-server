import os
import platform
import subprocess
import psutil
from mcp.server.fastmcp import FastMCP

# Commands blocked for safety
_BLOCKED = {
    "rm", "rmdir", "del", "format", "mkfs", "dd",
    "shutdown", "reboot", "halt", "poweroff",
    "reg", "regedit", "netsh", "iptables",
}


def register_system_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def run_command(command: str, timeout: int = 10) -> str:
        """
        Run a shell command and return its stdout + stderr output.
        Blocked commands: rm, del, format, shutdown, reboot, reg, netsh, and similar destructive ops.
        timeout: max seconds to wait (default 10, max 30).
        Returns combined stdout/stderr as a string.
        Example: run_command('dir E:\\claude\\MCP')
        """
        first_word = command.strip().split()[0].lower().rstrip(".exe")
        if first_word in _BLOCKED:
            return f"Error: '{first_word}' is blocked for safety."
        timeout = min(int(timeout), 30)
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True,
                text=True, timeout=timeout, encoding="utf-8", errors="replace"
            )
            out = result.stdout + result.stderr
            return out.strip() or f"(exit code {result.returncode}, no output)"
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {timeout}s"
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def system_info() -> str:
        """
        Return key system information: OS, CPU, RAM, disk usage, Python version.
        No arguments required.
        """
        try:
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return (
                f"OS          : {platform.system()} {platform.release()} ({platform.machine()})\n"
                f"Hostname    : {platform.node()}\n"
                f"CPU         : {platform.processor()}\n"
                f"CPU cores   : {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count()} logical\n"
                f"CPU usage   : {psutil.cpu_percent(interval=1)}%\n"
                f"RAM total   : {mem.total // (1024**3)} GB\n"
                f"RAM used    : {mem.used // (1024**3)} GB ({mem.percent}%)\n"
                f"Disk total  : {disk.total // (1024**3)} GB\n"
                f"Disk used   : {disk.used // (1024**3)} GB ({disk.percent}%)\n"
                f"Python      : {platform.python_version()}"
            )
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def get_env(variable: str = "") -> str:
        """
        Read environment variables.
        variable: specific variable name to read, e.g. 'PATH' or 'USERNAME'.
        Leave empty to list all variable names (values are hidden for security).
        Returns the value of the variable, or a list of names if empty.
        """
        if variable:
            val = os.environ.get(variable)
            return val if val is not None else f"Variable '{variable}' not set."
        return "\n".join(sorted(os.environ.keys()))

    @mcp.tool()
    def list_processes(filter: str = "") -> str:
        """
        List running processes with their PID, name, and CPU/memory usage.
        filter: optional substring to filter process names, e.g. 'python' or 'chrome'.
        Returns up to 30 matching processes sorted by memory usage (highest first).
        """
        try:
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    info = p.info
                    if filter.lower() in info["name"].lower():
                        procs.append(info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            procs.sort(key=lambda x: x.get("memory_percent") or 0, reverse=True)
            lines = ["PID    | Name                          | CPU%  | MEM%"]
            lines.append("-" * 60)
            for p in procs[:30]:
                lines.append(
                    f"{p['pid']:<7}| {p['name']:<31}| "
                    f"{(p['cpu_percent'] or 0):<6.1f}| {(p['memory_percent'] or 0):.2f}"
                )
            return "\n".join(lines) if len(lines) > 2 else "No matching processes."
        except Exception as e:
            return f"Error: {e}"
