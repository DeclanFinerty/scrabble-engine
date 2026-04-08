"""Board representation with bonus squares, tile placement, and board I/O."""

from __future__ import annotations

from enum import Enum

from scrabble_engine.dawg import DAWG
from scrabble_engine.tiles import LETTER_VALUES, Tile

BOARD_SIZE = 15


class Direction(Enum):
    ACROSS = "ACROSS"
    DOWN = "DOWN"


class BonusSquare(Enum):
    NONE = "."
    DOUBLE_LETTER = "DL"
    TRIPLE_LETTER = "TL"
    DOUBLE_WORD = "DW"
    TRIPLE_WORD = "TW"
    CENTER = "★"


# fmt: off
_BONUS_LAYOUT: list[list[str]] = [
    ["TW", ".", ".", "DL", ".", ".", ".", "TW", ".", ".", ".", "DL", ".", ".", "TW"],
    [".", "DW", ".", ".", ".", "TL", ".", ".", ".", "TL", ".", ".", ".", "DW", "."],
    [".", ".", "DW", ".", ".", ".", "DL", ".", "DL", ".", ".", ".", "DW", ".", "."],
    ["DL", ".", ".", "DW", ".", ".", ".", "DL", ".", ".", ".", "DW", ".", ".", "DL"],
    [".", ".", ".", ".", "DW", ".", ".", ".", ".", ".", "DW", ".", ".", ".", "."],
    [".", "TL", ".", ".", ".", "TL", ".", ".", ".", "TL", ".", ".", ".", "TL", "."],
    [".", ".", "DL", ".", ".", ".", "DL", ".", "DL", ".", ".", ".", "DL", ".", "."],
    ["TW", ".", ".", "DL", ".", ".", ".", "★", ".", ".", ".", "DL", ".", ".", "TW"],
    [".", ".", "DL", ".", ".", ".", "DL", ".", "DL", ".", ".", ".", "DL", ".", "."],
    [".", "TL", ".", ".", ".", "TL", ".", ".", ".", "TL", ".", ".", ".", "TL", "."],
    [".", ".", ".", ".", "DW", ".", ".", ".", ".", ".", "DW", ".", ".", ".", "."],
    ["DL", ".", ".", "DW", ".", ".", ".", "DL", ".", ".", ".", "DW", ".", ".", "DL"],
    [".", ".", "DW", ".", ".", ".", "DL", ".", "DL", ".", ".", ".", "DW", ".", "."],
    [".", "DW", ".", ".", ".", "TL", ".", ".", ".", "TL", ".", ".", ".", "DW", "."],
    ["TW", ".", ".", "DL", ".", ".", ".", "TW", ".", ".", ".", "DL", ".", ".", "TW"],
]
# fmt: on


def _build_bonus_grid() -> list[list[BonusSquare]]:
    grid: list[list[BonusSquare]] = []
    for row in _BONUS_LAYOUT:
        grid.append([BonusSquare(cell) for cell in row])
    return grid


class Board:
    """15x15 Scrabble board with bonus squares and tile placement."""

    def __init__(self) -> None:
        self.grid: list[list[Tile | None]] = [
            [None] * BOARD_SIZE for _ in range(BOARD_SIZE)
        ]
        self.bonus: list[list[BonusSquare]] = _build_bonus_grid()

    def get_tile(self, row: int, col: int) -> Tile | None:
        if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
            return self.grid[row][col]
        return None

    def is_occupied(self, row: int, col: int) -> bool:
        return self.get_tile(row, col) is not None

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE

    def is_empty(self) -> bool:
        """Return True if no tiles have been placed on the board."""
        return all(
            self.grid[r][c] is None
            for r in range(BOARD_SIZE)
            for c in range(BOARD_SIZE)
        )

    def place_tile(self, row: int, col: int, tile: Tile) -> None:
        """Place a single tile on the board."""
        if not self.in_bounds(row, col):
            raise ValueError(f"Position ({row}, {col}) is out of bounds")
        if self.grid[row][col] is not None:
            raise ValueError(f"Position ({row}, {col}) is already occupied")
        self.grid[row][col] = tile

    def place_word(
        self,
        word: str,
        start: tuple[int, int],
        direction: Direction,
        tiles: list[Tile],
    ) -> list[tuple[int, int]]:
        """Place a word on the board, skipping squares already occupied.

        Returns the list of (row, col) positions where new tiles were placed.
        """
        row, col = start
        dr = 1 if direction == Direction.DOWN else 0
        dc = 1 if direction == Direction.ACROSS else 0
        tile_idx = 0
        placed_positions: list[tuple[int, int]] = []

        for i, letter in enumerate(word.upper()):
            r = row + i * dr
            c = col + i * dc
            if not self.in_bounds(r, c):
                raise ValueError(f"Word extends out of bounds at ({r}, {c})")
            if self.grid[r][c] is not None:
                existing = self.grid[r][c]
                existing_letter = existing.blank_letter if existing.is_blank else existing.letter
                if existing_letter != letter:
                    raise ValueError(
                        f"Conflict at ({r}, {c}): existing '{existing_letter}' != '{letter}'"
                    )
                # Square already has the right letter, skip
            else:
                if tile_idx >= len(tiles):
                    raise ValueError("Not enough tiles provided")
                self.grid[r][c] = tiles[tile_idx]
                placed_positions.append((r, c))
                tile_idx += 1

        return placed_positions

    def get_anchor_squares(self) -> list[tuple[int, int]]:
        """Return empty squares adjacent to at least one occupied square.

        On an empty board, returns only the center square (7, 7).
        """
        if self.is_empty():
            return [(7, 7)]

        anchors: list[tuple[int, int]] = []
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.grid[r][c] is not None:
                    continue
                # Check four neighbors
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if self.in_bounds(nr, nc) and self.grid[nr][nc] is not None:
                        anchors.append((r, c))
                        break
        return anchors

    def get_cross_checks(
        self, row: int, col: int, direction: Direction, dawg: DAWG
    ) -> set[str]:
        """Return the set of letters valid at (row, col) given perpendicular constraints.

        If the perpendicular direction has no adjacent tiles, all letters are valid.
        Otherwise, find the existing prefix/suffix in the perpendicular direction
        and return only letters that form valid words with them.
        """
        if self.grid[row][col] is not None:
            return set()

        # Perpendicular direction
        if direction == Direction.ACROSS:
            # Check vertical (up/down) constraints
            pr, pc, pdr, pdc = row, col, -1, 0  # up
        else:
            # Check horizontal (left/right) constraints
            pr, pc, pdr, pdc = row, col, 0, -1  # left

        # Walk backwards to find prefix
        prefix_letters: list[str] = []
        r, c = row + pdr, col + pdc
        while self.in_bounds(r, c) and self.grid[r][c] is not None:
            tile = self.grid[r][c]
            prefix_letters.append(tile.blank_letter if tile.is_blank else tile.letter)
            r += pdr
            c += pdc
        prefix_letters.reverse()

        # Walk forwards to find suffix
        suffix_letters: list[str] = []
        fdr, fdc = -pdr, -pdc  # opposite direction
        r, c = row + fdr, col + fdc
        while self.in_bounds(r, c) and self.grid[r][c] is not None:
            tile = self.grid[r][c]
            suffix_letters.append(tile.blank_letter if tile.is_blank else tile.letter)
            r += fdr
            c += fdc

        # No adjacent tiles in perpendicular direction — any letter is valid
        if not prefix_letters and not suffix_letters:
            return set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

        prefix = "".join(prefix_letters)
        suffix = "".join(suffix_letters)

        valid: set[str] = set()
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            candidate = prefix + ch + suffix
            if dawg.search(candidate):
                valid.add(ch)
        return valid

    def read_word_at(
        self, row: int, col: int, direction: Direction
    ) -> tuple[str, tuple[int, int]]:
        """Read the full word at a position in the given direction.

        Returns (word, (start_row, start_col)).
        Walks backwards to find the start, then forwards to read the word.
        """
        dr = 1 if direction == Direction.DOWN else 0
        dc = 1 if direction == Direction.ACROSS else 0

        # Walk backwards to find start
        r, c = row, col
        while self.in_bounds(r - dr, c - dc) and self.grid[r - dr][c - dc] is not None:
            r -= dr
            c -= dc

        start = (r, c)
        letters: list[str] = []
        while self.in_bounds(r, c) and self.grid[r][c] is not None:
            tile = self.grid[r][c]
            letters.append(tile.blank_letter if tile.is_blank else tile.letter)
            r += dr
            c += dc

        return "".join(letters), start

    def to_text(self) -> str:
        """Export board as 15-line text grid.

        '.' for empty, 'A'-'Z' for regular tiles, 'a'-'z' for blanks.
        """
        lines: list[str] = []
        for r in range(BOARD_SIZE):
            row_chars: list[str] = []
            for c in range(BOARD_SIZE):
                tile = self.grid[r][c]
                if tile is None:
                    row_chars.append(".")
                elif tile.is_blank:
                    row_chars.append((tile.blank_letter or "?").lower())
                else:
                    row_chars.append(tile.letter)
            lines.append("".join(row_chars))
        return "\n".join(lines)

    @classmethod
    def from_text(cls, text: str) -> Board:
        """Import board from a text grid.

        '.' for empty, 'A'-'Z' for regular tiles, 'a'-'z' for blanks.
        """
        board = cls()
        lines = [line.strip() for line in text.strip().splitlines()]
        if len(lines) != BOARD_SIZE:
            raise ValueError(f"Expected {BOARD_SIZE} lines, got {len(lines)}")
        for r, line in enumerate(lines):
            if len(line) != BOARD_SIZE:
                raise ValueError(
                    f"Row {r}: expected {BOARD_SIZE} chars, got {len(line)}"
                )
            for c, ch in enumerate(line):
                if ch == ".":
                    continue
                elif ch.isupper():
                    board.grid[r][c] = Tile(
                        letter=ch, points=LETTER_VALUES.get(ch, 0)
                    )
                elif ch.islower():
                    letter = ch.upper()
                    board.grid[r][c] = Tile(
                        letter="?",
                        points=0,
                        is_blank=True,
                        blank_letter=letter,
                    )
        return board
