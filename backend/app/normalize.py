"""Text normalization for matching. Pure function: no I/O, no database, no network.

The same function must be applied to FAQ keywords and to student questions,
so both sides of the TF-IDF comparison use identical tokens.
"""
import re
import unicodedata

# Words that carry no topic. Negations ("not", "no", "cannot", "cant") are deliberately
# kept, because removing them could make a question look like the opposite request.
STOPWORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "am",
        "to", "of", "in", "on", "at", "for", "with", "by", "from", "as",
        "and", "or", "so", "if",
        "i", "me", "my", "we", "our", "you", "your", "it", "its",
        "this", "that", "which",
        "do", "does", "did",
        "how", "what", "when", "where", "why", "who",
        "s", "t",
    }
)

_APOSTROPHES = re.compile(r"['\u2019]")  # straight and curly apostrophes
_NON_WORD = re.compile(r"[\W_]+")  # punctuation, symbols, whitespace, and underscores


def normalize(text: str) -> str:
    """Return the matching form of `text`: NFKC, lowercase, no punctuation, no stopwords."""
    if not isinstance(text, str):
        raise TypeError("normalize() expects a str")

    s = unicodedata.normalize("NFKC", text)
    s = s.lower()
    # Remove apostrophes first so "can't" becomes "cant" and is not split into "can" + "t".
    s = _APOSTROPHES.sub("", s)
    s = _NON_WORD.sub(" ", s)

    tokens = [token for token in s.split() if token not in STOPWORDS]
    return " ".join(tokens)
