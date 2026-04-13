"""Composable word query builder for dictionary search."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum, auto

from scrabble_engine.dawg import DAWG, DAWGNode
from scrabble_engine.tiles import LETTER_VALUES


def word_score(word: str) -> int:
    """Base score of a word — sum of tile point values, no board bonuses."""
    return sum(LETTER_VALUES.get(ch, 0) for ch in word.upper())


class _SortKey(Enum):
    ALPHABETICAL = auto()
    SCORE = auto()
    LENGTH = auto()


@dataclass
class _SortSpec:
    key: _SortKey
    descending: bool


class WordQuery:
    """Builder-pattern query for searching the dictionary.

    Chain filter methods, then call execute() or count().
    """

    def __init__(self, dawg: DAWG) -> None:
        self._dawg = dawg
        self._prefix: str | None = None
        self._suffix: str | None = None
        self._containing: list[str] = []
        self._not_containing: set[str] = set()
        self._substrings: list[str] = []
        self._min_len: int | None = None
        self._max_len: int | None = None
        self._letter_at: list[tuple[int, str]] = []
        self._pattern: str | None = None
        self._rack: list[str] | None = None
        self._min_score: int | None = None
        self._sort: _SortSpec | None = None

    # --- Filter methods ---

    def containing(self, letters: str) -> WordQuery:
        """Word must contain ALL of these letters."""
        self._containing.extend(letters.upper())
        return self

    def not_containing(self, letters: str) -> WordQuery:
        """Word must NOT contain any of these letters."""
        self._not_containing.update(letters.upper())
        return self

    def has_substring(self, substring: str) -> WordQuery:
        """Word must contain this exact consecutive substring."""
        self._substrings.append(substring.upper())
        return self

    def starting_with(self, prefix: str) -> WordQuery:
        """Word must start with this prefix."""
        self._prefix = prefix.upper()
        return self

    def ending_with(self, suffix: str) -> WordQuery:
        """Word must end with this suffix."""
        self._suffix = suffix.upper()
        return self

    def length(self, min: int | None = None, max: int | None = None) -> WordQuery:
        """Word length must be within range."""
        if min is not None:
            self._min_len = min
        if max is not None:
            self._max_len = max
        return self

    def letter_at(self, position: int, letter: str) -> WordQuery:
        """Word must have this letter at this 0-indexed position."""
        self._letter_at.append((position, letter.upper()))
        return self

    def matching_pattern(self, pattern: str) -> WordQuery:
        """Pattern with '.' for wildcards. Implicitly sets length."""
        self._pattern = pattern.upper()
        self._min_len = len(pattern)
        self._max_len = len(pattern)
        return self

    def from_rack(self, letters: list[str]) -> WordQuery:
        """Word must be formable from these letters (supports '?' for blanks)."""
        self._rack = [ch.upper() for ch in letters]
        return self

    def min_score(self, score: int) -> WordQuery:
        """Word's base tile score must be >= score."""
        self._min_score = score
        return self

    # --- Sort methods ---

    def sort_by_score(self, descending: bool = True) -> WordQuery:
        self._sort = _SortSpec(_SortKey.SCORE, descending)
        return self

    def sort_by_length(self, descending: bool = True) -> WordQuery:
        self._sort = _SortSpec(_SortKey.LENGTH, descending)
        return self

    def sort_alphabetically(self) -> WordQuery:
        self._sort = _SortSpec(_SortKey.ALPHABETICAL, False)
        return self

    # --- Execution ---

    def execute(self, limit: int | None = None) -> list[str]:
        """Run the query and return matching words."""
        candidates = self._generate_candidates()
        candidates = self._apply_post_filters(candidates)
        results = self._apply_sort(candidates)
        if limit is not None:
            results = results[:limit]
        return results

    def count(self) -> int:
        """Return count of matching words."""
        candidates = self._generate_candidates()
        candidates = self._apply_post_filters(candidates)
        return len(candidates)

    # --- Internal ---

    def _generate_candidates(self) -> list[str]:
        """Use the most restrictive DAWG-accelerated filter for traversal."""
        if self._rack is not None:
            return self._candidates_from_rack()
        if self._prefix is not None:
            return self._candidates_from_prefix()
        if self._pattern is not None:
            return self._candidates_from_pattern()
        return self._candidates_all()

    def _candidates_from_rack(self) -> list[str]:
        """Traverse DAWG consuming rack letters (supports blanks)."""
        available = Counter(self._rack)
        found: set[str] = set()

        def _search(node: DAWGNode, prefix: str) -> None:
            if node.is_terminal and len(prefix) > 0:
                found.add(prefix)
            for ch, child in node.children.items():
                if available[ch] > 0:
                    available[ch] -= 1
                    _search(child, prefix + ch)
                    available[ch] += 1
                elif available["?"] > 0:
                    available["?"] -= 1
                    _search(child, prefix + ch)
                    available["?"] += 1

        _search(self._dawg.root, "")
        return list(found)

    def _candidates_from_prefix(self) -> list[str]:
        """Use DAWG prefix traversal."""
        node = self._dawg.starts_with(self._prefix)
        if node is None:
            return []
        return self._dawg.words_from_node(node, self._prefix)

    def _candidates_from_pattern(self) -> list[str]:
        """Traverse DAWG following pattern constraints."""
        results: list[str] = []

        def _search(node: DAWGNode, depth: int, prefix: str) -> None:
            if depth == len(self._pattern):
                if node.is_terminal:
                    results.append(prefix)
                return
            ch = self._pattern[depth]
            if ch == ".":
                for letter, child in node.children.items():
                    _search(child, depth + 1, prefix + letter)
            elif ch in node.children:
                _search(node.children[ch], depth + 1, prefix + ch)

        _search(self._dawg.root, 0, "")
        return results

    def _candidates_all(self) -> list[str]:
        """Collect all words from the DAWG."""
        return self._dawg.words_from_node(self._dawg.root, "")

    def _apply_post_filters(self, candidates: list[str]) -> list[str]:
        """Apply non-DAWG filters to the candidate list."""
        results = candidates

        if self._prefix is not None and self._rack is not None:
            # prefix wasn't used for traversal — apply as post-filter
            results = [w for w in results if w.startswith(self._prefix)]

        if self._suffix is not None:
            results = [w for w in results if w.endswith(self._suffix)]

        if self._min_len is not None:
            results = [w for w in results if len(w) >= self._min_len]

        if self._max_len is not None:
            results = [w for w in results if len(w) <= self._max_len]

        if self._containing:
            req = Counter(self._containing)
            results = [
                w for w in results
                if all(Counter(w)[ch] >= cnt for ch, cnt in req.items())
            ]

        if self._not_containing:
            results = [
                w for w in results
                if not any(ch in w for ch in self._not_containing)
            ]

        if self._substrings:
            results = [
                w for w in results
                if all(sub in w for sub in self._substrings)
            ]

        if self._letter_at:
            results = [
                w for w in results
                if all(
                    pos < len(w) and w[pos] == letter
                    for pos, letter in self._letter_at
                )
            ]

        if self._pattern is not None and self._rack is not None:
            # pattern wasn't used for traversal — apply as post-filter
            results = [
                w for w in results
                if len(w) == len(self._pattern)
                and all(
                    p == "." or p == c
                    for p, c in zip(self._pattern, w)
                )
            ]

        if self._min_score is not None:
            results = [w for w in results if word_score(w) >= self._min_score]

        return results

    def _apply_sort(self, candidates: list[str]) -> list[str]:
        if self._sort is None:
            return sorted(candidates)

        if self._sort.key == _SortKey.ALPHABETICAL:
            return sorted(candidates)
        elif self._sort.key == _SortKey.SCORE:
            return sorted(
                candidates,
                key=lambda w: word_score(w),
                reverse=self._sort.descending,
            )
        elif self._sort.key == _SortKey.LENGTH:
            return sorted(
                candidates,
                key=len,
                reverse=self._sort.descending,
            )
        return sorted(candidates)
