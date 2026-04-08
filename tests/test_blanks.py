"""Tests for blank tile support across all layers."""

import time
from collections import Counter

import pytest

from scrabble_engine.board import BOARD_SIZE, Board, Direction
from scrabble_engine.dawg import DAWG
from scrabble_engine.move_generator import generate_moves
from scrabble_engine.scoring import score_word
from scrabble_engine.tiles import Tile, find_words, find_words_detailed


@pytest.fixture(scope="module")
def dawg():
    return DAWG.from_file("src/scrabble_engine/data/twl06.txt")


# ---------------------------------------------------------------------------
# Tile.blank factory
# ---------------------------------------------------------------------------

class TestTileBlankFactory:
    def test_blank_factory(self):
        t = Tile.blank("S")
        assert t.letter == "?"
        assert t.points == 0
        assert t.is_blank
        assert t.blank_letter == "S"

    def test_blank_factory_lowercase(self):
        t = Tile.blank("s")
        assert t.blank_letter == "S"


# ---------------------------------------------------------------------------
# Rack solver with blanks
# ---------------------------------------------------------------------------

class TestFindWordsWithBlanks:
    def test_blank_finds_more_than_specific_letter(self, dawg):
        """['?', 'A', 'T'] should find strictly more words than ['B', 'A', 'T']
        because the blank can be B and also every other letter."""
        words_blank = set(find_words(["?", "A", "T"], dawg))
        words_bat = set(find_words(["B", "A", "T"], dawg))
        assert words_bat.issubset(words_blank)
        assert len(words_blank) > len(words_bat)

    def test_two_blanks_find_all_two_letter_words(self, dawg):
        """['?', '?'] should find every valid 2-letter word."""
        words = find_words(["?", "?"], dawg)
        # Get all 2-letter words from the dictionary
        all_twos = set()
        node = dawg.root
        for ch1, child1 in node.children.items():
            for ch2, child2 in child1.children.items():
                if child2.is_terminal:
                    all_twos.add(ch1 + ch2)
        # Also single-letter words
        for ch, child in node.children.items():
            if child.is_terminal:
                all_twos.add(ch)
        assert all_twos.issubset(set(words))

    def test_blank_does_not_duplicate_regular(self, dawg):
        """Words found with a regular tile should also appear with a blank,
        not be duplicated in the result."""
        words = find_words(["?", "A", "T"], dawg)
        assert len(words) == len(set(words)), "Duplicate words in find_words result"

    def test_blank_as_q(self, dawg):
        """Blank should be usable as Q to form QI."""
        words = find_words(["?", "I"], dawg)
        assert "QI" in words

    def test_find_words_detailed_shows_blank_positions(self, dawg):
        """find_words_detailed should indicate which positions used a blank."""
        results = find_words_detailed(["?", "A", "T"], dawg)
        assert len(results) > 0

        # Find CAT — blank used as C (position 0)
        cat_results = [r for r in results if r.word == "CAT"]
        assert len(cat_results) >= 1
        # One result should have blank at position 0 (the C)
        blank_at_0 = [r for r in cat_results if 0 in r.blank_positions]
        assert len(blank_at_0) >= 1

    def test_find_words_detailed_no_blank_when_regular_available(self, dawg):
        """When a regular tile covers a letter, no blank needed at that position."""
        results = find_words_detailed(["?", "A", "T"], dawg)
        # "AT" can be formed without using the blank
        at_results = [r for r in results if r.word == "AT"]
        no_blank = [r for r in at_results if len(r.blank_positions) == 0]
        assert len(no_blank) >= 1  # AT without any blank


# ---------------------------------------------------------------------------
# Move generator with blanks
# ---------------------------------------------------------------------------

class TestMoveGeneratorWithBlanks:
    def test_one_blank_generates_valid_moves(self, dawg):
        """Empty board, rack with one blank: all moves should be valid words."""
        board = Board()
        moves = generate_moves(board, ["?", "A", "T", "S", "D", "O", "G"], dawg)
        assert len(moves) > 0
        for m in moves:
            assert dawg.search(m.word), f"Invalid word: {m.word}"

    def test_blank_finds_superset_of_regular(self, dawg):
        """Rack with blank should find everything the regular rack finds, plus more.
        ['?', 'A', 'T', 'S', 'D', 'O', 'G'] >= ['C', 'A', 'T', 'S', 'D', 'O', 'G']
        because blank can be C."""
        board = Board()
        regular = generate_moves(board, ["C", "A", "T", "S", "D", "O", "G"], dawg)
        blank = generate_moves(board, ["?", "A", "T", "S", "D", "O", "G"], dawg)

        regular_words = {m.word for m in regular}
        blank_words = {m.word for m in blank}
        assert regular_words.issubset(blank_words)
        assert len(blank_words) > len(regular_words)

    def test_blank_hook(self, dawg):
        """Board with 'CAT', rack ['?']: should find CATS (blank as S), SCAT, etc."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        moves = generate_moves(board, ["?"], dawg)
        words = {m.word for m in moves}
        assert "CATS" in words  # blank as S appended
        assert "SCAT" in words  # blank as S prepended

    def test_blank_tiles_marked_correctly(self, dawg):
        """Tiles placed as blanks should have is_blank=True and blank_letter set."""
        board = Board()
        moves = generate_moves(board, ["?", "A", "T"], dawg)

        # Find a move that uses the blank
        blank_moves = [
            m for m in moves
            if any(t.is_blank for _, _, t in m.tiles_placed)
        ]
        assert len(blank_moves) > 0

        for m in blank_moves:
            for _, _, t in m.tiles_placed:
                if t.is_blank:
                    assert t.points == 0
                    assert t.blank_letter is not None
                    assert t.blank_letter.isalpha()

    def test_all_cross_words_valid_with_blanks(self, dawg):
        """Every cross-word formed by blank-using moves must be valid."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        moves = generate_moves(board, ["?", "E", "I", "O", "U", "S", "T"], dawg)
        for m in moves:
            for word in m.words_formed:
                assert dawg.search(word), f"Invalid cross-word: {word} in move {m.word}"

    def test_no_duplicate_moves_with_blank(self, dawg):
        """No duplicate moves when accounting for which tiles are blanks.
        The same word at the same position CAN appear multiple times if the
        blank represents different letters — those are distinct plays with
        different tiles on the board. But truly identical tile placements
        (same word, position, direction, and same blank assignments) should
        not occur."""
        board = Board()
        moves = generate_moves(board, ["?", "A", "T", "S", "D", "O", "G"], dawg)

        def move_key(m):
            # Include blank positions to distinguish different blank usages
            blank_info = tuple(
                (r, c, t.is_blank, t.blank_letter) for r, c, t in m.tiles_placed
            )
            return (m.word, m.start, m.direction, blank_info)

        keys = [move_key(m) for m in moves]
        assert len(keys) == len(set(keys)), "Truly duplicate moves detected"


# ---------------------------------------------------------------------------
# Scoring with blanks in move generator
# ---------------------------------------------------------------------------

class TestBlankScoring:
    def test_blank_scores_zero_in_move(self, dawg):
        """A move using a blank should score the blank tile as 0 points.

        Find "CAT" at (7,6) ACROSS with blank as C.
        Regular: C=3, A=1, T=1 = 5, DW(center) → 10
        With blank C: C=0, A=1, T=1 = 2, DW(center) → 4
        """
        board = Board()
        moves = generate_moves(board, ["?", "A", "T"], dawg)

        # Find CAT at (7,6) where the blank is used as C
        cat_moves = [
            m for m in moves
            if m.word == "CAT" and m.start == (7, 6) and m.direction == Direction.ACROSS
        ]
        # There might be multiple — one with blank as C, one with blank as A, etc.
        blank_c_cats = [
            m for m in cat_moves
            if any(t.is_blank and t.blank_letter == "C" for _, _, t in m.tiles_placed)
        ]
        assert len(blank_c_cats) >= 1
        # Blank C=0, A=1, T=1 = 2, center DW → 2*2 = 4
        assert blank_c_cats[0].score == 4

    def test_blank_vs_regular_score_comparison(self, dawg):
        """Same word with blank should score less than with regular tile."""
        board = Board()

        regular_moves = generate_moves(board, ["C", "A", "T"], dawg)
        blank_moves = generate_moves(board, ["?", "A", "T"], dawg)

        # Find CAT at same position in both
        reg_cat = [
            m for m in regular_moves
            if m.word == "CAT" and m.start == (7, 6) and m.direction == Direction.ACROSS
        ]
        blank_cat = [
            m for m in blank_moves
            if m.word == "CAT" and m.start == (7, 6) and m.direction == Direction.ACROSS
            and any(t.is_blank for _, _, t in m.tiles_placed)
        ]
        assert len(reg_cat) == 1
        assert len(blank_cat) >= 1
        assert blank_cat[0].score < reg_cat[0].score

    def test_blank_on_tl_scores_zero(self, dawg):
        """Blank on a TL square: 0 × 3 = 0, not letter_value × 3.

        Place a word where a blank lands on (5,5)=TL.
        """
        board = Board()
        # ZA at (5,5) ACROSS with Z as blank: Z(5,5)=TL, A(5,6)=NONE
        blank_z = Tile.blank("Z")
        a_tile = Tile.from_letter("A")
        placed = board.place_word("ZA", (5, 5), Direction.ACROSS, [blank_z, a_tile])
        # Blank Z on TL: 0 * 3 = 0, A=1 → sum=1, no word mult → 1
        score = score_word(board, "ZA", (5, 5), Direction.ACROSS, placed)
        assert score == 1

    def test_blank_on_board_scores_zero_in_cross_word(self):
        """A blank already on the board should score 0 when it's part of a cross-word.

        Place CAT with blank A at (7,7)=★. Then place "R" below at (8,7) forming "AR" down.
        Cross-word "AR": A(blank)=0(not new), R=1(new, NONE) → sum=1, no word mult → 1.
        """
        board = Board()
        c_tile = Tile.from_letter("C")
        a_blank = Tile.blank("A")
        t_tile = Tile.from_letter("T")
        board.place_word("CAT", (7, 6), Direction.ACROSS, [c_tile, a_blank, t_tile])

        # Now place "R" at (8,7) to form "AR" down through the blank A
        r_tile = Tile.from_letter("R")
        placed = board.place_word("AR", (7, 7), Direction.DOWN, [r_tile])
        # placed = [(8,7)] — A at (7,7) is existing blank

        # Main word "AR" DOWN: A=0(blank, not new), R=1(new, (8,7)=NONE) → 1
        # No cross-words (R at (8,7) has no horizontal neighbors)
        score = score_word(board, "AR", (7, 7), Direction.DOWN, placed)
        assert score == 1


# ---------------------------------------------------------------------------
# Cross-checks with blanks on board
# ---------------------------------------------------------------------------

class TestCrossChecksWithBlanks:
    def test_blank_on_board_constrains_cross_checks(self, dawg):
        """A blank on the board representing 'S' should constrain cross-checks
        as if 'S' is at that position, not as a wildcard."""
        board = Board()
        # Place 'CAT' with A as a blank representing A
        c_tile = Tile.from_letter("C")
        a_blank = Tile.blank("A")
        t_tile = Tile.from_letter("T")
        board.place_word("CAT", (7, 6), Direction.ACROSS, [c_tile, a_blank, t_tile])

        # Cross-checks at (6,7) for ACROSS direction should look at vertical:
        # above (6,7) nothing, below (7,7) = blank-A.
        # Valid letters: those forming a valid 2-letter word ?+A (down)
        checks = board.get_cross_checks(6, 7, Direction.ACROSS, dawg)
        # Words ending in A that are 2 letters: AA, BA, FA, HA, KA, LA, MA, NA, PA, TA, YA, ZA
        assert "A" in checks  # AA is valid
        assert "B" in checks  # BA is valid
        # X+A = XA — not a valid 2-letter word
        # (verify by checking the DAWG)
        if not dawg.search("XA"):
            assert "X" not in checks


# ---------------------------------------------------------------------------
# Board round-trip with blanks
# ---------------------------------------------------------------------------

class TestBoardRoundTripWithBlanks:
    def test_blank_survives_roundtrip(self):
        """Place a word with a blank, to_text, from_text, verify blank preserved."""
        board = Board()
        c_tile = Tile.from_letter("C")
        a_blank = Tile.blank("A")
        t_tile = Tile.from_letter("T")
        board.place_word("CAT", (7, 6), Direction.ACROSS, [c_tile, a_blank, t_tile])

        text = board.to_text()
        # (7,6)=C uppercase, (7,7)=a lowercase (blank), (7,8)=T uppercase
        lines = text.split("\n")
        assert lines[7][6] == "C"
        assert lines[7][7] == "a"  # blank represented as lowercase
        assert lines[7][8] == "T"

        board2 = Board.from_text(text)
        tile_a = board2.get_tile(7, 7)
        assert tile_a.is_blank
        assert tile_a.blank_letter == "A"
        assert tile_a.points == 0

        tile_c = board2.get_tile(7, 6)
        assert not tile_c.is_blank
        assert tile_c.letter == "C"


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

class TestBlankPerformance:
    def test_one_blank_under_10_seconds(self, dawg):
        """6 regular tiles + 1 blank should generate moves in under 10 seconds."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "HELLO"]
        board.place_word("HELLO", (7, 3), Direction.ACROSS, tiles)

        start = time.perf_counter()
        moves = generate_moves(
            board, ["?", "A", "T", "S", "I", "N"], dawg
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0, f"1 blank took {elapsed:.2f}s (limit 10s)"
        assert len(moves) > 0

    def test_two_blanks_under_60_seconds(self, dawg):
        """5 regular tiles + 2 blanks should generate moves in under 60 seconds."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "HELLO"]
        board.place_word("HELLO", (7, 3), Direction.ACROSS, tiles)

        start = time.perf_counter()
        moves = generate_moves(
            board, ["?", "?", "A", "T", "S"], dawg
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 60.0, f"2 blanks took {elapsed:.2f}s (limit 60s)"
        assert len(moves) > 0
