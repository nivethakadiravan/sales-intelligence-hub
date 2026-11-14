"""Password hashing and login verification.

Passwords are stored as salted PBKDF2-SHA256 hashes in the format
``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>`` - never as plain text.
Only the Python standard library is used, so no extra dependency is needed.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 200_000


def hash_password(password: str, *, salt: str | None = None, iterations: int = ITERATIONS) -> str:
    """Return a salted PBKDF2 hash string for ``password``."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
    return f"{ALGORITHM}${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check ``password`` against a hash produced by :func:`hash_password`."""
    try:
        algorithm, iterations, salt, expected = stored.split("$")
    except ValueError:
        return False
    if algorithm != ALGORITHM:
        return False
    candidate = hash_password(password, salt=salt, iterations=int(iterations))
    return hmac.compare_digest(candidate.split("$")[-1], expected)


def authenticate(username: str, password: str) -> dict | None:
    """Validate credentials against the ``users`` table.

    Returns the user row (without the password hash) on success, else ``None``.
    """
    from src.db import fetch_one  # local import keeps hashing usable without a DB

    row = fetch_one(
        """
        SELECT u.user_id, u.username, u.password, u.role, u.email,
               u.branch_id, b.branch_name
        FROM users u
        LEFT JOIN branches b ON b.branch_id = u.branch_id
        WHERE u.username = %s
        """,
        (username.strip(),),
    )
    if row and verify_password(password, row["password"]):
        row.pop("password")
        return row
    return None
