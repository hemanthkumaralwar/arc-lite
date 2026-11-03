"""Live smoke test for the deployed Arc Lite API.

Run from the backend folder:
    python scripts\\smoke_test.py https://YOUR-SERVICE.onrender.com

It prompts for the staff email and password (hidden). It reads and writes conversation
ratings and creates a few conversation rows, which count toward the analytics dashboard.
It does not create or change FAQ entries.

A live 403 check needs a non-staff account, which the project does not have. The test
suite covers 403 fully.
"""
import getpass
import sys

import httpx

NOT_A_REAL_PASSWORD = "definitely-wrong-password-123"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts\\smoke_test.py https://YOUR-SERVICE.onrender.com")
        return 2

    base_url = sys.argv[1].rstrip("/")
    email = input("Staff email: ").strip()
    password = getpass.getpass("Staff password (hidden): ")

    # The first request can take 30 to 60 seconds if the free Render service was asleep.
    client = httpx.Client(base_url=base_url, timeout=90)
    results: list[bool] = []

    def check(name, response, expected_status, extra=None):
        ok = response.status_code == expected_status
        if ok and extra is not None:
            ok = bool(extra(response))
        results.append(ok)
        label = "PASS" if ok else "FAIL"
        print(f"[{label}] {name}: got {response.status_code}, expected {expected_status}")
        return response

    def json_or_empty(response):
        try:
            return response.json()
        except ValueError:
            return {}

    # ---- public endpoints ----
    check("health", client.get("/health"), 200,
          lambda r: json_or_empty(r) == {"status": "ok"})

    chat = check(
        "chat: matched question",
        client.post("/chat", json={"question": "how do I get my certificate"}),
        200,
        lambda r: json_or_empty(r).get("verdict") in {"Answered", "Unclear", "Refused"}
        and isinstance(json_or_empty(r).get("conversation_id"), int),
    )
    conversation_id = json_or_empty(chat).get("conversation_id")

    check(
        "chat: nonsense question is refused",
        client.post("/chat", json={"question": "quantum chromodynamics lattice gauge"}),
        200,
        lambda r: json_or_empty(r).get("verdict") == "Refused"
        and json_or_empty(r).get("answer_type") == "refusal",
    )

    check("chat: empty question is 400", client.post("/chat", json={"question": "   "}), 400)

    if conversation_id is not None:
        check(
            "rate: thumbs up is stored",
            client.post(f"/chat/{conversation_id}/rate", json={"rating": "up"}),
            200,
        )
    check("rate: invalid rating is 400",
          client.post(f"/chat/{conversation_id or 1}/rate", json={"rating": "sideways"}), 400)
    check("rate: unknown conversation is 404",
          client.post("/chat/99999999/rate", json={"rating": "up"}), 404)

    # ---- sign-in ----
    check("login: wrong password is 401",
          client.post("/auth/login", json={"email": email, "password": NOT_A_REAL_PASSWORD}), 401)

    login = check(
        "login: correct credentials return a token",
        client.post("/auth/login", json={"email": email, "password": password}),
        200,
        lambda r: json_or_empty(r).get("role") == "staff" and json_or_empty(r).get("access_token"),
    )
    token = json_or_empty(login).get("access_token")

    # ---- staff-only endpoints ----
    check("admin faq: no token is 401", client.get("/admin/faq"), 401)
    check("admin stats: no token is 401", client.get("/admin/stats"), 401)
    check("auth me: malformed token is 401",
          client.get("/auth/me", headers={"Authorization": "Bearer not.a.token"}), 401)

    if token:
        headers = {"Authorization": f"Bearer {token}"}
        check("auth me: valid token returns the staff member",
              client.get("/auth/me", headers=headers), 200,
              lambda r: json_or_empty(r).get("role") == "staff")
        check("admin faq: list entries",
              client.get("/admin/faq", headers=headers), 200,
              lambda r: isinstance(json_or_empty(r).get("entries"), list)
              and len(json_or_empty(r)["entries"]) >= 12)
        check("admin stats: live analytics",
              client.get("/admin/stats", headers=headers), 200,
              lambda r: "totals" in json_or_empty(r) and "by_category" in json_or_empty(r))
    else:
        print("Skipping staff checks because sign-in did not return a token.")

    passed = sum(results)
    print()
    print(f"{passed} of {len(results)} checks passed.")
    if passed == len(results):
        print("All live checks passed. Live 403 is covered by the test suite, not this script.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
