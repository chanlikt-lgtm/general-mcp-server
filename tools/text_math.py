import ast
import base64
import hashlib
import math
import operator
import re
from mcp.server.fastmcp import FastMCP


# Safe math evaluator — no eval() on arbitrary code
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_SAFE_FUNCS = {
    "abs": abs, "round": round, "sqrt": math.sqrt,
    "ceil": math.ceil, "floor": math.floor,
    "log": math.log, "log10": math.log10,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "pi": math.pi, "e": math.e,
}

def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant: {node.value}")
    elif isinstance(node, ast.BinOp):
        op = _SAFE_OPS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported operator: {node.op}")
        return op(_safe_eval(node.left), _safe_eval(node.right))
    elif isinstance(node, ast.UnaryOp):
        op = _SAFE_OPS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported unary operator: {node.op}")
        return op(_safe_eval(node.operand))
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls allowed")
        fn = _SAFE_FUNCS.get(node.func.id)
        if not fn:
            raise ValueError(f"Unknown function: {node.func.id}")
        args = [_safe_eval(a) for a in node.args]
        return fn(*args)
    elif isinstance(node, ast.Name):
        val = _SAFE_FUNCS.get(node.id)
        if val is None:
            raise ValueError(f"Unknown name: {node.id}")
        return val
    raise ValueError(f"Unsupported expression type: {type(node)}")


def register_text_math_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def calculate(expression: str) -> str:
        """
        Safely evaluate a math expression and return the result.
        Supports: +, -, *, /, //, %, ** (power), sqrt, abs, round,
        ceil, floor, log, log10, sin, cos, tan, pi, e.
        Examples: '2 ** 10', 'sqrt(144)', 'round(pi, 4)', '(3 + 4) * 2'
        No arbitrary code execution — only math operations allowed.
        """
        try:
            tree = ast.parse(expression.strip(), mode="eval")
            result = _safe_eval(tree)
            # return int if result is a whole number
            if isinstance(result, float) and result.is_integer():
                return str(int(result))
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def regex_search(pattern: str, text: str, flags: str = "") -> str:
        """
        Search for a regex pattern in text and return all matches.
        pattern: Python regex pattern, e.g. r'\\d+' or '[A-Z]+'
        text: the string to search in
        flags: optional comma-separated flags — 'ignorecase', 'multiline', 'dotall'
        Returns each match on its own line, or 'No matches found.'
        """
        try:
            flag_map = {
                "ignorecase": re.IGNORECASE,
                "multiline": re.MULTILINE,
                "dotall": re.DOTALL,
            }
            combined = 0
            for f in flags.lower().split(","):
                f = f.strip()
                if f and f in flag_map:
                    combined |= flag_map[f]
            matches = re.findall(pattern, text, combined)
            if not matches:
                return "No matches found."
            return "\n".join(str(m) for m in matches)
        except re.error as e:
            return f"Invalid regex: {e}"
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def word_count(text: str) -> str:
        """
        Count characters, words, lines, and unique words in a block of text.
        Returns a summary with all four counts.
        """
        lines = text.splitlines()
        words = text.split()
        unique = set(w.lower().strip(".,!?;:\"'") for w in words)
        return (
            f"Characters : {len(text)}\n"
            f"Words      : {len(words)}\n"
            f"Lines      : {len(lines)}\n"
            f"Unique words: {len(unique)}"
        )

    @mcp.tool()
    def hash_text(text: str, algorithm: str = "sha256") -> str:
        """
        Hash a string using a cryptographic hash function.
        algorithm: 'md5', 'sha1', 'sha256' (default), or 'sha512'
        Returns the hex digest of the hash.
        Example: hash_text('hello', 'md5') → '5d41402abc4b2a76b9719d911017c592'
        """
        algo = algorithm.lower().strip()
        supported = {"md5", "sha1", "sha256", "sha512"}
        if algo not in supported:
            return f"Error: unsupported algorithm '{algo}'. Choose from: {', '.join(supported)}"
        h = hashlib.new(algo)
        h.update(text.encode("utf-8"))
        return h.hexdigest()

    @mcp.tool()
    def encode_base64(text: str) -> str:
        """
        Encode a string to Base64.
        Returns the Base64-encoded string (UTF-8 input).
        Useful for encoding credentials, binary data references, or API payloads.
        """
        try:
            return base64.b64encode(text.encode("utf-8")).decode("ascii")
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def decode_base64(encoded: str) -> str:
        """
        Decode a Base64-encoded string back to plain text.
        encoded: a valid Base64 string.
        Returns the decoded UTF-8 string, or an error if input is invalid.
        """
        try:
            return base64.b64decode(encoded.encode("ascii")).decode("utf-8")
        except Exception as e:
            return f"Error: invalid Base64 input — {e}"
