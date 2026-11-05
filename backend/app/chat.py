from fastapi import APIRouter, HTTPException

from .chat_service import answer_question
from .config import settings
from .db import engine
from .faq_index import faq_index
from .llm_assist import rewrite_query
from .repository import insert_conversation, update_rating
from .schemas import ChatRequest, RatingRequest

# PostgreSQL BIGINT upper limit. Larger ids cannot exist, so they are reported as not found.
MAX_CONVERSATION_ID = 2**63 - 1

router = APIRouter()


@router.post("/chat")
def chat(body: ChatRequest) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")

    with engine.begin() as conn:
        result = answer_question(
            body.question,
            faq_index,
            lambda row: insert_conversation(conn, row),
            rewrite=rewrite_query if (settings.enable_llm_assist and settings.gemini_api_key) else None,
        )

    return {
        "conversation_id": result.conversation_id,
        "verdict": result.verdict,
        "category": result.category,
        "answer_type": result.answer_type,
        "answer": result.answer,
        "response_ms": result.response_ms,
    }


@router.post("/chat/{conversation_id}/rate")
def rate(conversation_id: str, body: RatingRequest) -> dict:
    if not (conversation_id.isascii() and conversation_id.isdigit()):
        raise HTTPException(status_code=400, detail="Conversation id must be a whole number.")

    parsed_id = int(conversation_id)
    if parsed_id < 1 or parsed_id > MAX_CONVERSATION_ID:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    if engine is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")

    with engine.begin() as conn:
        found = update_rating(conn, parsed_id, body.rating)

    if not found:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return {"conversation_id": parsed_id, "rating": body.rating}
