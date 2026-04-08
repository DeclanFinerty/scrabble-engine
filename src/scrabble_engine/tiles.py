"""Tile definitions, bag management, rack, and rack solving."""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field

from scrabble_engine.dawg import DAWG, DAWGNode

# Letter -> (point value, count in standard bag)
TILE_DISTRIBUTION: dict[str, tuple[int, int]] = {
    "A": (1, 9),
    "B": (3, 2),
    "C": (3, 2),
    "D": (2, 4),
    "E": (1, 12),
    "F": (4, 2),
    "G": (2, 3),
    "H": (4, 2),
    "I": (1, 9),
    "J": (8, 1),
    "K": (5, 1),
    "L": (1, 4),
    "M": (3, 2),
    "N": (1, 6),
    "O": (1, 8),
    "P": (3, 2),
    "Q": (10, 1),
    "R": (1, 6),
    "S": (1, 4),
    "T": (1, 6),
    "U": (1, 4),
    "V": (4, 2),
    "W": (4, 2),
    "X": (8, 1),
    "Y": (4, 2),
    "Z": (10, 1),
    "?": (0, 2),  # blank
}

LETTER_VALUES: dict[str, int] = {letter: pts for letter, (pts, _) in TILE_DISTRIBUTION.items()}


@dataclass
class Tile:
    """A single Scrabble tile."""

    letter: str  # A-Z or '?' for blank
    points: int  # point value (0 for blank)
    is_blank: bool = False  # True if this tile is a blank representing a letter
    blank_letter: str | None = None  # The letter a blank is representing, or None

    @classmethod
    def from_letter(cls, letter: str) -> Tile:
        """Create a standard tile from a letter (A-Z or '?' for blank)."""
        letter = letter.upper()
        if letter == "?":
            return cls(letter="?", points=0, is_blank=True)
        return cls(letter=letter, points=LETTER_VALUES[letter])


class TileBag:
    """The bag of tiles for a Scrabble game."""

    def __init__(self) -> None:
        self._tiles: list[Tile] = []
        for letter, (points, count) in TILE_DISTRIBUTION.items():
            is_blank = letter == "?"
            for _ in range(count):
                self._tiles.append(Tile(letter=letter, points=points, is_blank=is_blank))
        random.shuffle(self._tiles)

    def draw(self, n: int) -> list[Tile]:
        """Draw n random tiles from the bag. Returns fewer if bag doesn't have enough."""
        n = min(n, len(self._tiles))
        drawn = self._tiles[:n]
        self._tiles = self._tiles[n:]
        return drawn

    def remaining(self) -> dict[str, int]:
        """Count of each letter remaining in the bag."""
        counts: dict[str, int] = Counter(t.letter for t in self._tiles)
        return dict(sorted(counts.items()))

    def remove(self, letters: list[str]) -> None:
        """Remove specific tiles from the bag by letter.

        Raises ValueError if a requested letter isn't in the bag.
        """
        for letter in letters:
            letter = letter.upper()
            for i, tile in enumerate(self._tiles):
                if tile.letter == letter:
                    self._tiles.pop(i)
                    break
            else:
                raise ValueError(f"Tile '{letter}' not found in bag")

    def return_tiles(self, tiles: list[Tile]) -> None:
        """Return tiles to the bag (e.g., after an exchange)."""
        self._tiles.extend(tiles)
        random.shuffle(self._tiles)

    def tiles_in_bag(self) -> int:
        """Total number of tiles remaining."""
        return len(self._tiles)


@dataclass
class Rack:
    """A player's tile rack (up to 7 tiles)."""

    MAX_TILES: int = field(default=7, init=False, repr=False)
    _tiles: list[Tile] = field(default_factory=list, init=False)

    @property
    def tiles(self) -> list[Tile]:
        return list(self._tiles)

    def add(self, tiles: list[Tile]) -> None:
        """Add tiles to the rack. Raises ValueError if it would exceed 7."""
        if len(self._tiles) + len(tiles) > self.MAX_TILES:
            raise ValueError(
                f"Cannot add {len(tiles)} tiles: rack has {len(self._tiles)}, max is {self.MAX_TILES}"
            )
        self._tiles.extend(tiles)

    def remove(self, tiles: list[Tile]) -> None:
        """Remove specific tiles from the rack."""
        remaining = list(self._tiles)
        for tile in tiles:
            for i, r in enumerate(remaining):
                if r.letter == tile.letter:
                    remaining.pop(i)
                    break
            else:
                raise ValueError(f"Tile '{tile.letter}' not on rack")
        self._tiles = remaining

    def letters(self) -> list[str]:
        """Sorted list of letters on the rack."""
        return sorted(t.letter for t in self._tiles)

    def size(self) -> int:
        return len(self._tiles)

    def is_full(self) -> bool:
        return len(self._tiles) >= self.MAX_TILES

    def is_empty(self) -> bool:
        return len(self._tiles) == 0


def find_words(rack: list[str], dawg: DAWG) -> list[str]:
    """Find all valid words that can be formed from the given rack letters.

    Traverses the DAWG, consuming letters from the rack at each step.
    Handles duplicate letters correctly.
    """
    rack_upper = [ch.upper() for ch in rack]
    available = Counter(rack_upper)
    found: set[str] = set()

    def _search(node: DAWGNode, prefix: str) -> None:
        if node.is_terminal and len(prefix) > 0:
            found.add(prefix)
        for ch, child in node.children.items():
            if available[ch] > 0:
                available[ch] -= 1
                _search(child, prefix + ch)
                available[ch] += 1

    _search(dawg.root, "")
    return sorted(found)
