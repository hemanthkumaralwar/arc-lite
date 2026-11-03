from sqlalchemy import text

INSERT_CONVERSATION = text(
    """
    INSERT INTO conversations
        (question, answer, category, matched_faq_id, verdict, score, response_ms, llm_used)
    VALUES
        (:question, :answer, :category, :matched_faq_id, :verdict, :score, :response_ms, FALSE)
    RETURNING id
    """
)


UPDATE_RATING = text(
    """
    UPDATE conversations
    SET rating = :rating
    WHERE id = :id
    RETURNING id
    """
)


SELECT_STAFF_BY_EMAIL = text(
    """
    SELECT id, email, password_hash
    FROM staff
    WHERE email = :email
    """
)


def get_staff_by_email(conn, email: str):
    """Return the staff row (id, email, password_hash) or None."""
    return conn.execute(SELECT_STAFF_BY_EMAIL, {"email": email}).first()


LIST_FAQ = text(
    """
    SELECT id, category, keywords, canonical_answer, created_at, updated_at
    FROM faq_entries
    ORDER BY id
    """
)

INSERT_FAQ = text(
    """
    INSERT INTO faq_entries (category, keywords, canonical_answer)
    VALUES (:category, :keywords, :canonical_answer)
    RETURNING id, category, keywords, canonical_answer, created_at, updated_at
    """
)

UPDATE_FAQ = text(
    """
    UPDATE faq_entries
    SET category = :category,
        keywords = :keywords,
        canonical_answer = :canonical_answer,
        updated_at = now()
    WHERE id = :id
    RETURNING id, category, keywords, canonical_answer, created_at, updated_at
    """
)


def list_faq_entries(conn):
    return conn.execute(LIST_FAQ).all()


def insert_faq_entry(conn, data: dict):
    return conn.execute(INSERT_FAQ, data).one()


def update_faq_entry(conn, entry_id: int, data: dict):
    """Return the updated row, or None if no entry has that id."""
    return conn.execute(UPDATE_FAQ, {**data, "id": entry_id}).first()


DELETE_FAQ = text(
    """
    DELETE FROM faq_entries
    WHERE id = :id
    RETURNING id
    """
)


def delete_faq_entry(conn, entry_id: int) -> bool:
    """Return True if an entry was deleted, False if no entry has that id."""
    return conn.execute(DELETE_FAQ, {"id": entry_id}).first() is not None


def insert_conversation(conn, row: dict) -> int:
    return conn.execute(INSERT_CONVERSATION, row).scalar_one()


def update_rating(conn, conversation_id: int, rating: str) -> bool:
    """Set the rating (last write wins). Returns False if no such conversation exists."""
    row = conn.execute(UPDATE_RATING, {"id": conversation_id, "rating": rating}).first()
    return row is not None
