"""Authentication service providing secure password hashing, token management, and authentication utilities."""

import hashlib
import os
import secrets
import time
from typing import Optional, Tuple, Dict, Any

# In-memory token storage (persists during server lifetime, maps token -> user_id, expires_at)
# In production with multiple workers this can be stored in Redis or DB, but in-memory is fast and clean for single-instance
_ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}
TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 days


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    Hash a password using PBKDF2-HMAC-SHA256 with 100,000 iterations and a unique salt.
    Returns (password_hash, salt).
    """
    if not salt:
        salt = secrets.token_hex(16)
    
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return key.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verify a plain password against the stored hash and salt."""
    key, _ = hash_password(password, salt)
    return secrets.compare_digest(key, password_hash)


def generate_session_token(user_id: int, user_email: str) -> str:
    """Generate a cryptographically secure session token and register it in active sessions."""
    token = secrets.token_urlsafe(32)
    _ACTIVE_SESSIONS[token] = {
        "user_id": user_id,
        "email": user_email,
        "created_at": time.time(),
        "expires_at": time.time() + TOKEN_TTL_SECONDS
    }
    return token


def validate_session_token(token: str) -> Optional[int]:
    """Validate a session token. Returns user_id if valid, None if expired or invalid."""
    if not token:
        return None
    
    session = _ACTIVE_SESSIONS.get(token)
    if not session:
        return None
    
    if time.time() > session["expires_at"]:
        # Expired
        _ACTIVE_SESSIONS.pop(token, None)
        return None
    
    return session["user_id"]


def revoke_session_token(token: str) -> bool:
    """Revoke/invalidate a session token."""
    if token in _ACTIVE_SESSIONS:
        del _ACTIVE_SESSIONS[token]
        return True
    return False
