"""Live dashboard statistics, computed from the conversations table on every request.

Nothing is cached or hardcoded. Percentages and averages are calculated here from raw
counts, so the dashboard shows exactly what the database holds.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from .auth import require_staff
from .db import engine

CATEGORIES = ("courses", "certificates", "jobs", "account")
NONE_BUCKET = "none"  # Refused conversations have no category

# All three queries run in one REPEATABLE READ transaction, so the totals and the
# per-category breakdown describe the same snapshot even while chats are being written.
SET_ISOLATION_SQL = text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

BY_CATEGORY_SQL = text(
    """
    SELECT COALESCE(category, 'none') AS bucket,
           COUNT(*) AS total,
           COUNT(*) FILTER (WHERE verdict = 'Answered') AS answered,
           COUNT(*) FILTER (WHERE verdict = 'Refused') AS refused,
           COUNT(*) FILTER (WHERE verdict = 'Unclear') AS unclear,
           AVG(response_ms) AS avg_response_ms
    FROM conversations
    GROUP BY 1
    """
)

TOTALS_SQL = text(
    """
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE verdict = 'Answered') AS answered,
           COUNT(*) FILTER (WHERE verdict = 'Refused') AS refused,
           COUNT(*) FILTER (WHERE verdict = 'Unclear') AS unclear,
           COUNT(*) FILTER (WHERE rating = 'up') AS rated_up,
           COUNT(*) FILTER (WHERE rating = 'down') AS rated_down,
           AVG(response_ms) AS avg_response_ms
    FROM conversations
    """
)

ANSWERED_RATED_DOWN_SQL = text(
    """
    SELECT id, question, answer, category, matched_faq_id, response_ms, created_at
    FROM conversations
    WHERE verdict = 'Answered' AND rating = 'down'
    ORDER BY created_at DESC, id DESC
    """
)


def _pct(part: int, total: int) -> float:
    return round(100.0 * part / total, 1) if total else 0.0


def _round_or_none(value) -> float | None:
    return None if value is None else round(float(value), 1)


def build_by_category(bucket_rows) -> list[dict]:
    by_bucket = {row.bucket: row for row in bucket_rows}
    result = []
    for name in (*CATEGORIES, NONE_BUCKET):
        row = by_bucket.get(name)
        total = int(row.total) if row else 0
        answered = int(row.answered) if row else 0
        refused = int(row.refused) if row else 0
        unclear = int(row.unclear) if row else 0
        result.append(
            {
                "category": name,
                "total": total,
                "answered": answered,
                "refused": refused,
                "unclear": unclear,
                "answered_pct": _pct(answered, total),
                "refused_pct": _pct(refused, total),
                "unclear_pct": _pct(unclear, total),
                "avg_response_ms": _round_or_none(row.avg_response_ms) if row else None,
            }
        )
    return result


def _serialize_down(row) -> dict:
    return {
        "id": row.id,
        "question": row.question,
        "answer": row.answer,
        "category": row.category,
        "matched_faq_id": row.matched_faq_id,
        "response_ms": row.response_ms,
        "created_at": row.created_at.isoformat(),
    }


def build_stats_payload(bucket_rows, totals_row, down_rows, generated_at: datetime) -> dict:
    total = int(totals_row.total)
    answered = int(totals_row.answered)
    refused = int(totals_row.refused)
    unclear = int(totals_row.unclear)
    return {
        "generated_at": generated_at.isoformat(),
        "totals": {
            "conversations": total,
            "answered": answered,
            "refused": refused,
            "unclear": unclear,
            "answered_pct": _pct(answered, total),
            "refused_pct": _pct(refused, total),
            "unclear_pct": _pct(unclear, total),
            "rated_up": int(totals_row.rated_up),
            "rated_down": int(totals_row.rated_down),
            "avg_response_ms": _round_or_none(totals_row.avg_response_ms),
        },
        "by_category": build_by_category(bucket_rows),
        "answered_rated_down_count": len(down_rows),
        "answered_rated_down": [_serialize_down(row) for row in down_rows],
    }


def fetch_raw(conn):
    conn.execute(SET_ISOLATION_SQL)
    bucket_rows = conn.execute(BY_CATEGORY_SQL).all()
    totals_row = conn.execute(TOTALS_SQL).one()
    down_rows = conn.execute(ANSWERED_RATED_DOWN_SQL).all()
    return bucket_rows, totals_row, down_rows


router = APIRouter()


@router.get("/admin/stats")
def stats(_staff: dict = Depends(require_staff)) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    with engine.connect() as conn:
        bucket_rows, totals_row, down_rows = fetch_raw(conn)
    return build_stats_payload(bucket_rows, totals_row, down_rows, datetime.now(timezone.utc))
