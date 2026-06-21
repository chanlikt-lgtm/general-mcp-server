import smtplib
import socket
import subprocess
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mcp.server.fastmcp import FastMCP

try:
    from dotenv import load_dotenv
    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_BASE, ".env"))
except ImportError:
    pass


def register_network_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def ping_host(host: str, count: int = 4) -> str:
        """
        Ping a host and return latency results.
        host: hostname or IP address, e.g. 'google.com' or '8.8.8.8'.
        count: number of ping packets to send (default 4, max 10).
        Returns round-trip time stats or an error if unreachable.
        """
        count = min(int(count), 10)
        try:
            result = subprocess.run(
                ["ping", "-n", str(count), host],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace"
            )
            return result.stdout.strip() or result.stderr.strip()
        except subprocess.TimeoutExpired:
            return f"Ping timed out after 30s."
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def dns_lookup(hostname: str) -> str:
        """
        Perform a DNS lookup for a hostname and return its IP addresses.
        hostname: domain name to resolve, e.g. 'google.com' or 'api.openai.com'.
        Returns all resolved IP addresses.
        """
        try:
            results = socket.getaddrinfo(hostname, None)
            ips = sorted(set(r[4][0] for r in results))
            return f"DNS lookup for '{hostname}':\n" + "\n".join(ips)
        except socket.gaierror as e:
            return f"DNS resolution failed for '{hostname}': {e}"
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def check_port(host: str, port: int, timeout: int = 5) -> str:
        """
        Check if a TCP port is open on a host.
        host: hostname or IP address.
        port: TCP port number, e.g. 80, 443, 8080, 5432.
        timeout: connection timeout in seconds (default 5).
        Returns OPEN or CLOSED with response time.
        """
        import time
        try:
            start = time.time()
            with socket.create_connection((host, int(port)), timeout=int(timeout)):
                elapsed = (time.time() - start) * 1000
                return f"Port {port} on {host}: OPEN ({elapsed:.1f}ms)"
        except (socket.timeout, ConnectionRefusedError, OSError):
            return f"Port {port} on {host}: CLOSED"
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def send_email(to: str, subject: str, body: str) -> str:
        """
        Send an email via SMTP using credentials from the .env file.
        Requires in .env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM.
        to: recipient email address, e.g. 'user@example.com'.
        subject: email subject line.
        body: plain text email body.
        Returns a confirmation or error message.
        """
        smtp_host = os.getenv("SMTP_HOST", "")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_pass = os.getenv("SMTP_PASSWORD", "")
        smtp_from = os.getenv("SMTP_FROM", smtp_user)

        if not all([smtp_host, smtp_user, smtp_pass]):
            return (
                "Error: SMTP not configured. Add to E:\\claude\\MCP\\.env:\n"
                "  SMTP_HOST=smtp.gmail.com\n"
                "  SMTP_PORT=587\n"
                "  SMTP_USER=your@email.com\n"
                "  SMTP_PASSWORD=your-app-password\n"
                "  SMTP_FROM=your@email.com"
            )
        try:
            msg = MIMEMultipart()
            msg["From"]    = smtp_from
            msg["To"]      = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, to, msg.as_string())
            return f"Email sent to {to} — Subject: '{subject}'"
        except Exception as e:
            return f"Failed to send email: {e}"
