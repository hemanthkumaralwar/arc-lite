import pytest

from app.normalize import normalize


@pytest.mark.parametrize(
    "raw, expected",
    [
        # 1. mixed case and stopwords
        ("How do I GET my Certificate?", "get certificate"),
        # 2. punctuation and repeated whitespace
        ("  Hello,   world!!  ", "hello world"),
        # 3. accented characters, composed form
        ("Résumé help", "résumé help"),
        # 4. accented characters, decomposed form (e + combining accent) gives the same result
        ("Re\u0301sume\u0301 help", "résumé help"),
        # 5. full-width characters are folded by NFKC
        ("ＡＢＣ１２３ course", "abc123 course"),
        # 6. apostrophes are removed so "can't" stays one token and keeps its negation
        ("I can't log in", "cant log"),
        # 7. curly apostrophe behaves the same as straight
        ("I can\u2019t log in", "cant log"),
        # 8. underscores and dashes become spaces
        ("email_address — update", "email address update"),
        # 9. tabs and newlines are whitespace
        ("course\t\tstart\n", "course start"),
        # 10. digits and ordinals are kept
        ("1st course!!!", "1st course"),
        # 11. only stopwords gives an empty string
        ("the the the", ""),
        # 12. empty and whitespace-only input
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalize_examples(raw, expected):
    assert normalize(raw) == expected


def test_same_input_always_gives_same_output():
    text = "Where can I download my certificate?"
    assert normalize(text) == normalize(text)


def test_non_string_input_raises_type_error():
    with pytest.raises(TypeError):
        normalize(None)
    with pytest.raises(TypeError):
        normalize(123)
