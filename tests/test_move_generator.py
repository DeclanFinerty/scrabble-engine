"""Tests for the move generator (Appel & Jacobson)."""

import pytest

from scrabble_engine.board import Board, Direction
from scrabble_engine.dawg import DAWG
from scrabble_engine.move_generator import Move, best_moves, generate_moves
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
        # Should be sorted
        for i in range(len(top) - 1):
            assert top[i].score >= top[i + 1].score


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
            # Check that placed letters are a subset of rack
            from collections import Counter
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
