import hashlib
import hmac
import json
import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional
import time

from PIL import Image

BASE = Path(__file__).resolve().parents[1]
CARDS_DIR = BASE / "output" / "cards"
META_DIR = BASE / "output" / "metadata"
USERS_FILE = META_DIR / "users.json"
DECKS_DIR = META_DIR / "decks"
NAMES_FILE = META_DIR / "card_names.json"
TYPES_FILE = META_DIR / "card_types.json"

# Mapping of filename to actual card name
CARD_NAMES = {}

# Cache for card types
_card_types_cache: Optional[dict] = None

# Cache for card discovery (invalidated by file modification time)
_discover_cache: Optional[tuple] = None
_discover_cache_time: float = 0


def ensure_metadata_dirs():
    META_DIR.mkdir(parents=True, exist_ok=True)
    DECKS_DIR.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        USERS_FILE.write_text(json.dumps({}))


@lru_cache(maxsize=1)
def _load_card_names() -> Dict[str, str]:
    """Load card names from JSON file with caching."""
    if not NAMES_FILE.exists():
        return {}
    try:
        return json.loads(NAMES_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


@lru_cache(maxsize=1)
def _load_card_types() -> Dict[str, str]:
    """Load card types from JSON file with caching."""
    if not TYPES_FILE.exists():
        return {}
    try:
        return json.loads(TYPES_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def discover_cards():
    """Return list of dicts: {theme, name, filename, path}
    
    Uses caching based on directory modification time to avoid repeated file system scans.
    """
    global _discover_cache, _discover_cache_time
    
    if not CARDS_DIR.exists():
        return []
    
    # Check if directory has been modified (new files added/removed)
    try:
        dir_mtime = CARDS_DIR.stat().st_mtime
        # Also check modification time of card_names.json and card_types.json
        names_mtime = NAMES_FILE.stat().st_mtime if NAMES_FILE.exists() else 0
        types_mtime = TYPES_FILE.stat().st_mtime if TYPES_FILE.exists() else 0
        max_mtime = max(dir_mtime, names_mtime, types_mtime)

        # Return cached result if directory hasn't changed
        if _discover_cache is not None and max_mtime <= _discover_cache_time:
            return _discover_cache
    except (OSError, AttributeError):
        # If stat fails, proceed without cache
        pass

    # Load card names and types (cached internally)
    card_names = _load_card_names()
    card_types = _load_card_types()
    
    results = []
    try:
        for p in sorted(CARDS_DIR.iterdir()):
            if p.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                continue
            # expect filename like Theme_card_000.png or similar
            name = p.stem
            # try to split theme and name
            parts = name.split("_")
            theme = parts[0] if parts else "Unknown"
            # Use actual name if available
            actual_name = card_names.get(p.name, name)
            # Get card type
            card_type = card_types.get(p.name, "Unknown")
            results.append({"theme": theme, "name": actual_name, "filename": p.name, "path": str(p), "type": card_type})
    except (OSError, PermissionError):
        # Handle permission errors gracefully
        pass
    
    # Update cache
    _discover_cache = results
    try:
        dir_mtime = CARDS_DIR.stat().st_mtime
        names_mtime = NAMES_FILE.stat().st_mtime if NAMES_FILE.exists() else 0
        types_mtime = TYPES_FILE.stat().st_mtime if TYPES_FILE.exists() else 0
        _discover_cache_time = max(dir_mtime, names_mtime, types_mtime)
    except (OSError, AttributeError):
        _discover_cache_time = time.time()
    
    return results


@lru_cache(maxsize=128)
def load_card_image(path: str) -> Image.Image:
    """Load and convert card image to RGB with LRU caching.
    
    Caches up to 128 images in memory to avoid repeated file I/O.
    Cache is keyed by file path and automatically evicts least recently used items.
    """
    return Image.open(path).convert("RGB")


# Cache for users file (invalidated on write)
_users_cache: Optional[dict] = None
_users_cache_time: float = 0


def _read_users():
    """Read users file with caching based on modification time."""
    global _users_cache, _users_cache_time
    
    if not USERS_FILE.exists():
        return {}
    
    try:
        mtime = USERS_FILE.stat().st_mtime
        if _users_cache is not None and mtime <= _users_cache_time:
            return _users_cache
    except (OSError, AttributeError):
        pass
    
    try:
        _users_cache = json.loads(USERS_FILE.read_text())
        try:
            _users_cache_time = USERS_FILE.stat().st_mtime
        except (OSError, AttributeError):
            _users_cache_time = time.time()
        return _users_cache
    except Exception:
        return {}


def _write_users(d):
    """Write users file and invalidate cache."""
    global _users_cache, _users_cache_time
    USERS_FILE.write_text(json.dumps(d, indent=2))
    _users_cache = d
    try:
        _users_cache_time = USERS_FILE.stat().st_mtime
    except (OSError, AttributeError):
        _users_cache_time = time.time()


_PBKDF2_ITERS = 260_000  # OWASP-recommended minimum for PBKDF2-SHA256 (2024)
_MIN_PASSWORD_LEN = 8


def _hash_password(password: str, salt: bytes) -> str:
    """Derive a hex digest using PBKDF2-HMAC-SHA256 with a caller-supplied salt."""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERS)
    return dk.hex()


def signup_user(username: str, password: str, allowed_users: Optional[List[str]] = None):
    if not username:
        return False, "username required"
    if allowed_users is not None and username not in allowed_users:
        return False, "not authorised – contact your administrator"
    if len(password) < _MIN_PASSWORD_LEN:
        return False, f"password must be at least {_MIN_PASSWORD_LEN} characters"
    users = _read_users()
    if username in users:
        return False, "user exists"
    salt = secrets.token_bytes(32)
    users[username] = {
        "pw":   _hash_password(password, salt),
        "salt": salt.hex(),
    }
    _write_users(users)
    return True, "account created"


def login_user(username: str, password: str, allowed_users: Optional[List[str]] = None):
    # Allowlist check before touching the credential store
    if allowed_users is not None and username not in allowed_users:
        _hash_password(password, b"\x00" * 32)  # timing parity
        return False, "invalid credentials"
    users = _read_users()
    if username not in users:
        _hash_password(password, b"\x00" * 32)  # timing parity
        return False, "invalid credentials"
    record = users[username]
    if "salt" not in record:
        return False, "account needs password reset – please sign up again"
    salt = bytes.fromhex(record["salt"])
    expected = _hash_password(password, salt)
    # Constant-time comparison prevents timing attacks
    if hmac.compare_digest(expected, record["pw"]):
        return True, "ok"
    return False, "invalid credentials"


def save_deck(username, deck_name, filenames):
    if not deck_name:
        deck_name = "deck"
    deck_file = DECKS_DIR / f"{username}__{deck_name}.json"
    deck_file.write_text(json.dumps({"owner": username, "cards": filenames}, indent=2))


def list_decks(username):
    out = []
    for p in sorted(DECKS_DIR.iterdir()):
        if p.is_file() and p.name.startswith(f"{username}__"):
            out.append(p.name.split("__", 1)[1].rsplit(".", 1)[0])
    return out


@lru_cache(maxsize=64)
def load_deck(username, deck_name):
    """Load deck with caching. Cache is cleared when decks are modified."""
    p = DECKS_DIR / f"{username}__{deck_name}.json"
    if not p.exists():
        return []
    try:
        d = json.loads(p.read_text())
        return d.get("cards", [])
    except Exception:
        return []


def clear_caches():
    """Clear all caches. Useful when files are modified externally."""
    global _discover_cache, _discover_cache_time, _users_cache, _users_cache_time
    _discover_cache = None
    _discover_cache_time = 0
    _users_cache = None
    _users_cache_time = 0
    _load_card_names.cache_clear()
    _load_card_types.cache_clear()
    load_card_image.cache_clear()
    load_deck.cache_clear()
