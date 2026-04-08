"""Scrabble engine - dictionary lookup, move generation, and optimal play analysis."""

from scrabble_engine.board import BOARD_SIZE, Board, BonusSquare, Direction
from scrabble_engine.dawg import DAWG, DAWGNode
from scrabble_engine.dictionary import Dictionary
from scrabble_engine.engine import (
    GameState,
    analyze_position,
    best_possible_moves,
    unplayed_tiles,
)
from scrabble_engine.move_generator import Move, best_moves, generate_moves
from scrabble_engine.scoring import score_word
from scrabble_engine.tiles import Rack, Tile, TileBag, find_words

__all__ = [
    "BOARD_SIZE",
    "Board",
    "BonusSquare",
    "DAWG",
    "DAWGNode",
    "Dictionary",
    "Direction",
    "GameState",
    "Move",
    "Rack",
    "Tile",
    "TileBag",
    "analyze_position",
    "best_moves",
    "best_possible_moves",
    "find_words",
    "generate_moves",
    "load_dictionary",
    "score_word",
    "unplayed_tiles",
]


def load_dictionary() -> Dictionary:
    """Load the default TWL06 dictionary."""
    return Dictionary.from_file()
