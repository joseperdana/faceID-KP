#!/usr/bin/env python3
"""Generate a bcrypt hash for ADMIN_PASSWORD_HASH.

    python scripts/hash_password.py

The password is read without echoing and never written to disk or shell
history. Paste the printed hash into .env.
"""

import getpass
import sys


def main() -> int:
    try:
        import bcrypt
    except ImportError:
        print("bcrypt is not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        return 1

    password = getpass.getpass("Password admin baru: ")
    if len(password) < 12:
        print("Password minimal 12 karakter.", file=sys.stderr)
        return 1
    if password != getpass.getpass("Ulangi password      : "):
        print("Password tidak cocok.", file=sys.stderr)
        return 1

    # cost=12 is roughly 250 ms per verification — slow enough to make offline
    # cracking expensive, fast enough for an interactive login.
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    print("\nTambahkan baris ini ke .env (hapus ADMIN_PASSWORD yang lama):\n")
    print(f"ADMIN_PASSWORD_HASH={hashed.decode()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
