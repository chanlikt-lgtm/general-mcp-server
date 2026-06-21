import json
import urllib.request
import urllib.error
from mcp.server.fastmcp import FastMCP

TIMEOUT = 10
MAX_BYTES = 8000


def register_web_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def fetch_url(url: str) -> str:
        """
        Fetch the text content of a public URL via HTTP GET.
        url: full URL including scheme, e.g. 'https://api.example.com/data'.
        Returns the response body as a string (capped at 8000 chars).
        Returns an error message if the request fails.
        """
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
                return r.read(MAX_BYTES).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            return f"Request failed: {e}"

    @mcp.tool()
    def call_api(url: str, method: str = "GET", body: str = "", headers: str = "") -> str:
        """
        Make an HTTP request to a REST API endpoint.
        url: full URL including scheme.
        method: HTTP verb — GET or POST (default: GET).
        body: JSON string to send as the request body for POST requests (optional).
        headers: JSON object of extra request headers, e.g. '{"Authorization": "Bearer token"}' (optional).
        Returns the response body as a string (capped at 8000 chars).
        """
        try:
            data = body.encode("utf-8") if body else None
            req = urllib.request.Request(url, data=data, method=method.upper())
            req.add_header("Content-Type", "application/json")
            if headers:
                for k, v in json.loads(headers).items():
                    req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read(MAX_BYTES).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            return f"Request failed: {e}"
