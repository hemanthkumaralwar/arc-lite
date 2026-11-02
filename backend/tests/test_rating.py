import pytest
from fastapi.testclient import TestClient

from app import chat as chat_module
from app.main import app
from app.repository import update_rating

client = TestClient(app)  # no `with` block, so the startup lifespan (database index load) does not run

KNOWN_IDS = {1, 2}


class _FakeTransaction:
    def __enter__(self):
        return object()

    def __exit__(self, *exc):
        return False


class FakeEngine:
    def begin(self):
        return _FakeTransaction()


@pytest.fixture
def ratings(monkeypatch):
    stored = {}

    def fake_update(conn, conversation_id, rating):
        if conversation_id not in KNOWN_IDS:
            return False
        stored[conversation_id] = rating
        return True

    monkeypatch.setattr(chat_module, "engine", FakeEngine())
    monkeypatch.setattr(chat_module, "update_rating", fake_update)
    return stored


def test_thumbs_up_is_stored_and_returned(ratings):
    response = client.post("/chat/1/rate", json={"rating": "up"})
    assert response.status_code == 200
    assert response.json() == {"conversation_id": 1, "rating": "up"}
    assert ratings == {1: "up"}


def test_thumbs_down_is_stored(ratings):
    response = client.post("/chat/2/rate", json={"rating": "down"})
    assert response.status_code == 200
    assert ratings == {2: "down"}


def test_rating_twice_keeps_the_latest_value(ratings):
    client.post("/chat/1/rate", json={"rating": "up"})
    client.post("/chat/1/rate", json={"rating": "down"})
    assert ratings == {1: "down"}


@pytest.mark.parametrize("payload", [{"rating": "sideways"}, {"rating": "UP"}, {"rating": ""}, {}])
def test_invalid_rating_value_is_400_and_not_stored(ratings, payload):
    response = client.post("/chat/1/rate", json=payload)
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"
    assert ratings == {}


def test_non_numeric_conversation_id_is_400(ratings):
    response = client.post("/chat/abc/rate", json={"rating": "up"})
    assert response.status_code == 400
    assert ratings == {}


def test_negative_or_zero_id_is_400_or_404_and_not_stored(ratings):
    response = client.post("/chat/-1/rate", json={"rating": "up"})
    assert response.status_code == 400
    response = client.post("/chat/0/rate", json={"rating": "up"})
    assert response.status_code == 404
    assert ratings == {}


def test_unknown_conversation_id_is_404_json(ratings):
    response = client.post("/chat/999/rate", json={"rating": "up"})
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert ratings == {}


def test_id_beyond_bigint_range_is_404(ratings):
    response = client.post(f"/chat/{2**63}/rate", json={"rating": "up"})
    assert response.status_code == 404


def test_missing_database_returns_503(monkeypatch):
    monkeypatch.setattr(chat_module, "engine", None)
    response = client.post("/chat/1/rate", json={"rating": "up"})
    assert response.status_code == 503


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeConn:
    def __init__(self, row):
        self._row = row
        self.params = None

    def execute(self, statement, params):
        self.params = params
        return _FakeResult(self._row)


def test_repository_update_reports_found_and_missing_rows():
    assert update_rating(_FakeConn(row=(1,)), 1, "up") is True
    assert update_rating(_FakeConn(row=None), 999, "up") is False


def test_repository_update_passes_id_and_rating_as_parameters():
    conn = _FakeConn(row=(1,))
    update_rating(conn, 1, "down")
    assert conn.params == {"id": 1, "rating": "down"}
