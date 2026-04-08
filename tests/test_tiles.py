"""Tests for tiles, bag, rack, and rack solver."""

import pytest

from scrabble_engine.dawg import DAWG
from scrabble_engine.tiles import (
    LETTER_VALUES,
    TILE_DISTRIBUTION,
    Rack,
    Tile,
    TileBag,
    find_words,
)


class TestTile:
    def test_from_letter(self):
        tile = Tile.from_letter("A")
        assert tile.letter == "A"
        assert tile.points == 1
        assert not tile.is_blank

    def test_from_blank(self):
        tile = Tile.from_letter("?")
        assert tile.letter == "?"
        assert tile.points == 0
        assert tile.is_blank

    def test_letter_values(self):
        assert LETTER_VALUES["A"] == 1
        assert LETTER_VALUES["Q"] == 10
        assert LETTER_VALUES["Z"] == 10
        assert LETTER_VALUES["X"] == 8
        assert LETTER_VALUES["J"] == 8
        assert LETTER_VALUES["K"] == 5
        assert LETTER_VALUES["?"] == 0


class TestTileBag:
    def test_initial_count(self):
        bag = TileBag()
        assert bag.tiles_in_bag() == 100

    def test_distribution_totals(self):
        total = sum(count for _, count in TILE_DISTRIBUTION.values())
        assert total == 100

    def test_draw(self):
        bag = TileBag()
        drawn = bag.draw(7)
        assert len(drawn) == 7
        assert bag.tiles_in_bag() == 93

    def test_draw_more_than_available(self):
        bag = TileBag()
        bag.draw(98)
        drawn = bag.draw(5)  # only 2 left
        assert len(drawn) == 2
        assert bag.tiles_in_bag() == 0

    def test_draw_from_empty(self):
        bag = TileBag()
        bag.draw(100)
        drawn = bag.draw(1)
        assert drawn == []
        assert bag.tiles_in_bag() == 0

    def test_remaining(self):
        bag = TileBag()
        remaining = bag.remaining()
        assert remaining["A"] == 9
        assert remaining["E"] == 12
        assert remaining["?"] == 2
        assert remaining["Z"] == 1

    def test_remove(self):
        bag = TileBag()
        bag.remove(["A", "E", "I"])
        assert bag.tiles_in_bag() == 97
        remaining = bag.remaining()
        assert remaining["A"] == 8
        assert remaining["E"] == 11
        assert remaining["I"] == 8

    def test_remove_not_found(self):
        bag = TileBag()
        bag.remove(["Z"])  # only 1 Z
        with pytest.raises(ValueError, match="not found"):
            bag.remove(["Z"])

    def test_remove_blank(self):
        bag = TileBag()
        bag.remove(["?"])
        remaining = bag.remaining()
        assert remaining["?"] == 1
        assert bag.tiles_in_bag() == 99


class TestRack:
    def test_add_and_letters(self):
        rack = Rack()
        rack.add([Tile.from_letter("C"), Tile.from_letter("A"), Tile.from_letter("T")])
        assert rack.letters() == ["A", "C", "T"]
        assert rack.size() == 3

    def test_add_exceeds_max(self):
        rack = Rack()
        rack.add([Tile.from_letter("A")] * 7)
        with pytest.raises(ValueError, match="Cannot add"):
            rack.add([Tile.from_letter("B")])

    def test_remove(self):
        rack = Rack()
        tiles = [Tile.from_letter("C"), Tile.from_letter("A"), Tile.from_letter("T")]
        rack.add(tiles)
        rack.remove([Tile.from_letter("A")])
        assert rack.letters() == ["C", "T"]

    def test_remove_not_on_rack(self):
        rack = Rack()
        rack.add([Tile.from_letter("A")])
        with pytest.raises(ValueError, match="not on rack"):
            rack.remove([Tile.from_letter("Z")])

    def test_is_full(self):
        rack = Rack()
        assert not rack.is_full()
        rack.add([Tile.from_letter("A")] * 7)
        assert rack.is_full()

    def test_is_empty(self):
        rack = Rack()
        assert rack.is_empty()
        rack.add([Tile.from_letter("A")])
        assert not rack.is_empty()


@pytest.fixture(scope="module")
def dawg():
    return DAWG.from_file("src/scrabble_engine/data/twl06.txt")


class TestFindWords:
    def test_cat(self, dawg):
        words = find_words(["C", "A", "T"], dawg)
        assert "CAT" in words
        assert "ACT" in words
        assert "AT" in words
        assert "TA" in words

    def test_qi(self, dawg):
        words = find_words(["Q", "I"], dawg)
        assert "QI" in words

    def test_no_reuse(self, dawg):
        """With one S, can't use S twice."""
        words = find_words(["S", "A", "T"], dawg)
        # Should not contain any word using S twice
        for w in words:
            from collections import Counter
            word_counts = Counter(w)
            rack_counts = Counter(["S", "A", "T"])
            for ch, cnt in word_counts.items():
                assert cnt <= rack_counts[ch], f"{w} uses {ch} more times than available"

    def test_aardvark_impossible(self, dawg):
        """Not enough letters for AARDVARK."""
        words = find_words(["A", "A", "R", "D", "V", "K"], dawg)
        assert "AARDVARK" not in words

    def test_seven_letter_rack(self, dawg):
        """A good 7-letter rack should find many words."""
        words = find_words(["A", "E", "R", "S", "T", "I", "N"], dawg)
        assert len(words) > 50
        assert "NASTIER" in words or "ANTSIER" in words or "RETINAS" in words
        # Should include short words too
        assert "AT" in words
        assert "IS" in words

    def test_duplicate_letters(self, dawg):
        """Duplicate letters on rack should be handled correctly."""
        words = find_words(["E", "E", "L"], dawg)
        assert "EEL" in words
        assert "LEE" in words
        assert "EL" in words

    def test_case_insensitive(self, dawg):
        """Rack letters should be case insensitive."""
        upper = find_words(["C", "A", "T"], dawg)
        lower = find_words(["c", "a", "t"], dawg)
        assert upper == lower

    def test_single_letter(self, dawg):
        """Single letter rack — only valid if that single letter is a word."""
        words = find_words(["A"], dawg)
        # "A" is not a valid scrabble word in TWL06 (only AA, AB, etc.)
        # But some single letters might be — check what the dawg says
        for w in words:
            assert dawg.search(w)

    def test_performance(self, dawg):
        """Rack solving should complete in under 100ms."""
        import time
        start = time.perf_counter()
        find_words(["A", "E", "R", "S", "T", "I", "N"], dawg)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1
