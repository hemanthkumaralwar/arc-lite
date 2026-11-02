import pytest
from fastapi.testclient import TestClient

from app import chat as chat_module
from app.faq_index import FaqDoc, faq_index
from app.main import app


class _FakeTransaction:
    def __enter__(self):
        return object()

    def __exit__(self, *exc):
        return False


class FakeEngine:
    def begin(self):
        return _FakeTransaction()


@pytest.fixture
def stored_rows(monkeypatch):
    rows = []

    def fake_insert(conn, row):
        rows.append(row)
        return len(rows)

    monkeypatch.setattr(chat_module, "engine", FakeEngine())
    monkeypatch.setattr(chat_module, "insert_conversation", fake_insert)
    faq_index.build(
        [
            FaqDoc(1, "certificates", ("certificate", "get", "download"),
                   "Certificates are issued after you complete the course requirements."),
            FaqDoc(2, "courses", ("start", "enroll", "course"),
                   "To start a course, open it from your dashboard."),
            FaqDoc(3, "account", ("password", "reset", "forgot"),
                   "Use the password reset option on the sign-in page."),
        ]
    )
    return rows


# TestClient without a `with` block does not run the lifespan, so no database is needed at startup.
client = TestClient(app)


def test_empty_question_is_400_and_nothing_is_recorded(stored_rows):
    response = client.post("/chat", json={"question": "   "})
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"
    assert stored_rows == []


def test_too_long_question_is_400(stored_rows):
    response = client.post("/chat", json={"question": "a" * 501})
    assert response.status_code == 400
    assert stored_rows == []


def test_valid_question_returns_verdict_category_answer_and_id(stored_rows):
    response = client.post("/chat", json={"question": "how do I get my certificate"})
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] in {"Answered", "Unclear", "Refused"}
    assert body["answer_type"] in {"faq", "clarify", "refusal"}
    assert isinstance(body["answer"], str) and body["answer"]
    assert body["conversation_id"] == 1
    assert isinstance(body["response_ms"], int) and body["response_ms"] >= 0


def test_every_valid_call_writes_one_conversation_row(stored_rows):
    client.post("/chat", json={"question": "how do I get my certificate"})
    client.post("/chat", json={"question": "quantum physics"})
    assert len(stored_rows) == 2
    assert stored_rows[0]["question"] == "how do I get my certificate"


def test_refused_question_returns_refusal_text_with_null_category(stored_rows):
    response = client.post("/chat", json={"question": "quantum physics"})
    body = response.json()
    assert body["verdict"] == "Refused"
    assert body["category"] is None
    assert body["answer_type"] == "refusal"


def test_missing_database_returns_503_json(monkeypatch):
    monkeypatch.setattr(chat_module, "engine", None)
    response = client.post("/chat", json={"question": "hello"})
    assert response.status_code == 503
    assert response.json()["error"] == "error"
