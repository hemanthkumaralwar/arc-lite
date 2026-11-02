from app.faq_index import FaqDoc, FaqIndex


def sample_entries() -> list[FaqDoc]:
    return [
        FaqDoc(
            id=1,
            category="certificates",
            keywords=("certificate", "get", "download"),
            canonical_answer="Certificates are issued after you complete the course requirements.",
        ),
        FaqDoc(
            id=2,
            category="courses",
            keywords=("start", "enroll", "course"),
            canonical_answer="To start a course, open it from your dashboard.",
        ),
        FaqDoc(
            id=3,
            category="jobs",
            keywords=("job", "apply", "vacancy"),
            canonical_answer="Job listings are shown in the jobs section.",
        ),
        FaqDoc(
            id=4,
            category="account",
            keywords=("password", "reset", "forgot"),
            canonical_answer="Use the password reset option on the sign-in page.",
        ),
    ]


def build_index(entries=None) -> FaqIndex:
    index = FaqIndex()
    index.build(sample_entries() if entries is None else entries)
    return index


def test_certificate_question_ranks_certificate_entry_first():
    index = build_index()
    ranked = index.rank("How do I get my certificate?")
    assert ranked[0].entry.id == 1
    assert ranked[0].entry.category == "certificates"


def test_password_question_ranks_account_entry_first():
    index = build_index()
    assert index.rank("I forgot my password")[0].entry.id == 4


def test_phrase_match_uses_word_pairs():
    index = build_index()
    assert index.rank("how do I start a course")[0].entry.id == 2


def test_query_is_normalized_before_matching():
    index = build_index()
    assert index.rank("CERTIFICATES!!!")[0].entry.id == 1


def test_scores_are_cosine_values_between_0_and_1():
    index = build_index()
    for item in index.rank("get certificate download"):
        assert 0.0 <= item.score <= 1.0 + 1e-9


def test_ranking_returns_every_entry_sorted_best_first():
    index = build_index()
    ranked = index.rank("get certificate")
    assert len(ranked) == 4
    scores = [item.score for item in ranked]
    assert scores == sorted(scores, reverse=True)


def test_query_with_no_known_words_returns_empty_list():
    index = build_index()
    assert index.rank("quantum physics") == []


def test_empty_or_stopword_only_query_returns_empty_list():
    index = build_index()
    assert index.rank("") == []
    assert index.rank("the and of") == []


def test_empty_index_returns_empty_list():
    index = FaqIndex()
    assert index.rank("get certificate") == []
    assert index.size() == 0


def test_refit_makes_new_entry_matchable_without_restart():
    index = build_index()
    assert index.rank("transcript request") == []

    entries = sample_entries() + [
        FaqDoc(
            id=5,
            category="certificates",
            keywords=("transcript", "request"),
            canonical_answer="To request a transcript, contact the support team.",
        )
    ]
    index.refit(entries)

    assert index.size() == 5
    assert index.rank("transcript request")[0].entry.id == 5


def test_ranking_is_deterministic():
    index = build_index()
    first = [(r.entry.id, r.score) for r in index.rank("get certificate start course")]
    second = [(r.entry.id, r.score) for r in index.rank("get certificate start course")]
    assert first == second
