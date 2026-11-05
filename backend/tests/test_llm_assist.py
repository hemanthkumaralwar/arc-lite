import httpx
import pytest

from app import config
from app import llm_assist
from app.chat_service import CLARIFY_TEXT, REFUSAL_TEXT, answer_question
from app.faq_index import FaqDoc, Ranked


# ---- validate_rewrite: only short, plain phrases pass ----

@pytest.mark.parametrize(
    "text, expected",
    [
        ("get certificate", "get certificate"),
        ("  reset   password  ", "reset password"),
        ("job application, status", "job application, status"),
        ("student's stipend", "student's stipend"),
        ("end-of-course deadline", "end-of-course deadline"),
    ],
)
def test_plain_short_phrases_are_accepted(text, expected):
    assert llm_assist.validate_rewrite(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        None,
        12,
        "line one\nline two",
        "Here is the phrase: get certificate",  # colon is not allowed
        "<script>alert(1)</script>",  # markup is not allowed
        "x" * 300,
        " ".join(["word"] * 13),  # more than 12 words
        "Yes, you will receive your certificate within 3 days.",  # a sentence with a period
    ],
)
def test_invalid_or_answer_like_output_is_rejected(text):
    assert llm_assist.validate_rewrite(text) is None


# ---- rewrite_query: off by default, and never fails the request ----

def test_no_network_call_when_disabled(monkeypatch):
    monkeypatch.setattr(config.settings, "enable_llm_assist", False)
    monkeypatch.setattr(config.settings, "gemini_api_key", "key")

    def fail(*args, **kwargs):
        raise AssertionError("network must not be called when the flag is off")

    monkeypatch.setattr(llm_assist.httpx, "post", fail)
    assert llm_assist.rewrite_query("wie bekomme ich mein Zertifikat") is None


def test_no_network_call_without_api_key(monkeypatch):
    monkeypatch.setattr(config.settings, "enable_llm_assist", True)
    monkeypatch.setattr(config.settings, "gemini_api_key", "")

    def fail(*args, **kwargs):
        raise AssertionError("network must not be called without a key")

    monkeypatch.setattr(llm_assist.httpx, "post", fail)
    assert llm_assist.rewrite_query("anything") is None


def test_timeout_or_error_returns_none(monkeypatch):
    monkeypatch.setattr(config.settings, "enable_llm_assist", True)
    monkeypatch.setattr(config.settings, "gemini_api_key", "key")

    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(llm_assist.httpx, "post", timeout)
    assert llm_assist.rewrite_query("anything") is None


def test_valid_model_reply_is_returned_after_validation(monkeypatch):
    monkeypatch.setattr(config.settings, "enable_llm_assist", True)
    monkeypatch.setattr(config.settings, "gemini_api_key", "key")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "get certificate"}]}}]}

    monkeypatch.setattr(llm_assist.httpx, "post", lambda *a, **k: FakeResponse())
    assert llm_assist.rewrite_query("wie bekomme ich mein Zertifikat") == "get certificate"


def test_invalid_model_reply_is_discarded(monkeypatch):
    monkeypatch.setattr(config.settings, "enable_llm_assist", True)
    monkeypatch.setattr(config.settings, "gemini_api_key", "key")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "Sure! Here you go:\nget certificate."}]}}]}

    monkeypatch.setattr(llm_assist.httpx, "post", lambda *a, **k: FakeResponse())
    assert llm_assist.rewrite_query("anything") is None


# ---- pipeline rules: the LLM can upgrade, never downgrade, and never writes text ----

class DictIndex:
    """Returns a fixed ranking per query, so each case is deterministic."""

    def __init__(self, rankings):
        self._rankings = rankings

    def rank(self, query):
        return self._rankings.get(query, [])


def entry(entry_id, category, answer):
    return FaqDoc(id=entry_id, category=category, keywords=("kw",), canonical_answer=answer)


def recorder():
    rows = []

    def record(row):
        rows.append(row)
        return len(rows)

    return rows, record


CERT = entry(1, "certificates", "Certificates are issued after you complete the course requirements.")


def test_rewrite_upgrades_refused_to_answered_and_marks_llm_used():
    index = DictIndex({"wie bekomme ich mein zertifikat": [], "get certificate": [Ranked(CERT, 0.6)]})
    rows, record = recorder()

    result = answer_question(
        "wie bekomme ich mein zertifikat", index, record,
        rewrite=lambda q: "get certificate",
    )

    assert result.verdict == "Answered"
    assert result.answer == CERT.canonical_answer
    assert rows[0]["llm_used"] is True
    assert rows[0]["matched_faq_id"] == 1


def test_rewrite_is_not_called_when_original_is_already_answered():
    index = DictIndex({"get certificate": [Ranked(CERT, 0.6)]})
    rows, record = recorder()
    called = []

    def rewrite(q):
        called.append(q)
        return "something else"

    result = answer_question("get certificate", index, record, rewrite=rewrite)

    assert result.verdict == "Answered"
    assert called == []
    assert rows[0]["llm_used"] is False


def test_rewrite_that_is_not_answered_keeps_the_original_verdict():
    index = DictIndex({"quantum physics": [], "lattice gauge": []})
    rows, record = recorder()

    result = answer_question("quantum physics", index, record, rewrite=lambda q: "lattice gauge")

    assert result.verdict == "Refused"
    assert result.answer == REFUSAL_TEXT
    assert rows[0]["llm_used"] is False


def test_rewrite_never_turns_a_refusal_into_a_different_answer_text():
    # Even when the rewrite is Answered, the text returned is the FAQ's canonical answer.
    index = DictIndex({"zzz": [], "get certificate": [Ranked(CERT, 0.6)]})
    rows, record = recorder()

    result = answer_question("zzz", index, record, rewrite=lambda q: "get certificate")

    assert result.answer == CERT.canonical_answer
    assert result.answer != "get certificate"


def test_failed_rewrite_leaves_unclear_unchanged():
    index = DictIndex({"something vague": [Ranked(CERT, 0.2)]})
    rows, record = recorder()

    result = answer_question("something vague", index, record, rewrite=lambda q: None)

    assert result.verdict == "Unclear"
    assert result.answer == CLARIFY_TEXT
    assert rows[0]["llm_used"] is False
