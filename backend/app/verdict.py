"""Deterministic verdict rules applied to the ranked FAQ list.

Terms:
  s1  best cosine score among all entries
  s2  best cosine score among entries in a different category from the s1 entry

Rules, applied in order:
  1. s1 below 0.10                       -> Refused   (nothing relevant)
  2. s1 at least 0.30 and s1 - s2 >= 0.05 -> Answered  (confident, unambiguous)
  3. everything else                     -> Unclear   (ask the student to rephrase)

Only Answered returns a canonical answer. Unclear and Refused never return an answer.
"""
from dataclasses import dataclass

from .faq_index import FaqDoc, Ranked

REFUSE_BELOW = 0.10
ANSWER_AT_OR_ABOVE = 0.30
MIN_MARGIN = 0.05


@dataclass(frozen=True)
class Decision:
    verdict: str  # "Answered", "Refused", or "Unclear"
    score: float  # s1
    second_score: float  # s2
    entry: FaqDoc | None  # set only when Answered
    category: str | None  # Answered: matched category. Unclear: best-guess category. Refused: None.


def decide(ranked: list[Ranked]) -> Decision:
    if not ranked:
        return Decision("Refused", 0.0, 0.0, None, None)

    top = ranked[0]
    s1 = top.score
    s2 = next(
        (item.score for item in ranked if item.entry.category != top.entry.category),
        0.0,
    )
    # Round the difference so float noise (e.g. 0.35 - 0.30) cannot flip the 0.05 boundary.
    margin = round(s1 - s2, 9)

    if s1 < REFUSE_BELOW:
        return Decision("Refused", s1, s2, None, None)

    if s1 >= ANSWER_AT_OR_ABOVE and margin >= MIN_MARGIN:
        return Decision("Answered", s1, s2, top.entry, top.entry.category)

    return Decision("Unclear", s1, s2, None, top.entry.category)
