"""Game state management, tile tracking, and position analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from scrabble_engine.board import BOARD_SIZE, Board, Direction
from scrabble_engine.dawg import DAWG
from scrabble_engine.move_generator import Move, generate_moves
from scrabble_engine.tiles import LETTER_VALUES, TILE_DISTRIBUTION, Rack, Tile, TileBag


# Standard tournament Scrabble: game ends after 6 consecutive scoreless turns
# (3 full rounds of 2 players each passing/exchanging).
_MAX_CONSECUTIVE_ZERO_TURNS = 6


@dataclass
class PlayedMove:
    """A move that was played, with the player who played it."""

    move: Move
    player: int


class GameState:
    """Full Scrabble game state: board, bag, racks, scores, history."""

    def __init__(self, dawg: DAWG, num_players: int = 2) -> None:
        self._dawg = dawg
        self._board = Board()
        self._bag = TileBag()
        self._num_players = num_players
        self._racks: list[Rack] = [Rack() for _ in range(num_players)]
        self._scores: list[int] = [0] * num_players
        self._current_player: int = 0
        self._move_history: list[PlayedMove] = []
        self._consecutive_zero_turns: int = 0

        # Draw initial tiles for each player
        for rack in self._racks:
            rack.add(self._bag.draw(7))

    @property
    def board(self) -> Board:
        return self._board

    @property
    def bag(self) -> TileBag:
        return self._bag

    @property
    def scores(self) -> list[int]:
        return list(self._scores)

    @property
    def current_player(self) -> int:
        return self._current_player

    @property
    def move_history(self) -> list[PlayedMove]:
        return list(self._move_history)

    def get_rack(self, player: int) -> Rack:
        return self._racks[player]

    def play_move(self, move: Move) -> None:
        """Play a move for the current player.

        Places tiles on the board, updates score, removes tiles from rack,
        draws replacements from bag, advances to next player.
        """
        player = self._current_player
        rack = self._racks[player]

        # Place tiles on the board
        for r, c, tile in move.tiles_placed:
            self._board.place_tile(r, c, tile)

        # Remove placed tiles from rack
        placed_tiles = [tile for _, _, tile in move.tiles_placed]
        rack.remove(placed_tiles)

        # Update score
        self._scores[player] += move.score

        # Draw new tiles
        num_to_draw = min(len(placed_tiles), 7 - rack.size())
        new_tiles = self._bag.draw(num_to_draw)
        if new_tiles:
            rack.add(new_tiles)

        # Record move
        self._move_history.append(PlayedMove(move=move, player=player))
        self._consecutive_zero_turns = 0

        # Advance to next player
        self._current_player = (self._current_player + 1) % self._num_players

    def pass_turn(self) -> None:
        """Pass the current player's turn (scores 0)."""
        self._consecutive_zero_turns += 1
        self._current_player = (self._current_player + 1) % self._num_players

    def exchange_tiles(self, tiles: list[Tile]) -> list[Tile]:
        """Exchange tiles from current player's rack with the bag.

        Must have at least 7 tiles in the bag to exchange.
        Returns the new tiles drawn.
        """
        if self._bag.tiles_in_bag() < 7:
            raise ValueError(
                f"Cannot exchange: only {self._bag.tiles_in_bag()} tiles in bag (need >= 7)"
            )

        player = self._current_player
        rack = self._racks[player]

        # Remove tiles from rack
        rack.remove(tiles)

        # Draw new tiles first (before returning old ones)
        new_tiles = self._bag.draw(len(tiles))
        rack.add(new_tiles)

        # Return exchanged tiles to bag
        self._bag.return_tiles(tiles)

        self._consecutive_zero_turns += 1
        self._current_player = (self._current_player + 1) % self._num_players

        return new_tiles

    def remaining_tiles(self) -> dict[str, int]:
        """Tiles unaccounted for from the current player's perspective.

        Returns the combined count of tiles in the bag plus all opponents' racks.
        This is what the current player doesn't know about.
        """
        counts: Counter[str] = Counter()

        # Tiles in the bag
        for letter, count in self._bag.remaining().items():
            counts[letter] += count

        # Tiles on opponents' racks
        for i, rack in enumerate(self._racks):
            if i != self._current_player:
                for tile in rack.tiles:
                    counts[tile.letter] += 1

        return dict(sorted(counts.items()))

    def tiles_on_board(self) -> dict[str, int]:
        """Count of each letter currently on the board."""
        counts: Counter[str] = Counter()
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                tile = self._board.get_tile(r, c)
                if tile is not None:
                    if tile.is_blank:
                        counts["?"] += 1
                    else:
                        counts[tile.letter] += 1
        return dict(sorted(counts.items()))

    def is_game_over(self) -> bool:
        """The game is over when:
        - The bag is empty AND any player's rack is empty, OR
        - 6 consecutive scoreless turns (standard tournament rule: 3 full
          rounds of passing/exchanging in a 2-player game)
        """
        if self._bag.tiles_in_bag() == 0:
            for rack in self._racks:
                if rack.is_empty():
                    return True

        if self._consecutive_zero_turns >= _MAX_CONSECUTIVE_ZERO_TURNS:
            return True

        return False

    def generate_moves_for_current_player(self) -> list[Move]:
        """Generate all legal moves for the current player."""
        rack = self._racks[self._current_player]
        return generate_moves(self._board, rack.letters(), self._dawg)


def analyze_position(board: Board, rack: list[str], dawg: DAWG) -> list[Move]:
    """Analyze a board position without game state (no bag interaction).

    Given a board (e.g., from scrabble-vision) and a rack, find all legal
    moves sorted by score descending.
    """
    return generate_moves(board, rack, dawg)


def unplayed_tiles(board: Board) -> dict[str, int]:
    """Compute remaining tiles as 100 - tiles on board.

    For analysis mode (scrabble-vision) where we don't know whose turn it is
    or what's in the bag vs. racks. Simply: standard distribution minus what's
    visible on the board.
    """
    pool: Counter[str] = Counter()
    for letter, (_, count) in TILE_DISTRIBUTION.items():
        pool[letter] = count

    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            tile = board.get_tile(r, c)
            if tile is not None:
                key = "?" if tile.is_blank else tile.letter
                pool[key] -= 1

    return dict(sorted((k, v) for k, v in pool.items() if v > 0))


def best_possible_moves(
    board: Board, dawg: DAWG, n: int = 10, max_tiles: int = 3
) -> list[Move]:
    """Find the highest-scoring possible moves with no rack constraint.

    Builds a rack from the remaining tile pool (standard 100 minus what's on
    the board), prioritizing high-value letters. The `max_tiles` parameter
    caps the rack size to keep the search tractable — higher values explore
    more combinations but take exponentially longer.

    Args:
        board: Current board state.
        dawg: The word graph.
        n: Number of top moves to return.
        max_tiles: Maximum rack size for the search (default 3).
    """
    pool = unplayed_tiles(board)

    # Build a rack prioritizing high-value tiles for best scoring potential.
    available = [(letter, count) for letter, count in pool.items()]
    available.sort(key=lambda x: LETTER_VALUES.get(x[0], 0), reverse=True)

    rack: list[str] = []
    for letter, count in available:
        add = min(count, max(1, max_tiles - len(rack)))
        rack.extend([letter] * add)
        if len(rack) >= max_tiles:
            break

    moves = generate_moves(board, rack[:max_tiles], dawg)
    return moves[:n]
