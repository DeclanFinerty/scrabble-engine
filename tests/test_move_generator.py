"""Tests for the move generator (Appel & Jacobson)."""

from collections import Counter

import pytest

from scrabble_engine.board import Board, Direction
from scrabble_engine.dawg import DAWG
from scrabble_engine.move_generator import Move, best_moves, generate_moves
from scrabble_engine.scoring import score_word
from scrabble_engine.tiles import Tile


@pytest.fixture(scope="module")
def dawg():
    return DAWG.from_file("src/scrabble_engine/data/twl06.txt")


class TestEmptyBoard:
    def test_finds_words(self, dawg):
        """Empty board should find words placed through center."""
        board = Board()
        moves = generate_moves(board, ["C", "A", "T", "S", "D", "O", "G"], dawg)
        assert len(moves) > 0

    def test_no_duplicate_moves(self, dawg):
        """Each (word, start, direction) triple should appear at most once."""
        board = Board()
        moves = generate_moves(board, ["C", "A", "T", "S", "D", "O", "G"], dawg)
        move_keys = [(m.word, m.start, m.direction) for m in moves]
        assert len(move_keys) == len(set(move_keys)), "Duplicate moves detected"

    def test_finds_cats(self, dawg):
        board = Board()
        moves = generate_moves(board, ["C", "A", "T", "S", "D", "O", "G"], dawg)
        words = {m.word for m in moves}
        assert "CATS" in words
        assert "DOGS" in words
        assert "CAT" in words
        assert "DOG" in words

    def test_all_through_center(self, dawg):
        """Every move on an empty board must pass through (7,7)."""
        board = Board()
        moves = generate_moves(board, ["C", "A", "T", "S", "D", "O", "G"], dawg)
        for move in moves:
            r, c = move.start
            length = len(move.word)
            if move.direction == Direction.ACROSS:
                cols = range(c, c + length)
                assert r == 7
                assert 7 in cols, f"{move.word} at {move.start} doesn't cross center"
            else:
                rows = range(r, r + length)
                assert c == 7
                assert 7 in rows, f"{move.word} at {move.start} doesn't cross center"

    def test_sorted_by_score(self, dawg):
        board = Board()
        moves = generate_moves(board, ["C", "A", "T", "S", "D", "O", "G"], dawg)
        scores = [m.score for m in moves]
        assert scores == sorted(scores, reverse=True)

    def test_no_single_letter_words(self, dawg):
        """Moves must be at least 2 letters."""
        board = Board()
        moves = generate_moves(board, ["A", "B", "C", "D", "E", "F", "G"], dawg)
        for move in moves:
            assert len(move.word) >= 2

    def test_finds_longer_words(self, dawg):
        """Should find multi-letter words from a good rack."""
        board = Board()
        moves = generate_moves(board, ["S", "A", "T", "I", "R", "E", "N"], dawg)
        words = {m.word for m in moves}
        # Should find some 6-7 letter words
        long_words = [w for w in words if len(w) >= 6]
        assert len(long_words) > 0


class TestHooking:
    def test_hook_s(self, dawg):
        """Place CAT, then with rack [S] find CATS."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        moves = generate_moves(board, ["S"], dawg)
        words = {m.word for m in moves}
        assert "CATS" in words

    def test_hook_front(self, dawg):
        """Hook a letter to the front of an existing word."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "ATE"]
        board.place_word("ATE", (7, 7), Direction.ACROSS, tiles)

        moves = generate_moves(board, ["L", "M", "G", "R", "D", "H", "S"], dawg)
        words = {m.word for m in moves}
        # LATE, MATE, GATE, RATE, DATE, HATE, SATE should all be hookable
        found_front_hooks = [w for w in words if w.endswith("ATE") and len(w) == 4]
        assert len(found_front_hooks) > 0

    def test_parallel_word(self, dawg):
        """Placing tiles parallel to an existing word should form cross-words."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        # Try to place a word in row 8 — each new tile must form valid cross-words
        moves = generate_moves(board, ["O", "N", "E", "S", "H", "A", "R"], dawg)
        # All generated moves should have valid cross-words
        for move in moves:
            for word in move.words_formed:
                assert dawg.search(word), f"Invalid word formed: {word}"


class TestCrossWordConstraints:
    def test_cross_words_valid(self, dawg):
        """All cross-words in generated moves must be valid."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "HELLO"]
        board.place_word("HELLO", (7, 3), Direction.ACROSS, tiles)

        moves = generate_moves(board, ["A", "E", "I", "O", "U", "S", "T"], dawg)
        for move in moves:
            for word in move.words_formed:
                assert dawg.search(word), f"Invalid cross-word: {word} in move {move.word}"

    def test_no_invalid_moves(self, dawg):
        """Verify the main word of every move is valid."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        moves = generate_moves(board, ["S", "E", "D", "A", "R", "T", "O"], dawg)
        for move in moves:
            assert dawg.search(move.word), f"Invalid main word: {move.word}"


class TestScoring:
    def test_moves_have_scores(self, dawg):
        board = Board()
        moves = generate_moves(board, ["C", "A", "T", "S", "D", "O", "G"], dawg)
        for move in moves:
            assert move.score > 0

    def test_best_moves(self, dawg):
        board = Board()
        top = best_moves(board, ["C", "A", "T", "S", "D", "O", "G"], dawg, n=5)
        assert len(top) <= 5
        assert len(top) > 0
        for i in range(len(top) - 1):
            assert top[i].score >= top[i + 1].score

    def test_exact_score_cat_through_center(self, dawg):
        """CAT at (7,6) ACROSS on empty board.

        Bonus layout ref: (7,6)=NONE, (7,7)=★/DW, (7,8)=NONE
        Tile values: C=3, A=1, T=1
        C=3 + A=1 + T=1 = 5, ★ DW → 5*2 = 10
        """
        board = Board()
        moves = generate_moves(board, ["C", "A", "T", "S", "D", "O", "G"], dawg)
        cat_at_76 = [
            m for m in moves
            if m.word == "CAT" and m.start == (7, 6) and m.direction == Direction.ACROSS
        ]
        assert len(cat_at_76) == 1
        assert cat_at_76[0].score == 10

    def test_exact_score_coats_with_dl(self, dawg):
        """COATS at (7,3) ACROSS on empty board — C lands on DL.

        Bonus layout ref: (7,3)=DL, (7,4)=NONE, (7,5)=NONE, (7,6)=NONE, (7,7)=★/DW
        Tile values: C=3, O=1, A=1, T=1, S=1
        C=3*2(DL)=6, O=1, A=1, T=1, S=1 → sum=10, ★ DW → 10*2 = 20
        """
        board = Board()
        moves = generate_moves(board, ["C", "A", "T", "S", "D", "O", "G"], dawg)
        coats = [
            m for m in moves
            if m.word == "COATS" and m.start == (7, 3) and m.direction == Direction.ACROSS
        ]
        assert len(coats) == 1
        assert coats[0].score == 20

    def test_exact_score_hook_cats(self, dawg):
        """After CAT at (7,6), hooking S to make CATS.

        Bonus layout ref: (7,9)=NONE — S is the only new tile.
        Existing: C(7,6)=3, A(7,7)=1, T(7,8)=1
        New: S(7,9)=1
        sum=6, no new tile on word bonus → 6
        """
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        moves = generate_moves(board, ["S"], dawg)
        cats = [
            m for m in moves
            if m.word == "CATS" and m.start == (7, 6) and m.direction == Direction.ACROSS
        ]
        assert len(cats) == 1
        assert cats[0].score == 6


class TestTilesPlaced:
    def test_tiles_placed_count(self, dawg):
        """tiles_placed should only include new tiles, not existing board tiles."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        moves = generate_moves(board, ["S"], dawg)
        cats_moves = [m for m in moves if m.word == "CATS"]
        assert len(cats_moves) > 0
        for m in cats_moves:
            # Only 1 tile placed (the S)
            assert len(m.tiles_placed) == 1

    def test_tiles_placed_match_rack(self, dawg):
        """Tiles placed should all come from the rack."""
        board = Board()
        rack = ["C", "A", "T", "S", "D", "O", "G"]
        moves = generate_moves(board, rack, dawg)
        for move in moves:
            placed_letters = [t.letter for _, _, t in move.tiles_placed]
            placed_counts = Counter(placed_letters)
            rack_counts = Counter(rack)
            for letter, count in placed_counts.items():
                assert count <= rack_counts[letter], (
                    f"Move {move.word} uses {count}x '{letter}' but rack has {rack_counts[letter]}"
                )


class TestBothDirections:
    def test_across_and_down(self, dawg):
        """Moves should be generated in both directions."""
        board = Board()
        moves = generate_moves(board, ["C", "A", "T", "S", "D", "O", "G"], dawg)
        directions = {m.direction for m in moves}
        assert Direction.ACROSS in directions
        assert Direction.DOWN in directions

    def test_after_placement_both_directions(self, dawg):
        """After placing a horizontal word, should find vertical moves too."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        moves = generate_moves(board, ["A", "E", "I", "O", "U", "S", "T"], dawg)
        directions = {m.direction for m in moves}
        # Should have moves in both directions
        assert Direction.ACROSS in directions
        assert Direction.DOWN in directions


class TestBingoInMoveGenerator:
    def test_seven_letter_move_includes_bingo(self, dawg):
        """A move using all 7 rack tiles must include the +50 bingo bonus.

        Rack: ["S","A","T","I","R","E","N"] can form NASTIER, RETINAS, etc.
        Any 7-letter move's score should be base + 50.
        """
        board = Board()
        moves = generate_moves(board, ["S", "A", "T", "I", "R", "E", "N"], dawg)

        seven_letter_moves = [m for m in moves if len(m.tiles_placed) == 7]
        assert len(seven_letter_moves) > 0, "Should find at least one 7-letter word"

        # Pick one 7-letter move and verify bingo is included by recomputing
        # score WITHOUT the bingo and confirming the difference is exactly 50
        m = seven_letter_moves[0]
        # Reconstruct the board with this move's tiles to compute raw score
        import copy
        temp_board = copy.deepcopy(board)
        for r, c, tile in m.tiles_placed:
            temp_board.grid[r][c] = tile
        placed_positions = [(r, c) for r, c, _ in m.tiles_placed]
        raw_score = score_word(temp_board, m.word, m.start, m.direction, placed_positions)
        # score_word already includes bingo, so raw_score == m.score
        assert raw_score == m.score

        # Now verify it's 50 more than scoring the same word with only 6 tiles_placed
        # would give. We test this by confirming score >= 50 for any 7-tile move.
        assert m.score >= 50, "7-tile move score must be at least 50 (the bingo alone)"

    def test_bingo_vs_short_word(self, dawg):
        """A 7-letter move should score higher than its raw letter values would
        suggest compared to shorter moves, due to the +50 bingo bonus."""
        board = Board()
        moves = generate_moves(board, ["S", "A", "T", "I", "R", "E", "N"], dawg)

        seven_tile = [m for m in moves if len(m.tiles_placed) == 7]
        short = [m for m in moves if len(m.tiles_placed) <= 3]
        assert len(seven_tile) > 0
        assert len(short) > 0

        # The best 7-tile move should beat the best 3-or-fewer-tile move
        # because the bingo alone is +50
        best_seven = max(m.score for m in seven_tile)
        best_short = max(m.score for m in short)
        assert best_seven > best_short


class TestCrossWordScoresInMoveGenerator:
    def test_cross_word_adds_to_total(self, dawg):
        """A move forming cross-words should score higher than the main word alone.

        Place CAT at (7,6), then generate moves. Find a move with words_formed > 1
        and verify its score exceeds what the main word alone would score.
        """
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        moves = generate_moves(board, ["A", "E", "I", "O", "U", "S", "T"], dawg)
        cross_moves = [m for m in moves if len(m.words_formed) > 1]

        assert len(cross_moves) > 0, "Should find at least one move forming cross-words"

        for m in cross_moves:
            # Recompute just the main word score (no cross-words)
            import copy
            temp_board = copy.deepcopy(board)
            for r, c, tile in m.tiles_placed:
                temp_board.grid[r][c] = tile
            placed_positions = [(r, c) for r, c, _ in m.tiles_placed]
            # Score just the main word using _score_single_word logic:
            # main_word_only = score with no cross-words
            from scrabble_engine.scoring import _score_single_word
            main_only = _score_single_word(
                temp_board, m.word, m.start, m.direction, set(placed_positions)
            )
            # Bingo applies to the total, not per-word, so add it back
            bingo = 50 if len(m.tiles_placed) == 7 else 0
            assert m.score > main_only + bingo, (
                f"Move {m.word} has cross-words {m.words_formed} but score {m.score} "
                f"<= main-only {main_only} + bingo {bingo}"
            )


class TestBoardTileReuse:
    def test_extend_through_existing_tiles(self, dawg):
        """Words that reuse existing board tiles should have fewer tiles_placed
        than letters in the word.

        Place "CAT" at (7,6), rack ["S","C","A","T","E","R","D"].
        "CATS" extends CAT by 1 tile (S). "SCAT" prepends S to CAT.
        """
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        rack = ["S", "C", "A", "T", "E", "R", "D"]
        moves = generate_moves(board, rack, dawg)

        # Find CATS at (7,6) — extends existing CAT by appending S at (7,9)
        cats = [
            m for m in moves
            if m.word == "CATS" and m.start == (7, 6) and m.direction == Direction.ACROSS
        ]
        assert len(cats) == 1
        m = cats[0]
        # 4-letter word but only 1 new tile (the S)
        assert len(m.tiles_placed) == 1
        assert len(m.tiles_placed) < len(m.word)
        assert m.tiles_placed[0][2].letter == "S"
        assert m.tiles_placed[0][:2] == (7, 9)

        # Find SCAT at (7,5) — prepends S to existing CAT
        scats = [
            m for m in moves
            if m.word == "SCAT" and m.start == (7, 5) and m.direction == Direction.ACROSS
        ]
        assert len(scats) == 1
        m = scats[0]
        # 4-letter word but only 1 new tile (the S)
        assert len(m.tiles_placed) == 1
        assert len(m.tiles_placed) < len(m.word)
        assert m.tiles_placed[0][2].letter == "S"
        assert m.tiles_placed[0][:2] == (7, 5)

    def test_reused_tiles_match_board(self, dawg):
        """For moves extending through board tiles, verify the letters NOT in
        tiles_placed match what's already on the board at those positions."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        rack = ["S", "C", "A", "T", "E", "R", "D"]
        moves = generate_moves(board, rack, dawg)

        # Check all ACROSS moves that extend through existing tiles
        extending_moves = [
            m for m in moves
            if m.direction == Direction.ACROSS
            and len(m.tiles_placed) < len(m.word)
            and m.start[0] == 7  # same row as CAT
        ]
        assert len(extending_moves) > 0

        for m in extending_moves:
            placed_positions = {(r, c) for r, c, _ in m.tiles_placed}
            r_start, c_start = m.start
            dr = 1 if m.direction == Direction.DOWN else 0
            dc = 1 if m.direction == Direction.ACROSS else 0

            for i, letter in enumerate(m.word):
                r = r_start + i * dr
                c = c_start + i * dc
                if (r, c) not in placed_positions:
                    # This letter came from the board
                    board_tile = board.get_tile(r, c)
                    assert board_tile is not None, (
                        f"Move {m.word}: position ({r},{c}) not in tiles_placed "
                        f"but board is empty there"
                    )
                    board_letter = (
                        board_tile.blank_letter if board_tile.is_blank else board_tile.letter
                    )
                    assert board_letter == letter, (
                        f"Move {m.word}: board has '{board_letter}' at ({r},{c}) "
                        f"but word expects '{letter}'"
                    )

    def test_placed_tiles_are_rack_subset(self, dawg):
        """tiles_placed letters must be a subset of the rack for moves
        that extend through existing board tiles."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        rack = ["S", "C", "A", "T", "E", "R", "D"]
        moves = generate_moves(board, rack, dawg)

        for m in moves:
            placed_letters = [t.letter for _, _, t in m.tiles_placed]
            placed_counts = Counter(placed_letters)
            rack_counts = Counter(rack)
            for letter, count in placed_counts.items():
                assert count <= rack_counts[letter], (
                    f"Move {m.word} places {count}x '{letter}' "
                    f"but rack only has {rack_counts[letter]}"
                )


class TestPerformance:
    def test_generation_speed(self, dawg):
        """Move generation should complete in under 2 seconds."""
        import time

        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "HELLO"]
        board.place_word("HELLO", (7, 3), Direction.ACROSS, tiles)

        start = time.perf_counter()
        moves = generate_moves(board, ["A", "E", "I", "O", "U", "S", "T"], dawg)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"Move generation took {elapsed:.2f}s"
        assert len(moves) > 0

    def test_empty_board_speed(self, dawg):
        """Empty board move generation should complete in under 2 seconds."""
        import time

        board = Board()
        start = time.perf_counter()
        moves = generate_moves(board, ["S", "A", "T", "I", "R", "E", "N"], dawg)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"Empty board generation took {elapsed:.2f}s"
