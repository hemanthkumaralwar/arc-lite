"""The /chat pipeline: rank the question, apply verdict rules, build the reply, record it.

Only an Answered verdict returns FAQ text. Unclear and Refused return fixed messages.
The database write is passed in as `record`, so this module can be tested without a database.
"""
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from .faq_index import FaqIndex
from .verdict import Decision, decide

REFUSAL_TEXT = (
    "I can't answer that from the Arc Lite FAQ. "
    "Please contact the ArchintX support team for help."
)
CLARIFY_TEXT = (
    "I'm not sure I understood that. Could you rephrase your question using words about "
    "courses, certificates, jobs, or your account?"
)


@dataclass(frozen=True)
class ChatResult:
    conversation_id: int
    verdict: str
    category: str | None
    answer_type: str  # "faq", "clarify", or "refusal"
    answer: str
    response_ms: int


def reply_for(decision: Decision) -> tuple[str, str]:
    if decision.verdict == "Answered":
        return "faq", decision.entry.canonical_answer
    if decision.verdict == "Unclear":
        return "clarify", CLARIFY_TEXT
    return "refusal", REFUSAL_TEXT


RecordFn = Callable[[dict], int]
RewriteFn = Callable[[str], str | None]


def answer_question(
    question: str,
    index: FaqIndex,
    record: RecordFn,
    rewrite: RewriteFn | None = None,
) -> ChatResult:
    started = perf_counter()
    ranked = index.rank(question)
    decision = decide(ranked)
    llm_used = False
    llm_status = "not_called"

    # The LLM can only upgrade a reply. If the original question was already Answered,
    # or the rewrite does not produce an Answered verdict, the original result stands.
    if decision.verdict != "Answered" and rewrite is not None:
        rewritten = rewrite(question)
        if not rewritten:
            llm_status = "no_rewrite"
        else:
            alternative = decide(index.rank(rewritten))
            if alternative.verdict == "Answered":
                decision = alternative
                llm_used = True
                llm_status = "used"
            else:
                llm_status = "not_better"
    answer_type, reply_text = reply_for(decision)
    # Timing covers matching and reply building. The database write happens after it,
    # so storage latency is not counted as response time.
    response_ms = max(0, round((perf_counter() - started) * 1000))

    conversation_id = record(
        {
            "question": question,
            "answer": reply_text,
            "category": decision.category,
            "matched_faq_id": decision.entry.id if decision.entry is not None else None,
            "verdict": decision.verdict,
            "score": decision.score,
            "response_ms": response_ms,
            "llm_used": llm_used,
            "llm_status": llm_status,
        }
    )

    return ChatResult(
        conversation_id=conversation_id,
        verdict=decision.verdict,
        category=decision.category,
        answer_type=answer_type,
        answer=reply_text,
        response_ms=response_ms,
    )
