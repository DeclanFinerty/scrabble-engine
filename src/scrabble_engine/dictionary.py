"""Dictionary module for word list loading and querying."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from scrabble_engine.dawg import DAWG

_DEFAULT_WORD_LIST = Path(__file__).parent / "data" / "twl06.txt"


class Dictionary:
    """Scrabble dictionary backed by a DAWG with auxiliary indexes for queries."""

    def __init__(self, dawg: DAWG, words: list[str]) -> None:
        self._dawg = dawg
        self._words = sorted(words)
        self._word_set = frozenset(words)
        self._by_length: dict[int, list[str]] = defaultdict(list)
        for w in self._words:
            self._by_length[len(w)].append(w)

    @classmethod
    def from_file(cls, path: str | Path = _DEFAULT_WORD_LIST) -> Dictionary:
        """Load a dictionary from a word list file."""
        words: list[str] = []
        with open(path) as f:
            for line in f:
                word = line.strip()
                if word and word.isalpha():
                    words.append(word.upper())
        dawg = DAWG(words)
        return cls(dawg, words)

    @property
    def dawg(self) -> DAWG:
        return self._dawg

    @property
    def word_count(self) -> int:
        return len(self._word_set)

    def is_valid(self, word: str) -> bool:
        """Check if a word is in the dictionary."""
        return word.upper() in self._word_set

    def words_by_length(self, n: int) -> list[str]:
        """Return all words of exactly length n."""
        return self._by_length.get(n, [])

    def words_starting_with(self, prefix: str) -> list[str]:
        """Return all words starting with the given prefix."""
        prefix = prefix.upper()
        node = self._dawg.starts_with(prefix)
        if node is None:
            return []
        return self._dawg.words_from_node(node, prefix)

    def words_ending_with(self, suffix: str) -> list[str]:
        """Return all words ending with the given suffix."""
        suffix = suffix.upper()
        return [w for w in self._words if w.endswith(suffix)]

    def words_containing(self, substring: str) -> list[str]:
        """Return all words containing the given substring."""
        substring = substring.upper()
        return [w for w in self._words if substring in w]

    def words_matching_pattern(self, pattern: str) -> list[str]:
        """Return all words matching the pattern.

        Pattern uses '.' for any single letter and uppercase letters
        for exact matches. Length is determined by pattern length.
        Example: '..G' matches all 3-letter words ending in G.
        """
        pattern = pattern.upper()
        n = len(pattern)
        candidates = self._by_length.get(n, [])
        results: list[str] = []
        for word in candidates:
            if all(p == "." or p == w for p, w in zip(pattern, word)):
                results.append(word)
        return results
