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


def insert_conversation(conn, row: dict) -> int:
    return conn.execute(INSERT_CONVERSATION, row).scalar_one()


def update_rating(conn, conversation_id: int, rating: str) -> bool:
    """Set the rating (last write wins). Returns False if no such conversation exists."""
    row = conn.execute(UPDATE_RATING, {"id": conversation_id, "rating": rating}).first()
    return row is not None
