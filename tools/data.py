import csv
import json
import os
from mcp.server.fastmcp import FastMCP

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE, "data")


def _safe(filename: str) -> str | None:
    target = os.path.normpath(os.path.join(DATA_DIR, filename))
    return target if target.startswith(DATA_DIR) else None


def register_data_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def read_csv(filename: str, max_rows: int = 100) -> str:
        """
        Read a CSV file from the data/ directory and return it as a formatted table.
        filename: relative path inside data/, e.g. 'sales.csv'.
        max_rows: maximum rows to return (default 100).
        Returns pipe-separated rows with a header line.
        """
        path = _safe(filename)
        if not path:
            return "Error: path traversal not allowed."
        if not os.path.exists(path):
            return f"File not found: {filename}"
        try:
            with open(path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            if not rows:
                return "CSV is empty."
            headers = list(rows[0].keys())
            lines = [" | ".join(headers), "-" * 60]
            for row in rows[:max_rows]:
                lines.append(" | ".join(str(row.get(h, "")) for h in headers))
            if len(rows) > max_rows:
                lines.append(f"... ({len(rows) - max_rows} more rows)")
            return "\n".join(lines)
        except Exception as e:
            return f"Error reading CSV: {e}"

    @mcp.tool()
    def write_csv(filename: str, data: str) -> str:
        """
        Write JSON data to a CSV file in the data/ directory.
        filename: relative path inside data/, e.g. 'output.csv'.
        data: JSON string — either a list of objects [{"col1":"v1","col2":"v2"},...],
              or a list of lists [["col1","col2"],["v1","v2"],...] (first row = headers).
        Returns a confirmation with row count.
        """
        path = _safe(filename)
        if not path:
            return "Error: path traversal not allowed."
        try:
            rows = json.loads(data)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if not rows:
                return "Error: data is empty."
            with open(path, "w", newline="", encoding="utf-8") as f:
                if isinstance(rows[0], dict):
                    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(rows)
                else:
                    writer = csv.writer(f)
                    writer.writerows(rows)
            return f"Written {len(rows)} rows to {filename}"
        except Exception as e:
            return f"Error writing CSV: {e}"

    @mcp.tool()
    def query_csv(filename: str, column: str, value: str, operator: str = "eq") -> str:
        """
        Filter rows in a CSV file by a column value.
        filename: relative path inside data/, e.g. 'sales.csv'.
        column: column name to filter on.
        value: value to compare against.
        operator: 'eq' (equal), 'ne' (not equal), 'contains', 'gt' (greater than), 'lt' (less than).
        Returns matching rows as a pipe-separated table.
        """
        path = _safe(filename)
        if not path:
            return "Error: path traversal not allowed."
        if not os.path.exists(path):
            return f"File not found: {filename}"
        try:
            with open(path, encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            if not rows:
                return "CSV is empty."
            if column not in rows[0]:
                return f"Column '{column}' not found. Available: {', '.join(rows[0].keys())}"

            def match(row):
                cell = row[column]
                if operator == "eq":       return cell == value
                if operator == "ne":       return cell != value
                if operator == "contains": return value.lower() in cell.lower()
                if operator == "gt":
                    try: return float(cell) > float(value)
                    except: return False
                if operator == "lt":
                    try: return float(cell) < float(value)
                    except: return False
                return False

            matched = [r for r in rows if match(r)]
            if not matched:
                return "No matching rows."
            headers = list(matched[0].keys())
            lines = [" | ".join(headers), "-" * 60]
            for row in matched[:100]:
                lines.append(" | ".join(str(row.get(h, "")) for h in headers))
            lines.append(f"\n{len(matched)} row(s) matched.")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def read_json(filename: str) -> str:
        """
        Read a JSON file from the data/ directory and return its contents as a formatted string.
        filename: relative path inside data/, e.g. 'config.json'.
        Returns pretty-printed JSON with 2-space indentation.
        """
        path = _safe(filename)
        if not path:
            return "Error: path traversal not allowed."
        if not os.path.exists(path):
            return f"File not found: {filename}"
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return json.dumps(data, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"Error reading JSON: {e}"

    @mcp.tool()
    def write_json(filename: str, data: str) -> str:
        """
        Write data to a JSON file in the data/ directory.
        filename: relative path inside data/, e.g. 'output.json'.
        data: valid JSON string to write.
        Returns a confirmation message.
        """
        path = _safe(filename)
        if not path:
            return "Error: path traversal not allowed."
        try:
            parsed = json.loads(data)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)
            return f"Written to {filename}"
        except json.JSONDecodeError as e:
            return f"Error: invalid JSON — {e}"
        except Exception as e:
            return f"Error writing JSON: {e}"
