"""Apply app/schema.sql to the database named in backend/.env (DATABASE_URL).

Run from the backend folder:
    python scripts\\migrate.py
"""
import sys
from pathlib import Path

from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import ENV_FILE  # noqa: E402
from app.db import engine  # noqa: E402

SCHEMA_FILE = BACKEND_DIR / "app" / "schema.sql"


def main() -> int:
    if engine is None:
        print("DATABASE_URL is empty.")
        print(f"Looked for .env here: {ENV_FILE}")
        print(f".env exists at that path: {ENV_FILE.exists()}")
        print("Fix: open that exact file in Notepad, make sure it has a line")
        print("DATABASE_URL=postgresql://... with no spaces around the = sign,")
        print("then save it with Encoding set to UTF-8 (not UTF-8 with BOM).")
        return 1

    statements = [
        part.strip()
        for part in SCHEMA_FILE.read_text(encoding="utf-8").split(";")
        if part.strip()
    ]

    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))

        tables = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
        ).scalars().all()

    print(f"Applied {len(statements)} statements from {SCHEMA_FILE.name}.")
    print("Tables in public schema:")
    for name in tables:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())