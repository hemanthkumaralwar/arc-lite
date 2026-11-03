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


MAX_KEYWORDS = 30
MAX_KEYWORD_LENGTH = 50
MAX_ANSWER_LENGTH = 2000


class FaqInput(BaseModel):
    category: Literal["courses", "certificates", "jobs", "account"]
    keywords: list[str]
    canonical_answer: str

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in value:
            keyword = " ".join(raw.split()).lower()
            if keyword and keyword not in cleaned:
                cleaned.append(keyword)
        if not cleaned:
            raise ValueError("Add at least one keyword.")
        if len(cleaned) > MAX_KEYWORDS:
            raise ValueError(f"Use at most {MAX_KEYWORDS} keywords.")
        if any(len(k) > MAX_KEYWORD_LENGTH for k in cleaned):
            raise ValueError(f"Each keyword must be {MAX_KEYWORD_LENGTH} characters or fewer.")
        return cleaned

    @field_validator("canonical_answer")
    @classmethod
    def clean_answer(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Answer must not be empty.")
        if len(cleaned) > MAX_ANSWER_LENGTH:
            raise ValueError(f"Answer must be {MAX_ANSWER_LENGTH} characters or fewer.")
        return cleaned


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
