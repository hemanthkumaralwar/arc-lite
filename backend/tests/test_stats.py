from collections import namedtuple
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app import config
from app import stats as stats_module
from app.main import app
from app.stats import build_by_category, build_stats_payload

client = TestClient(app)  # no `with` block, so the startup database load does not run

SECRET = "test-secret-that-is-at-least-thirty-two-characters-long"
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)

Bucket = namedtuple("Bucket", "bucket total answered refused unclear avg_response_ms")
Totals = namedtuple("Totals", "total answered refused unclear rated_up rated_down avg_response_ms")
Down = namedtuple("Down", "id question answer category matched_faq_id response_ms created_at")


# A hand-countable scenario of 10 conversations:
#   courses:      4 chats, 2 Answered + 2 Unclear, average 300 ms
#   certificates: 3 chats, 3 Answered, average 100 ms
#   none:         3 chats, 3 Refused (no category), average 50 ms
# Ratings: 6 up, 2 down. Overall average = (4*300 + 3*100 + 3*50) / 10 = 165 ms.
HAND_COUNT_BUCKETS = [
    Bucket("courses", 4, 2, 0, 2, 300),
    Bucket("certificates", 3, 3, 0, 0, 100),
    Bucket("none", 3, 0, 3, 0, 50),
]
HAND_COUNT_TOTALS = Totals(10, 5, 3, 2, 6, 2, 165)


def by_name(payload_list):
    return {item["category"]: item for item in payload_list}


def test_hand_counted_totals_match():
    payload = build_stats_payload(HAND_COUNT_BUCKETS, HAND_COUNT_TOTALS, [], NOW)
    totals = payload["totals"]
    assert totals["conversations"] == 10
    assert totals["answered"] == 5
    assert totals["refused"] == 3
    assert totals["unclear"] == 2
    assert totals["answered_pct"] == 50.0
    assert totals["refused_pct"] == 30.0
    assert totals["unclear_pct"] == 20.0
    assert totals["rated_up"] == 6
    assert totals["rated_down"] == 2
    assert totals["avg_response_ms"] == 165.0


def test_hand_counted_category_percentages_and_averages_match():
    categories = by_name(build_by_category(HAND_COUNT_BUCKETS))

    courses = categories["courses"]
    assert courses["total"] == 4
    assert courses["answered_pct"] == 50.0
    assert courses["unclear_pct"] == 50.0
    assert courses["refused_pct"] == 0.0
    assert courses["avg_response_ms"] == 300.0

    certificates = categories["certificates"]
    assert certificates["answered_pct"] == 100.0
    assert certificates["avg_response_ms"] == 100.0

    none_bucket = categories["none"]
    assert none_bucket["refused_pct"] == 100.0
    assert none_bucket["avg_response_ms"] == 50.0


def test_every_category_appears_in_order_even_with_no_conversations():
    result = build_by_category(HAND_COUNT_BUCKETS)
    assert [item["category"] for item in result] == ["courses", "certificates", "jobs", "account", "none"]

    jobs = by_name(result)["jobs"]
    assert jobs["total"] == 0
    assert jobs["answered_pct"] == 0.0
    assert jobs["avg_response_ms"] is None


def test_percentages_are_rounded_to_one_decimal_place():
    buckets = [Bucket("jobs", 3, 1, 0, 2, 10)]
    jobs = by_name(build_by_category(buckets))["jobs"]
    assert jobs["answered_pct"] == 33.3
    assert jobs["unclear_pct"] == 66.7


def test_answered_rated_down_list_is_reported_with_count():
    down_rows = [
        Down(9, "how do I pause", "Your progress is saved.", "courses", 2, 4, NOW - timedelta(hours=1)),
        Down(4, "certificate name", "Contact support.", "certificates", 7, 3, NOW - timedelta(days=1)),
    ]
    payload = build_stats_payload(HAND_COUNT_BUCKETS, HAND_COUNT_TOTALS, down_rows, NOW)
    assert payload["answered_rated_down_count"] == 2
    assert [item["id"] for item in payload["answered_rated_down"]] == [9, 4]
    assert payload["answered_rated_down"][0]["created_at"] == (NOW - timedelta(hours=1)).isoformat()


def test_empty_database_gives_zeros_and_null_averages():
    empty_totals = Totals(0, 0, 0, 0, 0, 0, None)
    payload = build_stats_payload([], empty_totals, [], NOW)
    assert payload["totals"]["conversations"] == 0
    assert payload["totals"]["answered_pct"] == 0.0
    assert payload["totals"]["avg_response_ms"] is None
    assert payload["answered_rated_down"] == []
    assert payload["answered_rated_down_count"] == 0


# ---- route ----

class _Connection:
    def __enter__(self):
        return object()

    def __exit__(self, *exc):
        return False


class FakeEngine:
    def connect(self):
        return _Connection()


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
def stats_db(monkeypatch):
    monkeypatch.setattr(config.settings, "jwt_secret", SECRET)
    monkeypatch.setattr(stats_module, "engine", FakeEngine())
    monkeypatch.setattr(
        stats_module,
        "fetch_raw",
        lambda conn: (HAND_COUNT_BUCKETS, HAND_COUNT_TOTALS, []),
    )


def test_stats_without_token_is_401(stats_db):
    assert client.get("/admin/stats").status_code == 401


def test_stats_with_non_staff_token_is_403(stats_db):
    assert client.get("/admin/stats", headers=staff_headers(role="customer")).status_code == 403


def test_stats_returns_the_full_payload_for_staff(stats_db):
    response = client.get("/admin/stats", headers=staff_headers())
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "generated_at",
        "totals",
        "by_category",
        "answered_rated_down_count",
        "answered_rated_down",
    }
    assert body["totals"]["conversations"] == 10
    assert len(body["by_category"]) == 5


def test_stats_without_database_returns_503(monkeypatch, stats_db):
    monkeypatch.setattr(stats_module, "engine", None)
    assert client.get("/admin/stats", headers=staff_headers()).status_code == 503
