#!/usr/bin/env python
"""Admin CLI for managing Tactician user accounts.

Commands:
    create <username>   Create a new account (prompts for password)
    delete <username>   Remove an existing account
    list                List all registered usernames

Examples:
    python src/manage_users.py create alice
    python src/manage_users.py list
    python src/manage_users.py delete alice
"""

import getpass
import json
import sys
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.web_utils import USERS_FILE, ensure_metadata_dirs, signup_user


def cmd_create(args: list) -> int:
    username = args[0] if args else input("Username: ").strip()
    if not username:
        print("ERROR: username cannot be empty.", file=sys.stderr)
        return 1
    password = getpass.getpass("Password: ")
    ensure_metadata_dirs()
    ok, msg = signup_user(username, password)
    print(f"{'OK' if ok else 'ERROR'}: {msg}")
    return 0 if ok else 1


def cmd_delete(args: list) -> int:
    username = args[0] if args else input("Username: ").strip()
    if not username:
        print("ERROR: username cannot be empty.", file=sys.stderr)
        return 1
    ensure_metadata_dirs()
    data: dict = json.loads(USERS_FILE.read_text()) if USERS_FILE.exists() else {}
    if username not in data:
        print(f"ERROR: user '{username}' not found.", file=sys.stderr)
        return 1
    del data[username]
    USERS_FILE.write_text(json.dumps(data, indent=2))
    print(f"OK: user '{username}' deleted.")
    return 0


def cmd_list(_args: list) -> int:
    ensure_metadata_dirs()
    data: dict = json.loads(USERS_FILE.read_text()) if USERS_FILE.exists() else {}
    if not data:
        print("No users registered.")
        return 0
    print(f"{len(data)} registered user(s):")
    for username in sorted(data):
        print(f"  {username}")
    return 0


_COMMANDS = {
    "create": cmd_create,
    "delete": cmd_delete,
    "list":   cmd_list,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in _COMMANDS:
        print(__doc__)
        print(f"Available commands: {', '.join(_COMMANDS)}")
        sys.exit(1)
    sys.exit(_COMMANDS[sys.argv[1]](sys.argv[2:]))
