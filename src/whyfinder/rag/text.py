"""Tokens and chunks for review retrieval (docs/spec/06_RAG.md; 04_ALGORITHMS.md §A8).

Tokens: Unicode-folded, lowercased words (letters and digits, inner apostrophes kept), English stop
words and one-character tokens dropped. Chunks: one short text is one chunk; a longer one is split
into windows of `size` words that overlap by `overlap`.
"""

from __future__ import annotations

import re
import unicodedata

WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
APOSTROPHES = {0x2018: "'", 0x2019: "'"}

# fmt: off
STOP_WORDS = frozenset(
    {
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any",
        "are", "aren't", "as", "at", "be", "because", "been", "before", "being", "below",
        "between", "both", "but", "by", "can", "can't", "cannot", "could", "couldn't", "did",
        "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during", "each", "few",
        "for", "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having",
        "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself", "him",
        "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into",
        "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't",
        "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
        "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
        "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than", "that",
        "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's",
        "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through",
        "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll",
        "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where",
        "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't",
        "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
        "yourself", "yourselves", "just", "also", "get", "got", "really", "much", "even", "still",
        "like", "will",
    }
)
# fmt: on


def fold(text: str) -> str:
    """Lowercase ASCII-folded text: accents dropped, curly apostrophes made straight."""
    text = text.translate(APOSTROPHES)
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def tokenize(text: str) -> list[str]:
    """Words of the text in order, without stop words or one-character tokens."""
    return [w for w in WORD.findall(fold(text)) if len(w) > 1 and w not in STOP_WORDS]


def chunk(words: list[str], size: int = 100, overlap: int = 20) -> list[list[str]]:
    """Windows of `size` words, each `size - overlap` after the last; short texts stay whole."""
    if size < 1 or not 0 <= overlap < size:
        raise ValueError("need size >= 1 and 0 <= overlap < size")
    if len(words) <= size:
        return [list(words)] if words else []
    step = size - overlap
    out = []
    for start in range(0, len(words), step):
        out.append(list(words[start : start + size]))
        if start + size >= len(words):
            break
    return out
