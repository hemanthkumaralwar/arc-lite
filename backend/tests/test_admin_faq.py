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


def valid_entry(**overrides):
    body = {
        "category": "jobs",
        "keywords": ["job", "vacancy"],
        "canonical_answer": "Job listings are shown in the jobs section.",
    }
    body.update(overrides)
    return body


@pytest.fixture
def store(monkeypatch):
    rows = {}
    counter = {"next": 0}
    chat_inserts = []

    def fake_list(conn):
        return [rows[key] for key in sorted(rows)]

    def fake_insert(conn, data):
        counter["next"] += 1
        row = Row(counter["next"], data["category"], list(data["keywords"]),
                  data["canonical_answer"], NOW, NOW)
        rows[row.id] = row
        return row

    def fake_update(conn, entry_id, data):
        if entry_id not in rows:
            return None
        old = rows[entry_id]
        row = Row(entry_id, data["category"], list(data["keywords"]),
                  data["canonical_answer"], old.created_at, NOW)
        rows[entry_id] = row
        return row

    def fake_load(conn):
        return [FaqDoc(r.id, r.category, tuple(r.keywords), r.canonical_answer)
                for r in sorted(rows.values(), key=lambda r: r.id)]

    def fake_chat_insert(conn, row):
        chat_inserts.append(row)
        return len(chat_inserts)

    monkeypatch.setattr(config.settings, "jwt_secret", SECRET)
    monkeypatch.setattr(admin_module, "engine", FakeEngine())
    monkeypatch.setattr(admin_module, "list_faq_entries", fake_list)
    monkeypatch.setattr(admin_module, "insert_faq_entry", fake_insert)
    monkeypatch.setattr(admin_module, "update_faq_entry", fake_update)
    monkeypatch.setattr(admin_module, "load_entries", fake_load)
    monkeypatch.setattr(chat_module, "engine", FakeEngine())
    monkeypatch.setattr(chat_module, "insert_conversation", fake_chat_insert)
    faq_index.build([])
    return rows


# ---- authorization ----

def test_list_without_token_is_401(store):
    assert client.get("/admin/faq").status_code == 401


def test_create_without_token_is_401(store):
    assert client.post("/admin/faq", json=valid_entry()).status_code == 401


def test_update_without_token_is_401(store):
    assert client.put("/admin/faq/1", json=valid_entry()).status_code == 401


def test_non_staff_token_is_403(store):
    response = client.post("/admin/faq", json=valid_entry(), headers=staff_headers(role="customer"))
    assert response.status_code == 403
    assert store == {}


def test_unauthenticated_request_with_bad_body_is_401_not_400(store):
    response = client.post("/admin/faq", json={"category": "nope"})
    assert response.status_code == 401


# ---- listing ----

def test_list_returns_entries_in_id_order(store):
    client.post("/admin/faq", json=valid_entry(), headers=staff_headers())
    client.post("/admin/faq", json=valid_entry(category="account", keywords=["password"],
                                               canonical_answer="Reset it."), headers=staff_headers())
    response = client.get("/admin/faq", headers=staff_headers())
    assert response.status_code == 200
    entries = response.json()["entries"]
    assert [e["id"] for e in entries] == [1, 2]
    assert entries[1]["category"] == "account"


# ---- creating ----

def test_create_returns_201_with_the_saved_entry(store):
    response = client.post("/admin/faq", json=valid_entry(), headers=staff_headers())
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["category"] == "jobs"
    assert body["keywords"] == ["job", "vacancy"]
    assert body["canonical_answer"] == "Job listings are shown in the jobs section."


def test_keywords_are_lowercased_trimmed_and_deduplicated(store):
    response = client.post(
        "/admin/faq",
        json=valid_entry(keywords=["  Reset ", "reset", "PASSWORD", "", "   ", "password"]),
        headers=staff_headers(),
    )
    assert response.status_code == 201
    assert response.json()["keywords"] == ["reset", "password"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"category": "billing"},
        {"category": ""},
        {"keywords": []},
        {"keywords": ["", "   "]},
        {"keywords": [f"k{i}" for i in range(31)]},
        {"keywords": ["x" * 51]},
        {"canonical_answer": ""},
        {"canonical_answer": "   "},
        {"canonical_answer": "a" * 2001},
    ],
)
def test_invalid_entry_is_400_and_not_saved(store, overrides):
    response = client.post("/admin/faq", json=valid_entry(**overrides), headers=staff_headers())
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"
    assert store == {}


def test_missing_field_is_400(store):
    response = client.post("/admin/faq", json={"category": "jobs"}, headers=staff_headers())
    assert response.status_code == 400


def test_new_entry_is_matched_by_chat_without_restart(store):
    client.post(
        "/admin/faq",
        json=valid_entry(category="certificates", keywords=["transcript", "request"],
                         canonical_answer="To request a transcript, contact the support team."),
        headers=staff_headers(),
    )
    response = client.post("/chat", json={"question": "how do I request a transcript"})
    body = response.json()
    assert body["category"] == "certificates"
    assert body["answer"] == "To request a transcript, contact the support team."


# ---- editing ----

def test_edit_updates_the_entry_and_refreshes_matching(store):
    client.post("/admin/faq", json=valid_entry(keywords=["job", "vacancy"]), headers=staff_headers())
    response = client.put(
        "/admin/faq/1",
        json=valid_entry(keywords=["passcode"], canonical_answer="Passcode help text."),
        headers=staff_headers(),
    )
    assert response.status_code == 200
    assert response.json()["keywords"] == ["passcode"]

    chat = client.post("/chat", json={"question": "passcode"}).json()
    assert chat["answer"] == "Passcode help text."


def test_edit_unknown_id_is_404(store):
    response = client.put("/admin/faq/999", json=valid_entry(), headers=staff_headers())
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_edit_non_numeric_id_is_400(store):
    response = client.put("/admin/faq/abc", json=valid_entry(), headers=staff_headers())
    assert response.status_code == 400


def test_edit_with_invalid_body_is_400(store):
    client.post("/admin/faq", json=valid_entry(), headers=staff_headers())
    response = client.put("/admin/faq/1", json=valid_entry(category="billing"), headers=staff_headers())
    assert response.status_code == 400


# ---- database ----

def test_missing_database_returns_503(monkeypatch, store):
    monkeypatch.setattr(admin_module, "engine", None)
    assert client.get("/admin/faq", headers=staff_headers()).status_code == 503
    assert client.post("/admin/faq", json=valid_entry(), headers=staff_headers()).status_code == 503
