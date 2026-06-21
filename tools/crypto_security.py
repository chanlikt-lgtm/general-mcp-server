import base64
import hashlib
import os
import secrets
import string
import uuid
from mcp.server.fastmcp import FastMCP


def register_crypto_security_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def generate_password(length: int = 16, include_symbols: bool = True) -> str:
        """
        Generate a cryptographically secure random password.
        length: password length (default 16, min 8, max 128).
        include_symbols: whether to include symbols !@#$%^&* (default true).
        Returns the generated password.
        """
        length = max(8, min(128, int(length)))
        chars = string.ascii_letters + string.digits
        if include_symbols:
            chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"
        password = "".join(secrets.choice(chars) for _ in range(length))
        strength = "weak" if length < 12 else "strong" if length >= 20 else "medium"
        return f"Password : {password}\nLength   : {length}\nStrength : {strength}"

    @mcp.tool()
    def generate_uuid(version: int = 4, count: int = 1) -> str:
        """
        Generate one or more UUIDs.
        version: UUID version — 1 (time-based) or 4 (random, default).
        count: how many UUIDs to generate (default 1, max 20).
        Returns one UUID per line.
        """
        version = int(version)
        count   = max(1, min(20, int(count)))
        if version not in (1, 4):
            return "Error: only UUID version 1 and 4 are supported."
        results = []
        for _ in range(count):
            u = uuid.uuid1() if version == 1 else uuid.uuid4()
            results.append(str(u))
        return "\n".join(results)

    @mcp.tool()
    def encrypt_text(text: str, password: str) -> str:
        """
        Encrypt a text string using AES-256 (Fernet symmetric encryption).
        text: plaintext to encrypt.
        password: passphrase used to derive the encryption key.
        Returns a Base64-encoded encrypted token — store this safely.
        Decrypt with decrypt_text using the same password.
        """
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes
            salt = b"mcp_static_salt_v1"   # deterministic so same password → same key
            kdf  = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
            key  = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            f    = Fernet(key)
            token = f.encrypt(text.encode("utf-8"))
            return token.decode("ascii")
        except ImportError:
            return "Error: cryptography package not installed. Run: pip install cryptography"
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def decrypt_text(token: str, password: str) -> str:
        """
        Decrypt a token previously encrypted with encrypt_text.
        token: the Base64-encoded encrypted token from encrypt_text.
        password: the same passphrase used during encryption.
        Returns the original plaintext, or an error if password is wrong.
        """
        try:
            from cryptography.fernet import Fernet, InvalidToken
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes
            salt = b"mcp_static_salt_v1"
            kdf  = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
            key  = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            f    = Fernet(key)
            return f.decrypt(token.encode("ascii")).decode("utf-8")
        except ImportError:
            return "Error: cryptography package not installed."
        except Exception:
            return "Error: decryption failed — wrong password or corrupted token."

    @mcp.tool()
    def sign_text(text: str, secret: str) -> str:
        """
        Create an HMAC-SHA256 signature for a text message.
        text: the message to sign.
        secret: secret key for the HMAC signature.
        Returns the hex signature — use to verify data integrity.
        Verify by calling sign_text again with the same inputs and comparing outputs.
        """
        import hmac
        sig = hmac.new(secret.encode(), text.encode(), hashlib.sha256).hexdigest()
        return f"Signature : {sig}\nAlgorithm : HMAC-SHA256\nMessage   : {text[:80]}{'...' if len(text) > 80 else ''}"
