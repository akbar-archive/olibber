from __future__ import annotations

import base64
from getpass import getpass
from pathlib import Path

import instaloader

try:
    from instaloader import get_default_session_filename
except ImportError:
    from instaloader.instaloader import get_default_session_filename


def main() -> None:
    username = input("Instagram username: ").strip()
    if not username:
        raise SystemExit("Username is required.")

    password = input("Instagram password: ").strip()
    if not password:
        raise SystemExit("Password is required.")

    loader = instaloader.Instaloader(quiet=True)
    loader.login(username, password)
    loader.save_session_to_file()

    session_path = Path(get_default_session_filename(username))
    session_bytes = session_path.read_bytes()
    session_b64 = base64.b64encode(session_bytes).decode("utf-8")

    print()
    print(f"Session saved to: {session_path}")
    print("Paste this into INSTALOADER_SESSION_B64:")
    print(session_b64)


if __name__ == "__main__":
    main()