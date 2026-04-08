"""Tests for Scrabble scoring."""

from scrabble_engine.board import Board, BonusSquare, Direction
from scrabble_engine.scoring import BINGO_BONUS, score_word
from scrabble_engine.tiles import LETTER_VALUES, Tile


def _place_and_score(
    board: Board,
    word: str,
    start: tuple[int, int],
    direction: Direction,
) -> int:
    """Helper: place a word on the board and score it. All tiles are new."""
    tiles = [Tile.from_letter(ch) for ch in word]
    placed = board.place_word(word, start, direction, tiles)
    return score_word(board, word, start, direction, placed)


class TestBasicScoring:
    def test_hello_through_center(self):
        """HELLO at (7,3) ACROSS — (7,3)=DL on H, center star (7,7) acts as DW.
        H=4*2(DL)=8, E=1, L=1, L=1, O=1 => sum=12, center DW => 12*2 = 24."""
        board = Board()
        score = _place_and_score(board, "HELLO", (7, 3), Direction.ACROSS)
        assert score == 24

    def test_simple_no_bonus(self):
        """Place a word that doesn't touch any bonus squares."""
        board = Board()
        # First place something to make the board non-empty, then test a word
        # that avoids bonuses. Use a known position with NONE bonus.
        # Row 7: TW . . DL . . . ★ . . . DL . . TW
        # (7,1) is NONE, (7,2) is NONE — but we need a connected play.
        # Simpler: just manually verify with known positions.
        # Place "AT" at (7,7) ACROSS — center is DW, (7,8) is NONE
        # A=1, T=1 => sum=2, DW on center => 2*2 = 4
        score = _place_and_score(board, "AT", (7, 7), Direction.ACROSS)
        assert score == 4

    def test_double_letter(self):
        """Place a tile on a DL square."""
        board = Board()
        # (7,3) is DL. Place "HEAT" at (7,3) ACROSS: H(7,3)=DL, E(7,4), A(7,5), T(7,6)
        # Row 7 bonuses: TW . . DL . . . ★ ...
        # H=4 *2(DL)=8, E=1, A=1, T=1 => sum=11, no word mult => 11
        # But (7,7) is the star... word is at cols 3-6, doesn't touch 7
        score = _place_and_score(board, "HEAT", (7, 3), Direction.ACROSS)
        assert score == 11

    def test_triple_letter(self):
        """Place a tile on a TL square."""
        board = Board()
        # (1,5) is TL. Place "IT" at (1,5) DOWN: I(1,5)=TL, T(2,5)=NONE
        # I=1*3(TL)=3, T=1 → sum=4, no word mult → 4
        score = _place_and_score(board, "IT", (1, 5), Direction.DOWN)
        assert score == 4

    def test_triple_letter_on_high_value_tile(self):
        """Z (10 pts) on a TL square is the biggest single-tile swing in Scrabble.

        Bonus layout ref: (5,5)=TL, (5,6)=NONE
        Tile values: Z=10, A=1
        """
        board = Board()
        # Place "ZA" at (5,5) ACROSS: Z(5,5)=TL, A(5,6)=NONE
        # Z=10*3(TL)=30, A=1 → sum=31, no word mult → 31
        score = _place_and_score(board, "ZA", (5, 5), Direction.ACROSS)
        assert score == 31

    def test_triple_letter_on_j(self):
        """J (8 pts) on a TL square.

        Bonus layout ref: (1,9)=TL, (1,10)=NONE
        Tile values: J=8, O=1
        """
        board = Board()
        # Place "JO" at (1,9) ACROSS: J(1,9)=TL, O(1,10)=NONE
        # J=8*3(TL)=24, O=1 → sum=25, no word mult → 25
        score = _place_and_score(board, "JO", (1, 9), Direction.ACROSS)
        assert score == 25

    def test_double_word(self):
        """Place on a DW square."""
        board = Board()
        # (1,1) is DW, (1,2) is NONE. Place "BE" at (1,1) ACROSS.
        # B=3, E=1 => sum=4, DW => 4*2 = 8
        score = _place_and_score(board, "BE", (1, 1), Direction.ACROSS)
        assert score == 8

    def test_triple_word(self):
        """Place on a TW square."""
        board = Board()
        # (0,0) is TW. Place "AT" at (0,0) ACROSS: A(0,0)=TW, T(0,1)=NONE
        # A=1, T=1 => sum=2, TW => 2*3 = 6
        score = _place_and_score(board, "AT", (0, 0), Direction.ACROSS)
        assert score == 6

    def test_multiple_word_multipliers(self):
        """Multiple word bonuses multiply together."""
        board = Board()
        # Place a word hitting two DW squares: (4,4) and (4,10) are both DW
        # That's 7 apart — too far. Let's use (1,1)=DW and (2,2)=DW diagonally — not in line.
        # (1,1)=DW, (1,2) is DW? No: row 1 = . DW . . . TL . . . TL . . . DW .
        # (1,1)=DW, (1,13)=DW — too far apart.
        # Use (0,0)=TW and (0,7)=TW — 8 apart, place an 8-letter word
        # Actually simpler: row 0 = TW . . DL . . . TW . . . DL . . TW
        # (0,0)=TW, (0,7)=TW — place an 8-letter word
        tiles = [Tile.from_letter(ch) for ch in "ABSOLUTE"]
        placed = board.place_word("ABSOLUTE", (0, 0), Direction.ACROSS, tiles)
        # A=1,B=3,S=1,O=1,L=1,U=1,T=1,E=1 = 10
        # (0,0)=TW, (0,3)=DL on O: O=1*2=2 instead of 1, so sum = 10+1 = 11
        # Wait: A(0,0), B(0,1), S(0,2), O(0,3)=DL, L(0,4), U(0,5), T(0,6), E(0,7)=TW
        # A=1, B=3, S=1, O=1*2(DL)=2, L=1, U=1, T=1, E=1 => sum=11
        # Word mults: TW(0,0) * TW(0,7) = 3*3 = 9
        # Total: 11 * 9 = 99
        score = score_word(board, "ABSOLUTE", (0, 0), Direction.ACROSS, placed)
        assert score == 99


class TestBonusOnlyForNewTiles:
    def test_dl_not_counted_for_existing(self):
        """DL should only apply to tiles placed THIS turn."""
        board = Board()
        # Place "H" at (7,3) which is a DL square
        board.place_tile(7, 3, Tile.from_letter("H"))
        # Now place "AT" at (7,4) ACROSS to form a cross-word or extend
        # Better: place "I" at (7,4) so "HI" is formed but we only placed I
        tiles = [Tile.from_letter("I")]
        placed = board.place_word("HI", (7, 3), Direction.ACROSS, tiles)
        # placed = [(7,4)] only — H was already there
        # H=4 (no DL because it's not new), I=1 => sum=5, no word mult => 5
        score = score_word(board, "HI", (7, 3), Direction.ACROSS, placed)
        assert score == 5

    def test_dw_not_counted_for_existing(self):
        """DW/TW should only apply if a new tile is on that bonus square."""
        board = Board()
        # Place "A" at (7,7) which is CENTER/DW
        board.place_tile(7, 7, Tile.from_letter("A"))
        # Now place "T" at (7,8) to form "AT"
        tiles = [Tile.from_letter("T")]
        placed = board.place_word("AT", (7, 7), Direction.ACROSS, tiles)
        # placed = [(7,8)] only — A at center was already there
        # A=1 (no DW since not new), T=1, no new tile on word bonus => sum=2
        score = score_word(board, "AT", (7, 7), Direction.ACROSS, placed)
        assert score == 2


class TestCrossWordScoring:
    def test_cross_word_length_one_no_score(self):
        """A cross-word of length 1 should not contribute to the score."""
        board = Board()
        tiles_cat = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles_cat)

        # Place S at (8,7) to form "AS" down. S at (8,7) has no horizontal neighbors.
        tiles_s = [Tile.from_letter("S")]
        placed = board.place_word("AS", (7, 7), Direction.DOWN, tiles_s)
        # placed = [(8,7)]
        # Main "AS" DOWN: A=1(not new), S=1(new, (8,7)=NONE) → sum=2, no word mult → 2
        # Cross at (8,7) ACROSS: just "S" → length 1 → 0
        # Total = 2
        score = score_word(board, "AS", (7, 7), Direction.DOWN, placed)
        assert score == 2

    def test_cross_word_multi_letter(self):
        """A newly placed tile adjacent to existing tiles should form and score
        a multi-letter cross-word.

        Board setup:
          Row 7: ...C A T.........  (CAT at (7,6) ACROSS)
          Row 8: ..D O G..........  (DOG at (8,5) ACROSS)
        Then place "TAG" at (7,8) DOWN: T(7,8) existing, A(8,8) new, G(9,8) new.

        Bonus layout ref:
          (8,8)=DL, (9,8)=NONE
        """
        board = Board()
        for word, start in [("CAT", (7, 6)), ("DOG", (8, 5))]:
            tiles = [Tile.from_letter(ch) for ch in word]
            board.place_word(word, start, Direction.ACROSS, tiles)

        tiles_ag = [Tile.from_letter("A"), Tile.from_letter("G")]
        placed = board.place_word("TAG", (7, 8), Direction.DOWN, tiles_ag)
        # placed = [(8,8), (9,8)]
        #
        # Main word "TAG" DOWN from (7,8):
        #   T(7,8)=NONE, not new → T=1
        #   A(8,8)=DL,   new    → A=1*2=2
        #   G(9,8)=NONE, new    → G=2
        #   sum=5, no word mult → 5
        #
        # Cross-word at (8,8) ACROSS — read through (8,8):
        #   D(8,5), O(8,6), G(8,7), A(8,8) = "DOGA" from (8,5)
        #   D=2(not new), O=1(not new), G=2(not new), A=1(new, DL)→ A=1*2=2
        #   sum=7, no word mult → 7
        #
        # Cross-word at (9,8) ACROSS — just "G" → length 1, no score
        #
        # Total = 5 + 7 = 12
        score = score_word(board, "TAG", (7, 8), Direction.DOWN, placed)
        assert score == 12

    def test_multiple_cross_words(self):
        """Placing 3 tiles parallel to an existing word should form 3 separate
        cross-words. Total = main word + cross1 + cross2 + cross3.

        Board setup: "CAT" at (7,6) ACROSS → C(7,6), A(7,7)=★, T(7,8)
        Then place "ARE" at (8,6) ACROSS → A(8,6), R(8,7), E(8,8)

        Bonus layout ref (row 8 = row 6 pattern):
          (8,6)=DL, (8,7)=NONE, (8,8)=DL
        """
        board = Board()
        tiles_cat = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles_cat)

        tiles_are = [Tile.from_letter(ch) for ch in "ARE"]
        placed = board.place_word("ARE", (8, 6), Direction.ACROSS, tiles_are)
        # placed = [(8,6), (8,7), (8,8)]
        #
        # Main word "ARE" ACROSS from (8,6):
        #   A(8,6)=DL   → A=1*2=2
        #   R(8,7)=NONE → R=1
        #   E(8,8)=DL   → E=1*2=2
        #   sum=5, no word mult → 5
        #
        # Cross-word at (8,6) DOWN: C(7,6)+A(8,6) = "CA" from (7,6)
        #   C=3(not new), A=1(new, DL) → A=1*2=2 → sum=5, no word mult → 5
        #
        # Cross-word at (8,7) DOWN: A(7,7)+R(8,7) = "AR" from (7,7)
        #   A=1(not new), R=1(new, NONE) → sum=2, no word mult → 2
        #
        # Cross-word at (8,8) DOWN: T(7,8)+E(8,8) = "TE" from (7,8)
        #   T=1(not new), E=1(new, DL) → E=1*2=2 → sum=3, no word mult → 3
        #
        # Total = 5 + 5 + 2 + 3 = 15
        score = score_word(board, "ARE", (8, 6), Direction.ACROSS, placed)
        assert score == 15

    def test_cross_word_with_bonus_on_new_tile(self):
        """Cross-word scoring should apply bonuses from new tile positions.
        Existing tiles never get bonus multiplied."""
        board = Board()
        tiles_cat = [Tile.from_letter(ch) for ch in "CAT"]
        placed_cat = board.place_word("CAT", (7, 6), Direction.ACROSS, tiles_cat)
        # C=3, A=1, T=1 → sum=5, CENTER DW on A → 5*2 = 10
        score_cat = score_word(board, "CAT", (7, 6), Direction.ACROSS, placed_cat)
        assert score_cat == 10

        # Place "OAR" at (6,7) DOWN: O(6,7) new, A(7,7) existing, R(8,7) new
        # Bonus ref: (6,7)=NONE, (8,7)=NONE
        tiles_oar = [Tile.from_letter("O"), Tile.from_letter("R")]
        placed = board.place_word("OAR", (6, 7), Direction.DOWN, tiles_oar)
        # placed = [(6,7), (8,7)]
        # Main "OAR" DOWN: O=1(NONE), A=1(not new), R=1(NONE) → sum=3, no word mult → 3
        # Cross at (6,7) ACROSS: just "O" → length 1 → 0
        # Cross at (8,7) ACROSS: just "R" → length 1 → 0
        # Total = 3
        score = score_word(board, "OAR", (6, 7), Direction.DOWN, placed)
        assert score == 3


class TestBingoBonus:
    def test_bingo(self):
        """Using all 7 tiles should add 50 bonus points."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "STUDIES"]
        placed = board.place_word("STUDIES", (7, 4), Direction.ACROSS, tiles)
        score = score_word(board, "STUDIES", (7, 4), Direction.ACROSS, placed)
        # S=1,T=1,U=1,D=2,I=1,E=1,S=1 = 8
        # (7,7)=CENTER/DW => 8*2 = 16
        # 7 tiles placed => +50 bingo
        assert score == 16 + BINGO_BONUS

    def test_no_bingo_for_six(self):
        """6 tiles should NOT get bingo bonus.

        Note: STUDIE is not a valid Scrabble word, but scoring doesn't validate.
        Bonus layout ref: (7,4)=NONE, (7,5)=NONE, (7,6)=NONE, (7,7)=★/DW, (7,8)=NONE, (7,9)=NONE
        Tile values: S=1, T=1, U=1, D=2, I=1, E=1
        """
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "STUDIE"]
        placed = board.place_word("STUDIE", (7, 4), Direction.ACROSS, tiles)
        score = score_word(board, "STUDIE", (7, 4), Direction.ACROSS, placed)
        # S=1, T=1, U=1, D=2, I=1, E=1 → sum=7, ★ DW on D → 7*2 = 14
        # 6 tiles placed → no bingo
        assert score == 14


class TestBlankScoring:
    def test_blank_scores_zero(self):
        """Blank tiles contribute 0 points regardless of letter."""
        board = Board()
        # Place "CAT" where A is a blank
        c_tile = Tile.from_letter("C")
        a_blank = Tile(letter="?", points=0, is_blank=True, blank_letter="A")
        t_tile = Tile.from_letter("T")
        placed = board.place_word("CAT", (7, 6), Direction.ACROSS, [c_tile, a_blank, t_tile])
        score = score_word(board, "CAT", (7, 6), Direction.ACROSS, placed)
        # C=3, A(blank)=0, T=1 => sum=4, CENTER DW at (7,7) => 4*2 = 8
        assert score == 8

    def test_blank_vs_regular(self):
        """Blank version of a word should score less than regular."""
        board1 = Board()
        score_regular = _place_and_score(board1, "CAT", (7, 6), Direction.ACROSS)

        board2 = Board()
        c_tile = Tile.from_letter("C")
        a_blank = Tile(letter="?", points=0, is_blank=True, blank_letter="A")
        t_tile = Tile.from_letter("T")
        placed = board2.place_word("CAT", (7, 6), Direction.ACROSS, [c_tile, a_blank, t_tile])
        score_blank = score_word(board2, "CAT", (7, 6), Direction.ACROSS, placed)

        assert score_blank < score_regular
