"""Optional LLM assist: rewrites a student's question into a short English search phrase.

Safety rules, all enforced here or in chat_service.py:
  - The LLM output is only used as search text. It is never shown to students.
  - Replies still come from FAQ canonical answers, verbatim.
  - The rewrite is used only when the original question did not already give Answered,
    and only if the rewrite gives Answered. It can upgrade a reply, never downgrade one.
  - Output must be short and plain (see validate_rewrite). Anything else is discarded.
  - Any error, timeout, or invalid output means no rewrite, and the original verdict stands.
  - Off unless ENABLE_LLM_ASSIST=true and GEMINI_API_KEY is set.
"""
import re

import httpx

from .config import settings

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT_SECONDS = 4.0
MAX_REWRITE_WORDS = 12
MAX_REWRITE_CHARS = 120
MAX_OUTPUT_TOKENS = 64

# Kept only for scripts/test_gemini.py. Students never see these values.
last_error: str | None = None
last_raw: str | None = None

SYSTEM_PROMPT = (
    "You rewrite a student's question into a short English search phrase of at most 12 words. "
    "Fix spelling mistakes first, for example 'cetificate' means 'certificate' and 'sertificate' "
    "means 'certificate'. Translate to English if needed. Keep only the words that matter, "
    "about ArchintX courses, certificates, jobs, or accounts. "
    "Output only the phrase, on one line, with no quotes, no punctuation other than commas, "
    "and no explanation. Do not answer the question. Do not add facts."
)

_PLAIN_TEXT = re.compile(r"[A-Za-z0-9 ,'\-]+")


def validate_rewrite(text) -> str | None:
    """Return the cleaned phrase, or None if the output is not a plain short phrase."""
    if not isinstance(text, str):
        return None
    if "\n" in text or "\r" in text:
        return None
    cleaned = " ".join(text.split())
    if not cleaned:
        return None
    if len(cleaned) > MAX_REWRITE_CHARS:
        return None
    if len(cleaned.split()) > MAX_REWRITE_WORDS:
        return None
    if not _PLAIN_TEXT.fullmatch(cleaned):
        return None
    return cleaned


def rewrite_query(question: str) -> str | None:
    """Ask the LLM for a search phrase. Returns None on any problem."""
    global last_error, last_raw
    last_error = None
    last_raw = None
    if not settings.enable_llm_assist or not settings.gemini_api_key:
        return None

    url = GEMINI_URL.format(model=settings.gemini_model)
    try:
        response = httpx.post(
            url,
            headers={
                "x-goog-api-key": settings.gemini_api_key,
                "content-type": "application/json",
            },
            json={
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": question}]}],
                "generationConfig": {
                    "maxOutputTokens": MAX_OUTPUT_TOKENS,
                    "temperature": 0,
                    # Gemini 2.5 models can spend output tokens on hidden reasoning.
                    # A budget of 0 keeps the whole reply for the short phrase.
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        # Silent for students: they still get the normal, deterministic answer.
        if isinstance(exc, httpx.HTTPStatusError):
            last_error = f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        else:
            last_error = f"{type(exc).__name__}: {exc}"
        return None

    last_raw = text
    return validate_rewrite(text)
