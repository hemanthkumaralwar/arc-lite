from app.faq_index import FaqDoc, Ranked
from app.verdict import decide


def entry(entry_id: int, category: str) -> FaqDoc:
    return FaqDoc(
        id=entry_id,
        category=category,
        keywords=("kw",),
        canonical_answer=f"Answer {entry_id}",
    )


def ranked(*pairs) -> list[Ranked]:
    """pairs of (entry_id, category, score), already sorted best first."""
    return [Ranked(entry=entry(i, c), score=s) for i, c, s in pairs]


# ---- Refused ----

def test_empty_ranking_is_refused():
    d = decide([])
    assert d.verdict == "Refused"
    assert d.entry is None
    assert d.category is None


def test_score_below_0_10_is_refused():
    d = decide(ranked((1, "courses", 0.09)))
    assert d.verdict == "Refused"
    assert d.entry is None
    assert d.category is None


# ---- Boundary: 0.10 is NOT refused (rule is strictly below 0.10) ----

def test_score_exactly_0_10_is_not_refused():
    d = decide(ranked((1, "courses", 0.10)))
    assert d.verdict == "Unclear"


# ---- Unclear: between 0.10 and 0.30 ----

def test_score_between_thresholds_is_unclear_with_best_guess_category():
    d = decide(ranked((1, "jobs", 0.20)))
    assert d.verdict == "Unclear"
    assert d.entry is None
    assert d.category == "jobs"


def test_score_just_below_0_30_is_unclear():
    d = decide(ranked((1, "jobs", 0.29)))
    assert d.verdict == "Unclear"


# ---- Answered ----

def test_strong_unambiguous_match_is_answered():
    d = decide(ranked((7, "certificates", 0.60), (2, "courses", 0.20)))
    assert d.verdict == "Answered"
    assert d.entry.id == 7
    assert d.category == "certificates"


def test_score_exactly_0_30_with_clear_margin_is_answered():
    d = decide(ranked((1, "account", 0.30)))
    assert d.verdict == "Answered"


def test_margin_exactly_0_05_is_answered():
    # 0.35 - 0.30 is 0.04999... in floating point; rounding keeps it on the 0.05 boundary.
    d = decide(ranked((1, "courses", 0.35), (2, "jobs", 0.30)))
    assert d.verdict == "Answered"


# ---- Unclear: ambiguous between categories ----

def test_strong_score_but_close_to_other_category_is_unclear():
    d = decide(ranked((1, "courses", 0.50), (2, "jobs", 0.47)))
    assert d.verdict == "Unclear"
    assert d.entry is None


def test_close_to_other_category_is_unclear_even_if_same_category_is_second():
    # The second entry is in the SAME category, so it does not count against s1.
    # Here the other-category score is 0.47, so the margin is too small.
    d = decide(ranked((1, "courses", 0.50), (2, "courses", 0.49), (3, "jobs", 0.47)))
    assert d.verdict == "Unclear"


def test_same_category_runner_up_does_not_block_answer():
    # s2 comes from a different category only. Here it is 0.10, so the margin is 0.40.
    d = decide(ranked((1, "courses", 0.50), (2, "courses", 0.49), (3, "jobs", 0.10)))
    assert d.verdict == "Answered"
    assert d.entry.id == 1


def test_tie_between_categories_is_unclear():
    d = decide(ranked((1, "courses", 0.50), (2, "jobs", 0.50)))
    assert d.verdict == "Unclear"


# ---- Never returns an answer unless Answered ----

def test_only_answered_carries_an_entry():
    cases = [
        ranked(),
        ranked((1, "courses", 0.05)),
        ranked((1, "courses", 0.20)),
        ranked((1, "courses", 0.50), (2, "jobs", 0.48)),
    ]
    for case in cases:
        d = decide(case)
        if d.verdict != "Answered":
            assert d.entry is None
