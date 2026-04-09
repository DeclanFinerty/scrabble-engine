"""Word family computation — find extensions, prefixes, and roots."""

from __future__ import annotations

from scrabble_engine.dawg import DAWG

# Common English suffixes, ordered longest first for greedy matching.
_SUFFIXES = [
    "TION", "MENT", "NESS", "ABLE", "IBLE", "LESS",
    "ING", "ERS", "EST", "ISH", "IST", "IZE", "FUL",
    "ED", "ER", "LY", "ES",
    "S",
]


def get_word_family(dawg: DAWG, root_word: str) -> dict:
    """Given a root word, find all valid extensions (suffixes) and prefixes.

    Returns:
        {
            "root": "BOARD",
            "extensions": [
                {"word": "BOARDS", "suffix": "S"},
                {"word": "BOARDED", "suffix": "ED"},
                ...
            ],
            "prefixes": [
                {"word": "ABOARD", "prefix": "A"},
                ...
            ]
        }
    """
    root = root_word.upper()
    if not dawg.search(root):
        raise ValueError(f"'{root}' is not a valid word")

    # Find extensions: words that start with root and are longer
    node = dawg.starts_with(root)
    extensions: list[dict[str, str]] = []
    if node is not None:
        all_from_root = dawg.words_from_node(node, root)
        for word in all_from_root:
            if word != root:
                extensions.append({
                    "word": word,
                    "suffix": word[len(root):],
                })

    # Find prefixes: words that end with root and are longer
    # Must iterate all words — no DAWG shortcut for suffix search
    prefixes: list[dict[str, str]] = []
    all_words = dawg.words_from_node(dawg.root, "")
    for word in all_words:
        if word != root and word.endswith(root) and len(word) > len(root):
            prefixes.append({
                "word": word,
                "prefix": word[: len(word) - len(root)],
            })

    return {
        "root": root,
        "extensions": sorted(extensions, key=lambda e: e["word"]),
        "prefixes": sorted(prefixes, key=lambda p: p["word"]),
    }


def get_root(dawg: DAWG, word: str) -> str:
    """Find the root of a word by removing common morphological suffixes.

    Tries removing the longest matching suffix first and checks if the
    remainder is a valid word. Returns the word itself if no suffix
    can be removed to form a valid word.
    """
    w = word.upper()
    if not dawg.search(w):
        raise ValueError(f"'{w}' is not a valid word")

    for suffix in _SUFFIXES:
        if w.endswith(suffix) and len(w) > len(suffix):
            candidate = w[: -len(suffix)]
            if dawg.search(candidate):
                return candidate

    return w
