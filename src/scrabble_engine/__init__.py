"""Scrabble engine - dictionary lookup, move generation, and optimal play analysis."""

from scrabble_engine.dawg import DAWG, DAWGNode
from scrabble_engine.dictionary import Dictionary
from scrabble_engine.tiles import Rack, Tile, TileBag, find_words

__all__ = [
    "DAWG",
    "DAWGNode",
    "Dictionary",
    "Rack",
    "Tile",
    "TileBag",
    "find_words",
    "load_dictionary",
]


def load_dictionary() -> Dictionary:
    """Load the default TWL06 dictionary."""
    return Dictionary.from_file()
