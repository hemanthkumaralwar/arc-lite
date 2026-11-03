from collections import namedtuple
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app import admin as admin_module
from app import chat as chat_module
from app import config
from app.faq_index import FaqDoc, faq_index
from app.main import app

client = TestClient(app)  # no `with` block, so the startup database load does not run

SECRET = "test-secret-that-is-at-least-thirty-two-characters-long"
NOW = datetime(2026, 11, 3, tzinfo=timezone.utc)
Row = namedtuple("Row", "id category keywords canonical_answer created_at updated_at")


class _Transaction:
    def __enter__(self):
        return object()

    def __exit__(self, *exc):
        return False


class FakeEngine:
    def begin(self):
        return _Transaction()

    def connect(self):
        return _Transaction()


def staff_headers(role="staff"):
    payload = {
        "sub": "1",
        "email": "staff@example.com",
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return {"Authorization": f"Bearer {jwt.encode(payload, SECRET, algorithm='HS256')}"}


@pytest.fixture
def store(monkeypatch):
    rows = {}
    counter = {"next": 0}

    def fake_insert(conn, data):
        counter["next"] += 1
        row = Row(counter["next"], data["category"], list(data["keywords"]),
                  data["canonical_answer"], NOW, NOW)
        rows[row.id] = row
        return row

    def fake_list(conn):
        return [rows[key] for key in sorted(rows)]

    def fake_delete(conn, entry_id):
        return rows.pop(entry_id, None) is not None

    def fake_load(conn):
        return [FaqDoc(r.id, r.category, tuple(r.keywords), r.canonical_answer)
                for r in sorted(rows.values(), key=lambda r: r.id)]

    monkeypatch.setattr(config.settings, "jwt_secret", SECRET)
    monkeypatch.setattr(admin_module, "engine", FakeEngine())
    monkeypatch.setattr(admin_module, "insert_faq_entry", fake_insert)
    monkeypatch.setattr(admin_module, "list_faq_entries", fake_list)
    monkeypatch.setattr(admin_module, "delete_faq_entry", fake_delete)
    monkeypatch.setattr(admin_module, "load_entries", fake_load)
    monkeypatch.setattr(chat_module, "engine", FakeEngine())
    monkeypatch.setattr(chat_module, "insert_conversation", lambda conn, row: 1)
    faq_index.build([])
    return rows


def create(category="account", keywords=("passcode",), answer="Passcode help text."):
    return client.post(
        "/admin/faq",
        json={"category": category, "keywords": list(keywords), "canonical_answer": answer},
        headers=staff_headers(),
    )


def test_delete_without_token_is_401(store):
    create()
    assert client.delete("/admin/faq/1").status_code == 401
    assert 1 in store


def test_delete_with_non_staff_token_is_403(store):
    create()
    assert client.delete("/admin/faq/1", headers=staff_headers(role="customer")).status_code == 403
    assert 1 in store


def test_delete_removes_the_entry(store):
    create()
    response = client.delete("/admin/faq/1", headers=staff_headers())
    assert response.status_code == 200
    assert response.json() == {"id": 1, "deleted": True}
    assert store == {}


def test_deleted_entry_disappears_from_the_list(store):
    create()
    create(answer="Second entry.", keywords=("other",))
    client.delete("/admin/faq/1", headers=staff_headers())
    entries = client.get("/admin/faq", headers=staff_headers()).json()["entries"]
    assert [e["id"] for e in entries] == [2]


def test_chat_stops_answering_from_a_deleted_entry(store):
    create()
    before = client.post("/chat", json={"question": "passcode"}).json()
    assert before["answer"] == "Passcode help text."

    client.delete("/admin/faq/1", headers=staff_headers())

    after = client.post("/chat", json={"question": "passcode"}).json()
    assert after["answer"] != "Passcode help text."
    assert after["verdict"] in {"Unclear", "Refused"}


def test_deleting_an_unknown_entry_is_404(store):
    response = client.delete("/admin/faq/999", headers=staff_headers())
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_deleting_with_a_non_numeric_id_is_400(store):
    response = client.delete("/admin/faq/abc", headers=staff_headers())
    assert response.status_code == 400


def test_deleting_twice_second_attempt_is_404(store):
    create()
    client.delete("/admin/faq/1", headers=staff_headers())
    assert client.delete("/admin/faq/1", headers=staff_headers()).status_code == 404


def test_missing_database_returns_503(monkeypatch, store):
    monkeypatch.setattr(admin_module, "engine", None)
    assert client.delete("/admin/faq/1", headers=staff_headers()).status_code == 503
