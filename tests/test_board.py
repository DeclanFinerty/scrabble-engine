"""Tests for the Board class."""

import pytest

from scrabble_engine.board import BOARD_SIZE, Board, BonusSquare, Direction
from scrabble_engine.dawg import DAWG
from scrabble_engine.tiles import Tile


class TestBoardInit:
    def test_empty_board(self):
        board = Board()
        assert board.is_empty()
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                assert board.get_tile(r, c) is None
                assert not board.is_occupied(r, c)

    def test_bonus_layout(self):
        board = Board()
        # Corners are triple word
        assert board.bonus[0][0] == BonusSquare.TRIPLE_WORD
        assert board.bonus[0][14] == BonusSquare.TRIPLE_WORD
        assert board.bonus[14][0] == BonusSquare.TRIPLE_WORD
        assert board.bonus[14][14] == BonusSquare.TRIPLE_WORD
        # Center is star
        assert board.bonus[7][7] == BonusSquare.CENTER
        # A known DL
        assert board.bonus[0][3] == BonusSquare.DOUBLE_LETTER
        # A known TL
        assert board.bonus[1][5] == BonusSquare.TRIPLE_LETTER
        # A known DW
        assert board.bonus[1][1] == BonusSquare.DOUBLE_WORD

    def test_bonus_symmetry(self):
        """Board bonuses should be symmetric across both axes."""
        board = Board()
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                # Horizontal symmetry
                assert board.bonus[r][c] == board.bonus[r][14 - c]
                # Vertical symmetry
                assert board.bonus[r][c] == board.bonus[14 - r][c]


class TestPlaceTile:
    def test_place_single(self):
        board = Board()
        tile = Tile.from_letter("A")
        board.place_tile(7, 7, tile)
        assert board.is_occupied(7, 7)
        assert board.get_tile(7, 7).letter == "A"
        assert not board.is_empty()

    def test_place_out_of_bounds(self):
        board = Board()
        with pytest.raises(ValueError, match="out of bounds"):
            board.place_tile(15, 0, Tile.from_letter("A"))

    def test_place_occupied(self):
        board = Board()
        board.place_tile(7, 7, Tile.from_letter("A"))
        with pytest.raises(ValueError, match="already occupied"):
            board.place_tile(7, 7, Tile.from_letter("B"))


class TestPlaceWord:
    def test_place_across(self):
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "HELLO"]
        placed = board.place_word("HELLO", (7, 3), Direction.ACROSS, tiles)
        assert len(placed) == 5
        assert board.get_tile(7, 3).letter == "H"
        assert board.get_tile(7, 7).letter == "O"

    def test_place_down(self):
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "HELLO"]
        placed = board.place_word("HELLO", (3, 7), Direction.DOWN, tiles)
        assert len(placed) == 5
        assert board.get_tile(3, 7).letter == "H"
        assert board.get_tile(7, 7).letter == "O"

    def test_place_through_existing(self):
        """Placing a word that overlaps an existing tile should skip it."""
        board = Board()
        board.place_tile(7, 7, Tile.from_letter("L"))
        # Place "HELLO" across — the L at (7,7) is at index 4 of the word starting at (7,3)
        # H=3, E=4, L=5, L=6, O=7 — wait, let me recalculate
        # "HELLO" at (7,5): H=5, E=6, L=7, L=8, O=9
        # The L at (7,7) matches index 2 of "HELLO"
        tiles = [Tile.from_letter(ch) for ch in "HELO"]  # only 4 tiles needed
        placed = board.place_word("HELLO", (7, 5), Direction.ACROSS, tiles)
        assert len(placed) == 4  # L at (7,7) was already there
        assert board.get_tile(7, 5).letter == "H"
        assert board.get_tile(7, 7).letter == "L"  # existing

    def test_place_conflict(self):
        """Placing a word that conflicts with existing tile should raise."""
        board = Board()
        board.place_tile(7, 7, Tile.from_letter("X"))
        tiles = [Tile.from_letter(ch) for ch in "HELLO"]
        with pytest.raises(ValueError, match="Conflict"):
            board.place_word("HELLO", (7, 3), Direction.ACROSS, tiles)

    def test_place_out_of_bounds(self):
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "HELLO"]
        with pytest.raises(ValueError, match="out of bounds"):
            board.place_word("HELLO", (7, 12), Direction.ACROSS, tiles)


class TestAnchorSquares:
    def test_empty_board(self):
        board = Board()
        anchors = board.get_anchor_squares()
        assert anchors == [(7, 7)]

    def test_after_first_word(self):
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)
        anchors = board.get_anchor_squares()
        # Should include squares adjacent to C, A, T but not the tiles themselves
        assert (7, 5) in anchors   # left of C
        assert (7, 9) in anchors   # right of T
        assert (6, 6) in anchors   # above C
        assert (8, 7) in anchors   # below A
        # Should NOT include occupied squares
        assert (7, 6) not in anchors
        assert (7, 7) not in anchors
        assert (7, 8) not in anchors


class TestCrossChecks:
    @pytest.fixture
    def dawg(self):
        return DAWG.from_file("src/scrabble_engine/data/twl06.txt")

    def test_no_constraints(self, dawg):
        """Empty board — all letters valid everywhere."""
        board = Board()
        checks = board.get_cross_checks(7, 7, Direction.ACROSS, dawg)
        assert checks == set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    def test_with_perpendicular_tiles(self, dawg):
        """Place 'A' above and 'T' below — only letters forming valid 3-letter
        words _A_T_ pattern should be in cross checks."""
        board = Board()
        board.place_tile(6, 7, Tile.from_letter("C"))
        board.place_tile(8, 7, Tile.from_letter("T"))
        # For ACROSS direction at (7,7), perpendicular is DOWN
        # Cross-word would be C + ? + T — valid letters form 3-letter words C?T
        checks = board.get_cross_checks(7, 7, Direction.ACROSS, dawg)
        # CAT, COT, CUT are valid — A, O, U should be in checks
        assert "A" in checks  # CAT
        assert "O" in checks  # COT
        assert "U" in checks  # CUT
        # CXT is not a word
        assert "X" not in checks

    def test_occupied_square(self, dawg):
        """Cross checks for an occupied square should be empty."""
        board = Board()
        board.place_tile(7, 7, Tile.from_letter("A"))
        checks = board.get_cross_checks(7, 7, Direction.ACROSS, dawg)
        assert checks == set()


class TestReadWordAt:
    def test_read_across(self):
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "HELLO"]
        board.place_word("HELLO", (7, 3), Direction.ACROSS, tiles)
        word, start = board.read_word_at(7, 5, Direction.ACROSS)
        assert word == "HELLO"
        assert start == (7, 3)

    def test_read_down(self):
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "HELLO"]
        board.place_word("HELLO", (3, 7), Direction.DOWN, tiles)
        word, start = board.read_word_at(5, 7, Direction.DOWN)
        assert word == "HELLO"
        assert start == (3, 7)

    def test_single_tile(self):
        board = Board()
        board.place_tile(7, 7, Tile.from_letter("A"))
        word, start = board.read_word_at(7, 7, Direction.ACROSS)
        assert word == "A"
        assert start == (7, 7)


class TestTextIO:
    def test_roundtrip_empty(self):
        board = Board()
        text = board.to_text()
        assert text.count(".") == 225
        board2 = Board.from_text(text)
        assert board2.is_empty()

    def test_roundtrip_with_tiles(self):
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "HELLO"]
        board.place_word("HELLO", (7, 3), Direction.ACROSS, tiles)
        text = board.to_text()
        board2 = Board.from_text(text)
        assert board2.get_tile(7, 3).letter == "H"
        assert board2.get_tile(7, 7).letter == "O"
        assert board2.get_tile(7, 8) is None

    def test_roundtrip_with_blanks(self):
        board = Board()
        blank = Tile(letter="?", points=0, is_blank=True, blank_letter="S")
        board.place_tile(7, 7, blank)
        text = board.to_text()
        assert text.split("\n")[7][7] == "s"  # lowercase for blank
        board2 = Board.from_text(text)
        tile = board2.get_tile(7, 7)
        assert tile.is_blank
        assert tile.blank_letter == "S"
        assert tile.points == 0

    def test_from_text_vision_format(self):
        """Test the scrabble-vision integration format from the spec."""
        grid = (
            "...............\n"
            "...............\n"
            "...............\n"
            ".....HELLO.....\n"
            ".........E.....\n"
            ".........A.....\n"
            ".........R.....\n"
            ".........N.....\n"
            "...............\n"
            "...............\n"
            "...............\n"
            "...............\n"
            "...............\n"
            "...............\n"
            "..............."
        )
        board = Board.from_text(grid)
        assert board.get_tile(3, 5).letter == "H"
        assert board.get_tile(3, 9).letter == "O"
        assert board.get_tile(7, 9).letter == "N"

    def test_from_text_wrong_size(self):
        with pytest.raises(ValueError, match="Expected 15 lines"):
            Board.from_text("...\n...\n...")
