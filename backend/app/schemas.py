from typing import Literal

from pydantic import BaseModel, field_validator

MAX_QUESTION_LENGTH = 500


class RatingRequest(BaseModel):
    rating: Literal["up", "down"]


class ChatRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question must not be empty.")
        if len(cleaned) > MAX_QUESTION_LENGTH:
            raise ValueError(f"Question must be {MAX_QUESTION_LENGTH} characters or fewer.")
        return cleaned
