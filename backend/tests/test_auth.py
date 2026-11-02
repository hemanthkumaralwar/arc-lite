from collections import namedtuple

import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient

from app import auth as auth_module
from app import config
from app.main import app

client = TestClient(app)  # no `with` block, so the startup database load does not run

SECRET = "test-secret-that-is-at-least-thirty-two-characters-long"
PASSWORD = "correct-horse-battery"
EMAIL = "staff@example.com"
StaffRow = namedtuple("StaffRow", ["id", "email", "password_hash"])


class _FakeTransaction:
    def __enter__(self):
        return object()

    def __exit__(self, *exc):
        return False


class FakeEngine:
    def begin(self):
        return _FakeTransaction()


@pytest.fixture
def staff_db(monkeypatch):
    monkeypatch.setattr(config.settings, "jwt_secret", SECRET)
    monkeypatch.setattr(config.settings, "jwt_expiry_hours", 8)

    # Cost 4 keeps tests fast. Production uses cost 12 in seed.py and in the dummy hash.
    password_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
    row = StaffRow(id=7, email=EMAIL, password_hash=password_hash)

    def fake_get_staff(conn, email):
        return row if email == EMAIL else None

    monkeypatch.setattr(auth_module, "engine", FakeEngine())
    monkeypatch.setattr(auth_module, "get_staff_by_email", fake_get_staff)
    return password_hash


def login(email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_correct_credentials_return_token(staff_db):
    response = login(EMAIL, PASSWORD)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "staff"
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_token_has_staff_role_subject_and_eight_hour_expiry(staff_db):
    body = login(EMAIL, PASSWORD).json()
    claims = jwt.decode(body["access_token"], SECRET, algorithms=["HS256"])
    assert claims["role"] == "staff"
    assert claims["sub"] == "7"
    assert claims["email"] == EMAIL
    assert claims["exp"] - claims["iat"] == 8 * 3600
    assert body["expires_in"] == 8 * 3600


def test_token_signed_with_a_different_secret_is_rejected(staff_db):
    token = login(EMAIL, PASSWORD).json()["access_token"]
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "a-different-secret-that-is-also-long-enough", algorithms=["HS256"])


def test_wrong_password_is_401(staff_db):
    response = login(EMAIL, "wrong-password-here")
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


def test_unknown_email_is_401_with_the_same_message_as_wrong_password(staff_db):
    wrong_password = login(EMAIL, "wrong-password-here").json()
    unknown_email = login("nobody@example.com", PASSWORD)
    assert unknown_email.status_code == 401
    assert unknown_email.json() == wrong_password


def test_email_is_case_insensitive(staff_db):
    response = login("  STAFF@Example.com ", PASSWORD)
    assert response.status_code == 200


def test_response_never_contains_password_or_hash(staff_db):
    for response in [
        login(EMAIL, PASSWORD),
        login(EMAIL, "wrong-password-here"),
        login("nobody@example.com", PASSWORD),
    ]:
        text = response.text
        assert PASSWORD not in text
        assert staff_db not in text
        assert "$2b$" not in text


def test_missing_password_is_400(staff_db):
    response = client.post("/auth/login", json={"email": EMAIL})
    assert response.status_code == 400


def test_empty_password_is_400(staff_db):
    assert login(EMAIL, "").status_code == 400


def test_invalid_email_format_is_400(staff_db):
    assert login("not-an-email", PASSWORD).status_code == 400


def test_password_over_72_bytes_is_400(staff_db):
    assert login(EMAIL, "x" * 73).status_code == 400


def test_missing_database_returns_503(monkeypatch, staff_db):
    monkeypatch.setattr(auth_module, "engine", None)
    assert login(EMAIL, PASSWORD).status_code == 503


@pytest.mark.parametrize("secret", ["change-me", "too-short"])
def test_weak_jwt_secret_refuses_to_sign_in(monkeypatch, staff_db, secret):
    monkeypatch.setattr(config.settings, "jwt_secret", secret)
    response = login(EMAIL, PASSWORD)
    assert response.status_code == 503
    assert "access_token" not in response.json()


def test_verify_password_handles_malformed_hash():
    assert auth_module.verify_password(PASSWORD, "not-a-bcrypt-hash") is False


def test_verify_password_accepts_correct_and_rejects_wrong(staff_db):
    assert auth_module.verify_password(PASSWORD, staff_db) is True
    assert auth_module.verify_password("nope", staff_db) is False
