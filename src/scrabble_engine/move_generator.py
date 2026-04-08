"""Board-aware legal move generation using the Appel & Jacobson algorithm."""

from __future__ import annotations

import copy
from collections import Counter
from dataclasses import dataclass, field

from scrabble_engine.board import BOARD_SIZE, Board, Direction
from scrabble_engine.dawg import DAWG, DAWGNode
from scrabble_engine.scoring import score_word
from scrabble_engine.tiles import Tile


@dataclass
class Move:
    """A legal move on the board."""

    word: str
    start: tuple[int, int]
    direction: Direction
    tiles_placed: list[tuple[int, int, Tile]]
    score: int
    words_formed: list[str]


def generate_moves(board: Board, rack: list[str], dawg: DAWG) -> list[Move]:
    """Generate all legal moves for the given board and rack.

    Returns moves sorted by score descending.
    """
    generator = _MoveGenerator(board, rack, dawg)
    moves = generator.generate()
    moves.sort(key=lambda m: m.score, reverse=True)
    return moves


def best_moves(
    board: Board, rack: list[str], dawg: DAWG, n: int = 10
) -> list[Move]:
    """Return the top n moves by score."""
    return generate_moves(board, rack, dawg)[:n]


class _MoveGenerator:
    """Internal move generator implementing Appel & Jacobson."""

    def __init__(self, board: Board, rack: list[str], dawg: DAWG) -> None:
        self.board = board
        self.dawg = dawg
        self.rack_letters = [ch.upper() for ch in rack]
        self.available = Counter(self.rack_letters)
        self.moves: list[Move] = []

    def generate(self) -> list[Move]:
        self._generate_direction(Direction.ACROSS)
        self._generate_direction(Direction.DOWN)
        return self.moves

    def _generate_direction(self, direction: Direction) -> None:
        """Generate all moves in one direction (ACROSS or DOWN)."""
        # For ACROSS, iterate rows. For DOWN, iterate columns.
        # We transpose the logic: for DOWN, we swap row/col conceptually.
        for primary in range(BOARD_SIZE):
            self._generate_for_line(primary, direction)

    def _generate_for_line(self, line: int, direction: Direction) -> None:
        """Generate moves for a single row (ACROSS) or column (DOWN)."""
        # Precompute cross-checks for every cell in this line
        cross_checks: list[set[str]] = []
        for secondary in range(BOARD_SIZE):
            r, c = self._coords(line, secondary, direction)
            cross_checks.append(
                self.board.get_cross_checks(r, c, direction, self.dawg)
            )

        # Find anchor squares in this line
        anchors = self._find_anchors_in_line(line, direction)

        if not anchors:
            return

        for anchor_pos in anchors:
            # Determine left limit: count empty non-anchor squares to the left
            left_limit = 0
            pos = anchor_pos - 1
            while pos >= 0:
                r, c = self._coords(line, pos, direction)
                if self.board.is_occupied(r, c):
                    break
                # Check if this is also an anchor
                if pos in anchors:
                    break
                left_limit += 1
                pos -= 1

            # Check if there are existing tiles to the left of the anchor
            # If so, we must use them as the left part instead of generating one
            r_check, c_check = self._coords(line, anchor_pos - 1, direction)
            if anchor_pos > 0 and self.board.is_occupied(r_check, c_check):
                # There are tiles to the left — read the existing prefix
                existing_prefix, existing_node = self._read_existing_prefix(
                    line, anchor_pos, direction
                )
                if existing_node is not None:
                    self._extend_right(
                        existing_prefix,
                        existing_node,
                        anchor_pos,
                        line,
                        direction,
                        cross_checks,
                        [],
                    )
            else:
                # Generate left parts from scratch
                self._left_part(
                    "",
                    self.dawg.root,
                    anchor_pos,
                    left_limit,
                    line,
                    direction,
                    cross_checks,
                    [],
                )

    def _read_existing_prefix(
        self, line: int, anchor_pos: int, direction: Direction
    ) -> tuple[str, DAWGNode | None]:
        """Read tiles to the left of the anchor as an existing prefix."""
        letters: list[str] = []
        pos = anchor_pos - 1
        while pos >= 0:
            r, c = self._coords(line, pos, direction)
            tile = self.board.get_tile(r, c)
            if tile is None:
                break
            letter = tile.blank_letter if tile.is_blank else tile.letter
            letters.append(letter)
            pos -= 1
        letters.reverse()

        # Traverse DAWG for this prefix
        node = self.dawg.root
        for ch in letters:
            if ch not in node.children:
                return "".join(letters), None
            node = node.children[ch]

        return "".join(letters), node

    def _left_part(
        self,
        partial: str,
        node: DAWGNode,
        anchor_pos: int,
        limit: int,
        line: int,
        direction: Direction,
        cross_checks: list[set[str]],
        tiles_used: list[tuple[int, int, Tile]],
    ) -> None:
        """Generate left parts and try extending right from the anchor."""
        self._extend_right(
            partial, node, anchor_pos, line, direction, cross_checks, tiles_used
        )
        if limit > 0:
            for ch in set(self.available):
                if self.available[ch] > 0 and ch in node.children:
                    self.available[ch] -= 1
                    col_pos = anchor_pos - len(partial) - 1
                    r, c = self._coords(line, col_pos, direction)
                    tile = Tile.from_letter(ch)
                    self._left_part(
                        partial + ch,  # note: built left-to-right but placed right-to-left
                        node.children[ch],
                        anchor_pos,
                        limit - 1,
                        line,
                        direction,
                        cross_checks,
                        tiles_used + [(r, c, tile)],
                    )
                    self.available[ch] += 1

    def _extend_right(
        self,
        partial: str,
        node: DAWGNode,
        pos: int,
        line: int,
        direction: Direction,
        cross_checks: list[set[str]],
        tiles_used: list[tuple[int, int, Tile]],
    ) -> None:
        """Extend the partial word to the right from position pos."""
        if pos >= BOARD_SIZE:
            # Off the board — check if we have a valid word
            if node.is_terminal and len(partial) >= 2 and tiles_used:
                self._record_move(partial, pos, line, direction, tiles_used)
            return

        r, c = self._coords(line, pos, direction)
        tile = self.board.get_tile(r, c)

        if tile is None:
            # Empty square
            if node.is_terminal and len(partial) >= 2 and tiles_used:
                self._record_move(partial, pos, line, direction, tiles_used)
            for ch in set(self.available):
                if (
                    self.available[ch] > 0
                    and ch in node.children
                    and ch in cross_checks[pos]
                ):
                    self.available[ch] -= 1
                    new_tile = Tile.from_letter(ch)
                    self._extend_right(
                        partial + ch,
                        node.children[ch],
                        pos + 1,
                        line,
                        direction,
                        cross_checks,
                        tiles_used + [(r, c, new_tile)],
                    )
                    self.available[ch] += 1
        else:
            # Occupied square — use the existing letter
            letter = tile.blank_letter if tile.is_blank else tile.letter
            if letter in node.children:
                self._extend_right(
                    partial + letter,
                    node.children[letter],
                    pos + 1,
                    line,
                    direction,
                    cross_checks,
                    tiles_used,
                )

    def _record_move(
        self,
        word: str,
        end_pos: int,
        line: int,
        direction: Direction,
        tiles_used: list[tuple[int, int, Tile]],
    ) -> None:
        """Validate and record a complete move."""
        word_len = len(word)
        start_pos = end_pos - word_len
        start_r, start_c = self._coords(line, start_pos, direction)

        # For the empty board, the first move must cross the center square
        if self.board.is_empty():
            if direction == Direction.ACROSS:
                if start_r != 7 or not (start_c <= 7 < start_c + word_len):
                    return
            else:
                if start_c != 7 or not (start_r <= 7 < start_r + word_len):
                    return

        # Place tiles on a temporary board to compute the score
        temp_board = self._make_temp_board(tiles_used)

        placed_positions = [(r, c) for r, c, _ in tiles_used]

        # Collect all words formed
        words_formed = [word]
        cross_dir = (
            Direction.DOWN if direction == Direction.ACROSS else Direction.ACROSS
        )
        for r, c, _ in tiles_used:
            cross_word, _ = temp_board.read_word_at(r, c, cross_dir)
            if len(cross_word) > 1:
                # Validate cross-word
                if not self.dawg.search(cross_word):
                    return  # Invalid cross-word, reject move
                words_formed.append(cross_word)

        total_score = score_word(
            temp_board, word, (start_r, start_c), direction, placed_positions
        )

        self.moves.append(
            Move(
                word=word,
                start=(start_r, start_c),
                direction=direction,
                tiles_placed=tiles_used,
                score=total_score,
                words_formed=words_formed,
            )
        )

    def _make_temp_board(
        self, tiles_used: list[tuple[int, int, Tile]]
    ) -> Board:
        """Create a copy of the board with the new tiles placed."""
        temp = copy.deepcopy(self.board)
        for r, c, tile in tiles_used:
            temp.grid[r][c] = tile
        return temp

    def _find_anchors_in_line(
        self, line: int, direction: Direction
    ) -> set[int]:
        """Find anchor positions along a line (row for ACROSS, col for DOWN)."""
        if self.board.is_empty():
            # Only anchor is center
            if direction == Direction.ACROSS and line == 7:
                return {7}
            elif direction == Direction.DOWN and line == 7:
                return {7}
            return set()

        anchors: set[int] = set()
        for pos in range(BOARD_SIZE):
            r, c = self._coords(line, pos, direction)
            if self.board.is_occupied(r, c):
                continue
            # Check neighbors in ALL directions (not just along the line)
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if self.board.in_bounds(nr, nc) and self.board.is_occupied(nr, nc):
                    anchors.add(pos)
                    break
        return anchors

    @staticmethod
    def _coords(
        line: int, pos: int, direction: Direction
    ) -> tuple[int, int]:
        """Convert (line, position) to (row, col) based on direction."""
        if direction == Direction.ACROSS:
            return line, pos
        return pos, line
