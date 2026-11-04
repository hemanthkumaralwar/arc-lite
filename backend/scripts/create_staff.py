"""Add one staff account to the live database. Does not touch FAQ entries.

Run from the backend folder:
    venv\\Scripts\\activate
    python scripts\\create_staff.py

The password is typed at a hidden prompt and stored only as a bcrypt hash.
If the email already has an account, nothing is changed.
"""
import getpass
import re
import sys
from pathlib import Path

import bcrypt
from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.db import engine  # noqa: E402

BCRYPT_ROUNDS = 12
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def main() -> int:
    if engine is None:
        print("DATABASE_URL is empty. Set it in backend\\.env and run again.")
        return 1

    email = input("New staff email: ").strip().lower()
    if not EMAIL_PATTERN.match(email):
        print("That does not look like an email address.")
        return 1

    password = getpass.getpass("Password (at least 10 characters, hidden): ")
    if len(password) < 10:
        print("Password must be at least 10 characters.")
        return 1
    if len(password.encode("utf-8")) > 72:
        print("Password is longer than 72 bytes. Use a shorter one.")
        return 1

    confirm = getpass.getpass("Type the password again: ")
    if confirm != password:
        print("Passwords do not match. Nothing was created.")
        return 1

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS))

    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO staff (email, password_hash) VALUES (:email, :password_hash) "
                "ON CONFLICT (email) DO NOTHING"
            ),
            {"email": email, "password_hash": password_hash.decode("utf-8")},
        )

    if result.rowcount == 1:
        print(f"Created staff account {email}.")
    else:
        print(f"{email} already has an account. Nothing was changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
