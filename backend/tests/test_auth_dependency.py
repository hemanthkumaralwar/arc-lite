from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)  # no `with` block, so the startup database load does not run

SECRET = "test-secret-that-is-at-least-thirty-two-characters-long"
OTHER_SECRET = "a-different-secret-that-is-also-long-enough-to-pass"
EMAIL = "staff@example.com"


@pytest.fixture(autouse=True)
def configured_secret(monkeypatch):
    monkeypatch.setattr(config.settings, "jwt_secret", SECRET)
    monkeypatch.setattr(config.settings, "jwt_expiry_hours", 8)


def make_token(
    role="staff",
    hours=8,
    secret=SECRET,
    sub="7",
    email=EMAIL,
    include_role=True,
    algorithm="HS256",
):
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "email": email, "iat": now, "exp": now + timedelta(hours=hours)}
    if include_role:
        payload["role"] = role
    key = None if algorithm == "none" else secret
    return jwt.encode(payload, key, algorithm=algorithm)


def get_me(authorization=None):
    headers = {} if authorization is None else {"Authorization": authorization}
    return client.get("/auth/me", headers=headers)


# ---- 401: not signed in or token not acceptable ----

def test_missing_header_is_401():
    response = get_me()
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


@pytest.mark.parametrize("header", ["Basic abc123", "Bearer", "Bearer   ", "token-without-prefix"])
def test_malformed_header_is_401(header):
    assert get_me(header).status_code == 401


def test_garbage_token_is_401():
    assert get_me("Bearer not.a.jwt").status_code == 401


def test_token_signed_with_another_secret_is_401():
    token = make_token(secret=OTHER_SECRET)
    assert get_me(f"Bearer {token}").status_code == 401


def test_expired_token_is_401_with_session_expired_message():
    token = make_token(hours=-1)
    response = get_me(f"Bearer {token}")
    assert response.status_code == 401
    assert "expired" in response.json()["message"].lower()


def test_alg_none_token_is_401():
    token = make_token(algorithm="none")
    assert get_me(f"Bearer {token}").status_code == 401


def test_token_without_role_claim_is_401():
    token = make_token(include_role=False)
    assert get_me(f"Bearer {token}").status_code == 401


# ---- 403: valid token, wrong role ----

@pytest.mark.parametrize("role", ["customer", "student", "", "Staff"])
def test_valid_token_with_non_staff_role_is_403(role):
    token = make_token(role=role)
    response = get_me(f"Bearer {token}")
    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"


# ---- 200: valid staff token ----

def test_valid_staff_token_returns_the_signed_in_staff_member():
    token = make_token()
    response = get_me(f"Bearer {token}")
    assert response.status_code == 200
    assert response.json() == {"staff_id": 7, "email": EMAIL, "role": "staff"}


def test_bearer_scheme_is_case_sensitive_per_common_practice():
    token = make_token()
    assert get_me(f"bearer {token}").status_code == 401


def test_weak_secret_returns_503_even_with_a_valid_looking_token(monkeypatch):
    monkeypatch.setattr(config.settings, "jwt_secret", "change-me")
    token = make_token(secret="change-me")
    assert get_me(f"Bearer {token}").status_code == 503
