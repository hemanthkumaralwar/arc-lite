from app.chat_service import CLARIFY_TEXT, REFUSAL_TEXT, answer_question
from app.faq_index import FaqDoc, FaqIndex, Ranked


class FakeIndex:
    """Returns a fixed ranking so each verdict can be tested deterministically."""

    def __init__(self, ranked):
        self._ranked = ranked

    def rank(self, query):
        return self._ranked


def entry(entry_id, category, answer="Answer text."):
    return FaqDoc(id=entry_id, category=category, keywords=("kw",), canonical_answer=answer)


def recorder():
    rows = []

    def record(row):
        rows.append(row)
        return len(rows)

    return rows, record


def test_answered_returns_canonical_answer_verbatim_and_records_match():
    answer = "Certificates are issued after you complete the course requirements."
    best = entry(1, "certificates", answer)
    index = FakeIndex([Ranked(best, 0.60), Ranked(entry(2, "courses"), 0.10)])
    rows, record = recorder()

    result = answer_question("get certificate", index, record)

    assert result.verdict == "Answered"
    assert result.category == "certificates"
    assert result.answer_type == "faq"
    assert result.answer == answer
    assert rows[0]["matched_faq_id"] == 1
    assert rows[0]["verdict"] == "Answered"


def test_unclear_returns_fixed_prompt_and_no_faq_id():
    index = FakeIndex([Ranked(entry(3, "jobs", "Job text."), 0.20)])
    rows, record = recorder()

    result = answer_question("something vague", index, record)

    assert result.verdict == "Unclear"
    assert result.answer_type == "clarify"
    assert result.answer == CLARIFY_TEXT
    assert result.category == "jobs"  # best-guess category is kept for analytics
    assert rows[0]["matched_faq_id"] is None
    assert "Job text." not in result.answer


def test_refused_returns_fixed_message_and_no_category():
    rows, record = recorder()

    result = answer_question("quantum physics", FakeIndex([]), record)

    assert result.verdict == "Refused"
    assert result.answer_type == "refusal"
    assert result.answer == REFUSAL_TEXT
    assert result.category is None
    assert rows[0]["category"] is None
    assert rows[0]["matched_faq_id"] is None


def test_response_time_is_a_non_negative_integer_and_is_recorded():
    rows, record = recorder()

    result = answer_question("anything", FakeIndex([]), record)

    assert isinstance(result.response_ms, int)
    assert result.response_ms >= 0
    assert rows[0]["response_ms"] == result.response_ms


def test_record_receives_every_column_the_table_needs():
    rows, record = recorder()
    answer_question("anything", FakeIndex([]), record)
    assert set(rows[0]) == {
        "question",
        "answer",
        "category",
        "matched_faq_id",
        "verdict",
        "score",
        "response_ms",
    }


def test_real_index_answers_exact_canonical_text():
    # Asking with an entry's own canonical answer should match that entry strongly.
    answer = "To start a course, open it from your dashboard."
    index = FaqIndex()
    index.build(
        [
            FaqDoc(1, "courses", ("start", "enroll", "course"), answer),
            FaqDoc(2, "jobs", ("job", "apply", "vacancy"), "Job listings are shown in the jobs section."),
            FaqDoc(3, "account", ("password", "reset"), "Use the password reset option on the sign-in page."),
        ]
    )
    rows, record = recorder()

    result = answer_question(answer, index, record)

    assert result.verdict == "Answered"
    assert result.answer == answer
    assert rows[0]["matched_faq_id"] == 1
