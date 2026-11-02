"""Seed FAQ entries and one staff login.

Run from the backend folder:
    python scripts\\seed.py

- FAQ entries are inserted only if faq_entries is empty, so re-running is safe.
- The staff password is typed at a hidden prompt. Only its bcrypt hash (cost 12) is stored.
  The password itself is never written to a file or printed.

The canonical answers below are PLACEHOLDERS. Replace them with verified ArchintX
policy before submission. Arc Lite must never present an unverified answer as fact.
"""
import getpass
import sys
from pathlib import Path

import bcrypt
from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.db import engine  # noqa: E402

BCRYPT_COST = 12

FAQ_SEED = [
    # courses
    {
        "category": "courses",
        "keywords": ["start course", "enroll", "enrol", "register for course", "begin course"],
        "canonical_answer": "To start a course, open it from the programme catalogue and use the enrol or start button. Make sure you are signed in to your student account first.",
    },
    {
        "category": "courses",
        "keywords": ["cannot open course", "course locked", "lost access", "course access"],
        "canonical_answer": "If you cannot open a course you are enrolled in, sign out, sign back in, and check the course page again. If it still does not open, contact the programme team.",
    },
    {
        "category": "courses",
        "keywords": ["course progress", "track progress", "completion status", "how far"],
        "canonical_answer": "Your progress for each course is shown on your dashboard. If the progress shown looks wrong, contact the programme team with the course name.",
    },
    # certificates
    {
        "category": "certificates",
        "keywords": ["certificate", "get certificate", "download certificate", "certificate issued"],
        "canonical_answer": "Certificates are issued after you meet the completion requirements for a course. Check the course page for the exact requirements, then download the certificate from your account page.",
    },
    {
        "category": "certificates",
        "keywords": ["wrong name", "name on certificate", "certificate name", "spelling on certificate"],
        "canonical_answer": "If the name on your certificate is wrong, contact the programme team with your registered email address and the correct spelling. Name corrections are made by the team.",
    },
    {
        "category": "certificates",
        "keywords": ["verify certificate", "certificate authentic", "prove certificate", "certificate genuine"],
        "canonical_answer": "If you need to prove a certificate is genuine, contact the programme team with the certificate details. They will confirm whether it was issued.",
    },
    # jobs
    {
        "category": "jobs",
        "keywords": ["job", "jobs", "job openings", "apply for job", "job listings"],
        "canonical_answer": "Job listings are shown in the jobs section. Read each listing's requirements carefully before you apply.",
    },
    {
        "category": "jobs",
        "keywords": ["resume", "cv", "resume review", "improve resume"],
        "canonical_answer": "Check your course materials for resume guidance. If you need more help, ask the programme team.",
    },
    {
        "category": "jobs",
        "keywords": ["interview", "interview preparation", "prepare for interview", "interview tips"],
        "canonical_answer": "Interview preparation resources, if available for your batch, are listed in your course materials. Ask the programme team if you cannot find them.",
    },
    # account
    {
        "category": "account",
        "keywords": ["forgot password", "reset password", "change password", "password"],
        "canonical_answer": "Use the password reset option on the sign-in page. If you do not receive the reset email, check your spam folder and confirm the email address on your account.",
    },
    {
        "category": "account",
        "keywords": ["change email", "update email", "new email address", "email change"],
        "canonical_answer": "Email changes are not self-service. Contact the programme team with your current email address and the new one.",
    },
    {
        "category": "account",
        "keywords": ["cannot sign in", "cannot log in", "login problem", "sign in issue"],
        "canonical_answer": "Check your email and password, then try password reset if needed. If you still cannot sign in, contact the programme team.",
    },
]


def seed_faq(conn) -> None:
    count = conn.execute(text("SELECT count(*) FROM faq_entries")).scalar_one()
    if count > 0:
        print(f"faq_entries already has {count} rows. Skipping FAQ seed.")
        return
    for entry in FAQ_SEED:
        conn.execute(
            text(
                "INSERT INTO faq_entries (category, keywords, canonical_answer) "
                "VALUES (:category, :keywords, :canonical_answer)"
            ),
            {
                "category": entry["category"],
                "keywords": [k.lower() for k in entry["keywords"]],
                "canonical_answer": entry["canonical_answer"],
            },
        )
    print(f"Inserted {len(FAQ_SEED)} FAQ entries.")


def seed_staff(conn) -> None:
    email = input("Staff email to create: ").strip().lower()
    if not email or "@" not in email:
        print("A valid email is required. Staff not created.")
        return

    existing = conn.execute(
        text("SELECT 1 FROM staff WHERE email = :email"), {"email": email}
    ).first()
    if existing:
        print(f"Staff account {email} already exists. Skipping.")
        return

    password = getpass.getpass("Password for this staff account (hidden): ")
    confirm = getpass.getpass("Repeat password (hidden): ")
    if not password or password != confirm:
        print("Passwords were empty or did not match. Staff not created.")
        return
    if len(password.encode("utf-8")) > 72:
        print("Password is longer than 72 bytes (bcrypt limit). Use a shorter password.")
        return

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_COST)).decode("utf-8")
    conn.execute(
        text("INSERT INTO staff (email, password_hash) VALUES (:email, :password_hash)"),
        {"email": email, "password_hash": password_hash},
    )
    print(f"Created staff account {email}. Password stored as a bcrypt hash.")


def main() -> int:
    if engine is None:
        print("DATABASE_URL is empty. Set it in backend\\.env and run again.")
        return 1

    with engine.begin() as conn:
        seed_faq(conn)
        seed_staff(conn)

    print("Seed finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
