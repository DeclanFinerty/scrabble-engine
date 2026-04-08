"""Tests for game state management and position analysis."""

import time

import pytest

from scrabble_engine.board import BOARD_SIZE, Board, Direction
from scrabble_engine.dawg import DAWG
from scrabble_engine.engine import (
    GameState,
    analyze_position,
    best_possible_moves,
    unplayed_tiles,
)
from scrabble_engine.move_generator import generate_moves
from scrabble_engine.tiles import TILE_DISTRIBUTION, Tile


@pytest.fixture(scope="module")
def dawg():
    return DAWG.from_file("src/scrabble_engine/data/twl06.txt")


class TestGameStateInit:
    def test_initial_state(self, dawg):
        gs = GameState(dawg)
        assert gs.current_player == 0
        assert gs.scores == [0, 0]
        assert gs.board.is_empty()
        assert gs.get_rack(0).size() == 7
        assert gs.get_rack(1).size() == 7
        assert gs.bag.tiles_in_bag() == 86  # 100 - 7 - 7
        assert len(gs.move_history) == 0
        assert not gs.is_game_over()

    def test_tile_conservation(self, dawg):
        """Total tiles should always be 100: bag + racks + board."""
        gs = GameState(dawg)
        total = gs.bag.tiles_in_bag() + gs.get_rack(0).size() + gs.get_rack(1).size()
        assert total == 100


class TestPlayMove:
    def test_play_first_move(self, dawg):
        gs = GameState(dawg)
        moves = gs.generate_moves_for_current_player()
        assert len(moves) > 0

        move = moves[0]  # highest scoring

        gs.play_move(move)

        assert gs.scores[0] == move.score
        assert gs.scores[1] == 0
        assert gs.current_player == 1
        assert not gs.board.is_empty()
        assert len(gs.move_history) == 1
        assert gs.move_history[0].player == 0
        # Rack should have been refilled
        assert gs.get_rack(0).size() == 7

    def test_play_two_moves(self, dawg):
        gs = GameState(dawg)

        # Player 0 plays
        moves_p0 = gs.generate_moves_for_current_player()
        move_p0 = moves_p0[0]
        gs.play_move(move_p0)
        assert gs.current_player == 1

        # Player 1 plays
        moves_p1 = gs.generate_moves_for_current_player()
        if moves_p1:
            move_p1 = moves_p1[0]
            gs.play_move(move_p1)
            assert gs.current_player == 0
            assert gs.scores[0] == move_p0.score
            assert gs.scores[1] == move_p1.score
            assert len(gs.move_history) == 2

    def test_tile_conservation_after_play(self, dawg):
        """Tiles should be conserved after playing moves."""
        gs = GameState(dawg)
        moves = gs.generate_moves_for_current_player()
        gs.play_move(moves[0])

        bag_count = gs.bag.tiles_in_bag()
        rack0 = gs.get_rack(0).size()
        rack1 = gs.get_rack(1).size()
        board_tiles = sum(gs.tiles_on_board().values())

        assert bag_count + rack0 + rack1 + board_tiles == 100


class TestRemainingTiles:
    def test_initial_remaining(self, dawg):
        """Remaining tiles = bag + opponent rack = 86 + 7 = 93 from player 0's view."""
        gs = GameState(dawg)
        remaining = gs.remaining_tiles()
        total = sum(remaining.values())
        assert total == 93  # 100 - 7 (current player's rack)

    def test_remaining_after_move(self, dawg):
        gs = GameState(dawg)
        moves = gs.generate_moves_for_current_player()
        tiles_placed = len(moves[0].tiles_placed)
        gs.play_move(moves[0])

        # Now current player is 1. Remaining = bag + player 0's rack
        remaining = gs.remaining_tiles()
        total = sum(remaining.values())
        # Player 1 has 7 tiles on rack. Board has tiles_placed tiles.
        # Remaining = 100 - 7 (player 1 rack) - tiles_placed (board)
        assert total == 100 - 7 - tiles_placed

    def test_remaining_accounts_for_all_tiles(self, dawg):
        """remaining + current rack + board tiles should equal 100."""
        gs = GameState(dawg)
        moves = gs.generate_moves_for_current_player()
        gs.play_move(moves[0])

        remaining_count = sum(gs.remaining_tiles().values())
        current_rack_count = gs.get_rack(gs.current_player).size()
        board_count = sum(gs.tiles_on_board().values())

        assert remaining_count + current_rack_count + board_count == 100


class TestTilesOnBoard:
    def test_empty_board(self, dawg):
        gs = GameState(dawg)
        assert gs.tiles_on_board() == {}

    def test_after_move(self, dawg):
        gs = GameState(dawg)
        moves = gs.generate_moves_for_current_player()
        move = moves[0]
        gs.play_move(move)

        board_tiles = gs.tiles_on_board()
        total = sum(board_tiles.values())
        assert total == len(move.tiles_placed)


class TestPassTurn:
    def test_pass(self, dawg):
        gs = GameState(dawg)
        gs.pass_turn()
        assert gs.current_player == 1
        assert gs.scores == [0, 0]

    def test_game_over_on_consecutive_passes(self, dawg):
        """Standard tournament Scrabble rule: game ends after 6 consecutive
        scoreless turns (3 full rounds in a 2-player game). Each pass or
        exchange counts as a scoreless turn. This matches NASPA/FIDE rules."""
        gs = GameState(dawg)
        for i in range(5):
            assert not gs.is_game_over(), f"Game should not be over after {i + 1} passes"
            gs.pass_turn()
        # 6th consecutive zero-score turn ends the game
        gs.pass_turn()
        assert gs.is_game_over()

    def test_pass_counter_resets_on_play(self, dawg):
        """Playing a scoring move should reset the consecutive pass counter."""
        gs = GameState(dawg)
        gs.pass_turn()  # p0
        gs.pass_turn()  # p1

        # p0 plays a real move — resets counter
        moves = gs.generate_moves_for_current_player()
        gs.play_move(moves[0])

        # Now need 6 more passes to end
        for _ in range(5):
            assert not gs.is_game_over()
            gs.pass_turn()
        gs.pass_turn()
        assert gs.is_game_over()


class TestExchangeTiles:
    def test_exchange(self, dawg):
        gs = GameState(dawg)
        rack = gs.get_rack(0)
        old_tiles = rack.tiles[:3]

        new_tiles = gs.exchange_tiles(old_tiles)
        assert len(new_tiles) == 3
        assert rack.size() == 7  # still 7 tiles
        assert gs.current_player == 1  # turn advanced
        assert gs.bag.tiles_in_bag() == 86  # 86 - 3 drawn + 3 returned = 86

    def test_exchange_not_enough_in_bag(self, dawg):
        """Cannot exchange when fewer than 7 tiles remain in the bag.
        Drain the bag by drawing tiles until only a few remain."""
        gs = GameState(dawg)
        # Draw tiles until bag has fewer than 7
        while gs.bag.tiles_in_bag() >= 7:
            gs.bag.draw(7)

        assert gs.bag.tiles_in_bag() < 7
        rack = gs.get_rack(0)
        with pytest.raises(ValueError, match="Cannot exchange"):
            gs.exchange_tiles(rack.tiles[:2])


class TestGameOver:
    def test_not_over_at_start(self, dawg):
        gs = GameState(dawg)
        assert not gs.is_game_over()

    def test_over_when_bag_and_rack_empty(self, dawg):
        """Game ends when bag is empty and any player's rack is empty.
        Drain the bag by drawing, then empty a rack by removing tiles."""
        gs = GameState(dawg)
        # Draw all remaining tiles from bag
        gs.bag.draw(gs.bag.tiles_in_bag())
        assert gs.bag.tiles_in_bag() == 0

        # Empty player 0's rack by removing all tiles
        rack = gs.get_rack(0)
        rack.remove(rack.tiles)
        assert rack.is_empty()

        assert gs.is_game_over()

    def test_not_over_bag_empty_racks_full(self, dawg):
        gs = GameState(dawg)
        # Draw all remaining tiles from bag
        gs.bag.draw(gs.bag.tiles_in_bag())
        assert gs.bag.tiles_in_bag() == 0
        # Both racks still have tiles
        assert not gs.is_game_over()


class TestGameSimulation:
    def test_multi_turn_game(self, dawg):
        """Play several turns and verify state consistency throughout."""
        gs = GameState(dawg)
        turns_played = 0
        max_turns = 6  # 3 per player

        while turns_played < max_turns and not gs.is_game_over():
            moves = gs.generate_moves_for_current_player()
            if not moves:
                gs.pass_turn()
                turns_played += 1
                continue

            move = moves[0]
            gs.play_move(move)
            turns_played += 1

            # Verify conservation after each turn
            bag_count = gs.bag.tiles_in_bag()
            rack0 = gs.get_rack(0).size()
            rack1 = gs.get_rack(1).size()
            board_count = sum(gs.tiles_on_board().values())
            assert bag_count + rack0 + rack1 + board_count == 100

        assert turns_played > 0
        assert len(gs.move_history) > 0
        assert sum(gs.scores) > 0


class TestAnalyzePosition:
    def test_analyze_empty_board(self, dawg):
        board = Board()
        moves = analyze_position(board, ["C", "A", "T", "S", "D", "O", "G"], dawg)
        assert len(moves) > 0
        words = {m.word for m in moves}
        assert "CAT" in words
        assert "CATS" in words

    def test_analyze_from_text_grid(self, dawg):
        """Import a realistic board from a text grid and run analysis.

        Board state (simulating a mid-game scrabble-vision scan):
          Row 5:  ......QUEST....
          Row 7:  .....CHATTER...
          Row 9:  ........BOND...

        Words are spaced so no accidental cross-column conflicts.
        TATE at col 10 (T from QUEST, A+T+E from CHATTER) is valid — but
        we avoid column 6 overlap by offsetting BOND.
        """
        rows = ["." * 15] * 15
        rows = list(rows)
        # QUEST at (5, 6): Q(5,6), U(5,7), E(5,8), S(5,9), T(5,10)
        rows[5] = "......QUEST...."
        # CHATTER at (7, 5): C(7,5), H(7,6), A(7,7), T(7,8), T(7,9), E(7,10), R(7,11)
        rows[7] = ".....CHATTER..."
        # BOND at (9, 8): B(9,8), O(9,9), N(9,10), D(9,11)
        rows[9] = "........BOND..."
        grid = "\n".join(rows)

        board = Board.from_text(grid)
        assert board.get_tile(5, 6).letter == "Q"
        assert board.get_tile(7, 5).letter == "C"
        assert board.get_tile(9, 8).letter == "B"

        # Analyze with a rack that can form interesting plays
        moves = analyze_position(board, ["S", "I", "N", "G", "E", "R", "D"], dawg)
        assert len(moves) > 0

        # Should find non-trivial plays (not just single-letter hooks)
        multi_tile_moves = [m for m in moves if len(m.tiles_placed) >= 3]
        assert len(multi_tile_moves) > 0

        # All moves should have valid words
        for m in moves[:20]:
            assert dawg.search(m.word), f"Invalid word: {m.word}"

    def test_analyze_sorted_by_score(self, dawg):
        board = Board()
        moves = analyze_position(board, ["A", "E", "I", "O", "U", "S", "T"], dawg)
        scores = [m.score for m in moves]
        assert scores == sorted(scores, reverse=True)

    def test_analyze_no_disconnected(self, dawg):
        """analyze_position must enforce connectivity — no moves far from tiles."""
        grid = (
            "...............\n"
            "...............\n"
            "...............\n"
            "...............\n"
            "...............\n"
            "...............\n"
            "...............\n"
            "......HELLO....\n"
            "...............\n"
            "...............\n"
            "...............\n"
            "...............\n"
            "...............\n"
            "...............\n"
            "..............."
        )
        board = Board.from_text(grid)
        moves = analyze_position(board, ["H", "A", "Z", "E", "Q", "I", "S"], dawg)

        for move in moves:
            r, c = move.start
            length = len(move.word)
            if move.direction == Direction.ACROSS:
                positions = [(r, c + i) for i in range(length)]
            else:
                positions = [(r + i, c) for i in range(length)]

            near_existing = any(
                board.get_tile(pr + dr, pc + dc) is not None
                for pr, pc in positions
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0)]
                if 0 <= pr + dr < 15 and 0 <= pc + dc < 15
            )
            assert near_existing, (
                f"analyze_position: {move.word} at {move.start} is disconnected"
            )


class TestBestPossibleMoves:
    def test_finds_moves(self, dawg):
        """With max_tiles=2, should find moves quickly and return valid results."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        start = time.perf_counter()
        moves = best_possible_moves(board, dawg, n=5, max_tiles=2)
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"best_possible_moves took {elapsed:.2f}s (limit 5s)"
        assert len(moves) > 0
        assert len(moves) <= 5
        for i in range(len(moves) - 1):
            assert moves[i].score >= moves[i + 1].score

    def test_moves_are_valid(self, dawg):
        """All returned moves should have valid words."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        moves = best_possible_moves(board, dawg, n=10, max_tiles=2)
        for m in moves:
            assert dawg.search(m.word), f"Invalid word: {m.word}"
            assert m.score > 0


class TestUnplayedTiles:
    def test_empty_board(self):
        """On an empty board, unplayed tiles equals the full standard distribution."""
        board = Board()
        pool = unplayed_tiles(board)
        total = sum(pool.values())
        assert total == 100
        assert pool["A"] == 9
        assert pool["E"] == 12
        assert pool["?"] == 2
        assert pool["Z"] == 1

    def test_after_placing_tiles(self):
        """Unplayed tiles should decrease as tiles are placed."""
        board = Board()
        tiles = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles)

        pool = unplayed_tiles(board)
        total = sum(pool.values())
        assert total == 97  # 100 - 3

        # Original distribution: C=2, A=9, T=6
        # After placing CAT: C=1, A=8, T=5
        assert pool["C"] == 1
        assert pool["A"] == 8
        assert pool["T"] == 5

    def test_unplayed_with_blank(self):
        """Blank tiles on the board should be counted as '?' in the pool."""
        board = Board()
        blank = Tile(letter="?", points=0, is_blank=True, blank_letter="S")
        board.place_tile(7, 7, blank)

        pool = unplayed_tiles(board)
        assert pool["?"] == 1  # started with 2, one placed
        assert pool.get("S", 4) == 4  # S count unchanged — blank is tracked as '?'
        assert sum(pool.values()) == 99


class TestBoardTextRoundTrip:
    def test_full_roundtrip(self):
        """Place several words, serialize to text, deserialize, verify every cell."""
        board = Board()
        tiles_cat = [Tile.from_letter(ch) for ch in "CAT"]
        board.place_word("CAT", (7, 6), Direction.ACROSS, tiles_cat)
        tiles_ape = [Tile.from_letter(ch) for ch in "PE"]
        board.place_word("APE", (7, 7), Direction.DOWN, tiles_ape)
        # Board now has: C(7,6), A(7,7), T(7,8), P(8,7), E(9,7)

        text = board.to_text()
        board2 = Board.from_text(text)

        # Verify every cell matches
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                orig = board.get_tile(r, c)
                copy = board2.get_tile(r, c)
                if orig is None:
                    assert copy is None, f"({r},{c}) should be empty"
                else:
                    assert copy is not None, f"({r},{c}) should have a tile"
                    orig_letter = orig.blank_letter if orig.is_blank else orig.letter
                    copy_letter = copy.blank_letter if copy.is_blank else copy.letter
                    assert orig_letter == copy_letter, (
                        f"({r},{c}): '{orig_letter}' != '{copy_letter}'"
                    )

    def test_blank_tile_text_representation(self):
        """Blank tiles should be lowercase in text format and round-trip correctly.

        Spec: '.' = empty, 'A'-'Z' = regular tiles, 'a'-'z' = blanks.
        """
        board = Board()
        blank_s = Tile(letter="?", points=0, is_blank=True, blank_letter="S")
        board.place_tile(7, 7, blank_s)
        board.place_tile(7, 8, Tile.from_letter("A"))

        text = board.to_text()
        lines = text.split("\n")

        # (7,7) should be lowercase 's', (7,8) should be uppercase 'A'
        assert lines[7][7] == "s"
        assert lines[7][8] == "A"

        # Round-trip
        board2 = Board.from_text(text)
        tile = board2.get_tile(7, 7)
        assert tile.is_blank
        assert tile.blank_letter == "S"
        assert tile.points == 0

        tile_a = board2.get_tile(7, 8)
        assert not tile_a.is_blank
        assert tile_a.letter == "A"
