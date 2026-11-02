from typing import Literal

from pydantic import BaseModel, field_validator

MAX_QUESTION_LENGTH = 500


class RatingRequest(BaseModel):
    rating: Literal["up", "down"]


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned or "@" not in cleaned or len(cleaned) > 254:
            raise ValueError("Enter a valid email address.")
        return cleaned

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        if not value:
            raise ValueError("Password must not be empty.")
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password is too long.")
        return value


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
