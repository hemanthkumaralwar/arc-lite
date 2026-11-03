"""Staff-only FAQ management. Every route requires a valid staff token.

After each committed write the in-memory search index is rebuilt from the database,
so a new or edited entry is matched by /chat immediately, without a restart.
"""
import threading

from fastapi import APIRouter, Depends, HTTPException

from .auth import require_staff
from .db import engine
from .faq_index import faq_index, load_entries
from .repository import delete_faq_entry, insert_faq_entry, list_faq_entries, update_faq_entry
from .schemas import FaqInput

router = APIRouter()

MAX_ENTRY_ID = 2**63 - 1

# Serializes writes, so an older index snapshot can never finish building after a newer one.
_faq_write_lock = threading.Lock()


def _require_database() -> None:
    if engine is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")


def _serialize(row) -> dict:
    return {
        "id": row.id,
        "category": row.category,
        "keywords": list(row.keywords),
        "canonical_answer": row.canonical_answer,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _refresh_index() -> None:
    with engine.connect() as conn:
        faq_index.refit(load_entries(conn))


@router.get("/admin/faq")
def list_faq(_staff: dict = Depends(require_staff)) -> dict:
    _require_database()
    with engine.connect() as conn:
        rows = list_faq_entries(conn)
    return {"entries": [_serialize(row) for row in rows]}


@router.post("/admin/faq", status_code=201)
def create_faq(body: FaqInput, _staff: dict = Depends(require_staff)) -> dict:
    _require_database()
    with _faq_write_lock:
        with engine.begin() as conn:
            row = insert_faq_entry(conn, body.model_dump())
        _refresh_index()
    return _serialize(row)


@router.put("/admin/faq/{entry_id}")
def update_faq(entry_id: int, body: FaqInput, _staff: dict = Depends(require_staff)) -> dict:
    _require_database()
    if entry_id < 1 or entry_id > MAX_ENTRY_ID:
        raise HTTPException(status_code=404, detail="FAQ entry not found.")

    with _faq_write_lock:
        with engine.begin() as conn:
            row = update_faq_entry(conn, entry_id, body.model_dump())
        if row is None:
            raise HTTPException(status_code=404, detail="FAQ entry not found.")
        _refresh_index()
    return _serialize(row)


@router.delete("/admin/faq/{entry_id}")
def delete_faq(entry_id: int, _staff: dict = Depends(require_staff)) -> dict:
    _require_database()
    if entry_id < 1 or entry_id > MAX_ENTRY_ID:
        raise HTTPException(status_code=404, detail="FAQ entry not found.")

    with _faq_write_lock:
        with engine.begin() as conn:
            deleted = delete_faq_entry(conn, entry_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="FAQ entry not found.")
        _refresh_index()
    return {"id": entry_id, "deleted": True}
