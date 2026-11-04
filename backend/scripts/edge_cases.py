"""Edge-case pass against the deployed Arc Lite API.

Run from the backend folder:
    python scripts\\edge_cases.py https://YOUR-SERVICE.onrender.com

It prompts for the staff email and password (hidden). It does not create or change FAQ entries.
It creates a few conversation rows, which count toward the dashboard.

Optional expired-token check: if you set JWT_SECRET in this window first
(set JWT_SECRET=the-value-from-backend\\.env), the script also signs an expired token and
expects a 401. Skip this and the rest still runs.

Pass rules:
  - the status code matches what the brief requires
  - no 5xx response anywhere
  - every Answered reply uses text that exists in the FAQ table (no invented answers)
"""
import getpass
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx
import jwt

LONG_OK = "a" * 500
LONG_TOO_LONG = "a" * 501
WRONG_PASSWORD = "definitely-wrong-password-123"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts\\edge_cases.py https://YOUR-SERVICE.onrender.com")
        return 2

    base_url = sys.argv[1].rstrip("/")
    email = input("Staff email: ").strip()
    password = getpass.getpass("Staff password (hidden): ")

    client = httpx.Client(base_url=base_url, timeout=90)
    results: list[bool] = []
    server_errors: list[str] = []
    answered_texts: list[str] = []

    def record(name, response, expected, passed_extra=True, detail=""):
        status = response.status_code
        if status >= 500:
            server_errors.append(f"{name} returned {status}")
        ok = status == expected and passed_extra
        results.append(ok)
        label = "PASS" if ok else "FAIL"
        suffix = f" ({detail})" if detail else ""
        print(f"[{label}] {name}: got {status}, expected {expected}{suffix}")
        return response

    def body(response):
        try:
            return response.json()
        except ValueError:
            return {}

    # ---- chat: bad and unusual input ----
    print("\n-- Chat: input --")
    record("empty question", client.post("/chat", json={"question": ""}), 400)
    record("whitespace-only question", client.post("/chat", json={"question": " \t \n "}), 400)
    record("exactly 500 characters", client.post("/chat", json={"question": LONG_OK}), 200)
    record("501 characters", client.post("/chat", json={"question": LONG_TOO_LONG}), 400)
    record("missing question field", client.post("/chat", json={}), 400)
    record("question sent as a number", client.post("/chat", json={"question": 12345}), 400)
    record("malformed JSON",
           client.post("/chat", content="{not valid json", headers={"Content-Type": "application/json"}), 400)
    record("emoji only", client.post("/chat", json={"question": "🎓😀🎉"}), 200)
    record("script tag as question",
           client.post("/chat", json={"question": "<script>alert('x')</script>"}), 200)
    record("SQL-looking question",
           client.post("/chat", json={"question": "' OR 1=1 --; DROP TABLE faq_entries;"}), 200)

    refused = record(
        "nonsense question is refused",
        client.post("/chat", json={"question": "quantum chromodynamics lattice gauge"}),
        200,
        passed_extra=body(client.post("/chat", json={"question": "quantum chromodynamics lattice gauge"}))
        .get("verdict") == "Refused",
        detail="expects verdict Refused",
    )

    # Collect Answered replies so their text can be checked against the FAQ later.
    for question in [
        "how do I get my certificate",
        "I forgot my password",
        "how do I start a course",
        "job listings and how to apply",
    ]:
        response = client.post("/chat", json={"question": question})
        if response.status_code == 200 and body(response).get("verdict") == "Answered":
            answered_texts.append(body(response)["answer"])

    # ---- rating edge cases ----
    print("\n-- Rating --")
    chat = client.post("/chat", json={"question": "how do I get my certificate"})
    cid = body(chat).get("conversation_id")
    if cid is None:
        print("[FAIL] could not create a conversation to rate")
        results.append(False)
    else:
        record("rate up", client.post(f"/chat/{cid}/rate", json={"rating": "up"}), 200)
        record("rate with capital letters", client.post(f"/chat/{cid}/rate", json={"rating": "UP"}), 400)
        record("rate with empty value", client.post(f"/chat/{cid}/rate", json={"rating": ""}), 400)
        record("rate with missing value", client.post(f"/chat/{cid}/rate", json={}), 400)
    record("rate with non-numeric id", client.post("/chat/abc/rate", json={"rating": "up"}), 400)
    record("rate with negative id", client.post("/chat/-1/rate", json={"rating": "up"}), 400)
    record("rate with id zero", client.post("/chat/0/rate", json={"rating": "up"}), 404)
    record("rate unknown id", client.post("/chat/99999999/rate", json={"rating": "up"}), 404)
    record("rate id beyond database range",
           client.post(f"/chat/{2**63}/rate", json={"rating": "up"}), 404)

    # ---- sign-in edge cases ----
    print("\n-- Sign-in --")
    wrong = record("wrong password", client.post(
        "/auth/login", json={"email": email, "password": WRONG_PASSWORD}), 401)
    unknown = record("unknown email", client.post(
        "/auth/login", json={"email": "nobody-here@example.com", "password": WRONG_PASSWORD}), 401,
        passed_extra=body(client.post("/auth/login", json={"email": "nobody-here@example.com",
                                                           "password": WRONG_PASSWORD})) == body(wrong),
        detail="message must match the wrong-password message")
    record("empty password", client.post("/auth/login", json={"email": email, "password": ""}), 400)
    record("password over 72 bytes",
           client.post("/auth/login", json={"email": email, "password": "x" * 73}), 400)
    record("email without @", client.post("/auth/login", json={"email": "not-an-email", "password": "x"}), 400)
    record("SQL-looking email",
           client.post("/auth/login", json={"email": "x' OR '1'='1@a.com", "password": "x"}), 401)
    record("login with no body", client.post("/auth/login"), 400)
    record("unknown route returns JSON 404", client.get("/does-not-exist"), 404,
           passed_extra="error" in body(client.get("/does-not-exist")))

    # ---- staff-only: no token or bad token ----
    print("\n-- Staff-only: no or bad token --")
    record("FAQ list without token", client.get("/admin/faq"), 401)
    record("stats without token", client.get("/admin/stats"), 401)
    record("delete without token", client.delete("/admin/faq/1"), 401)
    record("FAQ list with malformed token",
           client.get("/admin/faq", headers={"Authorization": "Bearer not.a.token"}), 401)
    record("FAQ list with wrong scheme",
           client.get("/admin/faq", headers={"Authorization": "Basic abc123"}), 401)

    if os.environ.get("JWT_SECRET"):
        now = datetime.now(timezone.utc)
        expired = jwt.encode(
            {"sub": "1", "email": email, "role": "staff",
             "iat": now - timedelta(hours=10), "exp": now - timedelta(hours=2)},
            os.environ["JWT_SECRET"], algorithm="HS256",
        )
        record("expired token", client.get("/admin/faq", headers={"Authorization": f"Bearer {expired}"}), 401,
               passed_extra="expired" in body(client.get("/admin/faq",
                                                         headers={"Authorization": f"Bearer {expired}"}))
               .get("message", "").lower())
    else:
        print("[SKIP] expired token: JWT_SECRET is not set in this window")

    # ---- staff: valid token, bad input ----
    print("\n-- Staff: valid token, bad input --")
    login = client.post("/auth/login", json={"email": email, "password": password})
    token = body(login).get("access_token")
    if not token:
        print("[FAIL] staff sign-in failed, so the staff checks cannot run")
        results.append(False)
        faq_answers = set()
    else:
        headers = {"Authorization": f"Bearer {token}"}
        faq_response = record("FAQ list with valid token", client.get("/admin/faq", headers=headers), 200)
        faq_answers = {e["canonical_answer"] for e in body(faq_response).get("entries", [])}
        record("create entry with unknown category", client.post("/admin/faq", headers=headers, json={
            "category": "billing", "keywords": ["x"], "canonical_answer": "x"}), 400)
        record("create entry with no keywords", client.post("/admin/faq", headers=headers, json={
            "category": "jobs", "keywords": [], "canonical_answer": "x"}), 400)
        record("create entry with blank answer", client.post("/admin/faq", headers=headers, json={
            "category": "jobs", "keywords": ["x"], "canonical_answer": "   "}), 400)
        record("update with non-numeric id", client.put("/admin/faq/abc", headers=headers, json={
            "category": "jobs", "keywords": ["x"], "canonical_answer": "x"}), 400)
        record("delete unknown entry", client.delete("/admin/faq/99999999", headers=headers), 404)
        record("delete entry id zero", client.delete("/admin/faq/0", headers=headers), 404)
        record("stats with valid token", client.get("/admin/stats", headers=headers), 200)

    # ---- every Answered reply must come from the FAQ ----
    print("\n-- Answers come from the FAQ only --")
    invented = [text for text in answered_texts if text not in faq_answers]
    if not answered_texts:
        print("[INFO] no Answered replies were produced, so the FAQ check had nothing to compare")
    elif invented:
        print(f"[FAIL] {len(invented)} Answered reply text(s) are not in the FAQ table")
        results.append(False)
    else:
        print(f"[PASS] all {len(answered_texts)} Answered replies match FAQ text exactly")
        results.append(True)

    # ---- summary ----
    print()
    passed = sum(results)
    print(f"{passed} of {len(results)} checks passed.")
    if server_errors:
        print("Server errors (5xx) found:")
        for item in server_errors:
            print("  - " + item)
    else:
        print("No server errors (5xx) were returned.")

    return 0 if passed == len(results) and not server_errors else 1


if __name__ == "__main__":
    sys.exit(main())
