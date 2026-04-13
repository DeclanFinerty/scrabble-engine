"""Tests for WordQuery filter pipeline and word families."""

import time

import pytest

from scrabble_engine.dawg import DAWG
from scrabble_engine.query import WordQuery, word_score
from scrabble_engine.word_families import get_root, get_word_family


@pytest.fixture(scope="module")
def dawg():
    return DAWG.from_file("src/scrabble_engine/data/twl06.txt")


# ---------------------------------------------------------------------------
# word_score
# ---------------------------------------------------------------------------

class TestWordScore:
    def test_basic(self):
        # C=3, A=1, T=1
        assert word_score("CAT") == 5

    def test_high_value(self):
        # Q=10, I=1
        assert word_score("QI") == 11

    def test_case_insensitive(self):
        assert word_score("cat") == word_score("CAT")

    def test_empty(self):
        assert word_score("") == 0


# ---------------------------------------------------------------------------
# Basic chaining
# ---------------------------------------------------------------------------

class TestBasicChaining:
    def test_containing_z_not_u(self, dawg):
        results = WordQuery(dawg).containing("Z").not_containing("U").execute()
        assert all("Z" in w for w in results)
        assert all("U" not in w for w in results)
        assert "ZA" in results
        assert len(results) > 0

    def test_chain_multiple(self, dawg):
        results = (
            WordQuery(dawg)
            .containing("Z")
            .not_containing("U")
            .length(min=3, max=5)
            .sort_by_score()
            .execute()
        )
        assert all(3 <= len(w) <= 5 for w in results)
        assert all("Z" in w for w in results)
        scores = [word_score(w) for w in results]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Individual filters
# ---------------------------------------------------------------------------

class TestIndividualFilters:
    def test_starting_with(self, dawg):
        results = WordQuery(dawg).starting_with("QU").execute()
        assert all(w.startswith("QU") for w in results)
        assert "QUIT" in results

    def test_ending_with(self, dawg):
        results = WordQuery(dawg).ending_with("ING").execute()
        assert all(w.endswith("ING") for w in results)
        assert len(results) > 100

    def test_letter_at(self, dawg):
        results = WordQuery(dawg).letter_at(0, "X").length(min=2, max=3).execute()
        assert all(w[0] == "X" for w in results)
        assert all(2 <= len(w) <= 3 for w in results)
        assert len(results) > 0

    def test_matching_pattern(self, dawg):
        results = WordQuery(dawg).matching_pattern("..G").execute()
        assert all(len(w) == 3 and w[2] == "G" for w in results)
        assert "BAG" in results
        assert "DOG" in results

    def test_from_rack(self, dawg):
        results = WordQuery(dawg).from_rack(["C", "A", "T", "S"]).execute()
        assert "CAT" in results
        assert "CATS" in results
        assert "ACT" in results
        assert "ACTS" in results

    def test_from_rack_with_blank(self, dawg):
        results = WordQuery(dawg).from_rack(["?", "A", "T"]).execute()
        assert "CAT" in results  # blank as C
        assert "BAT" in results  # blank as B
        assert "AT" in results   # no blank needed

    def test_min_score(self, dawg):
        results = WordQuery(dawg).min_score(20).length(min=2, max=4).execute()
        assert all(word_score(w) >= 20 for w in results)
        assert len(results) > 0

    def test_not_containing_multiple(self, dawg):
        """not_containing with multiple letters excludes all of them."""
        results = WordQuery(dawg).not_containing("AEIOU").length(min=2).execute()
        for w in results:
            assert not any(v in w for v in "AEIOU")

    def test_containing_requires_all(self, dawg):
        """containing("QZ") means word must have BOTH Q and Z."""
        results = WordQuery(dawg).containing("QZ").execute()
        for w in results:
            assert "Q" in w and "Z" in w


# ---------------------------------------------------------------------------
# Substring filter
# ---------------------------------------------------------------------------

class TestHasSubstring:
    def test_basic(self, dawg):
        results = WordQuery(dawg).has_substring("ING").execute()
        assert all("ING" in w for w in results)
        assert "KING" in results
        assert len(results) > 0

    def test_multiple_substrings_and_logic(self, dawg):
        results = WordQuery(dawg).has_substring("UN").has_substring("ING").execute()
        assert all("UN" in w and "ING" in w for w in results)
        assert len(results) > 0

    def test_no_match(self, dawg):
        results = WordQuery(dawg).has_substring("XYZQ").execute()
        assert results == []

    def test_case_insensitive(self, dawg):
        upper = WordQuery(dawg).has_substring("ING").execute()
        lower = WordQuery(dawg).has_substring("ing").execute()
        assert upper == lower

    def test_chained_with_other_filters(self, dawg):
        results = (
            WordQuery(dawg)
            .has_substring("ING")
            .length(min=5, max=7)
            .not_containing("Z")
            .execute()
        )
        assert all("ING" in w for w in results)
        assert all(5 <= len(w) <= 7 for w in results)
        assert all("Z" not in w for w in results)


# ---------------------------------------------------------------------------
# Limit and count
# ---------------------------------------------------------------------------

class TestLimitAndCount:
    def test_limit(self, dawg):
        all_results = WordQuery(dawg).containing("Z").execute()
        limited = WordQuery(dawg).containing("Z").execute(limit=10)
        assert len(limited) == 10
        assert len(all_results) > 10

    def test_count(self, dawg):
        count = WordQuery(dawg).length(min=2, max=2).count()
        results = WordQuery(dawg).length(min=2, max=2).execute()
        assert count == len(results)


# ---------------------------------------------------------------------------
# Sort orders
# ---------------------------------------------------------------------------

class TestSortOrders:
    def test_sort_alphabetically(self, dawg):
        results = WordQuery(dawg).starting_with("ZA").sort_alphabetically().execute()
        assert results == sorted(results)

    def test_sort_by_length(self, dawg):
        results = WordQuery(dawg).containing("Z").sort_by_length().execute()
        lengths = [len(w) for w in results]
        assert lengths == sorted(lengths, reverse=True)

    def test_sort_by_score(self, dawg):
        results = WordQuery(dawg).starting_with("QU").sort_by_score().execute()
        scores = [word_score(w) for w in results]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Word families
# ---------------------------------------------------------------------------

class TestWordFamilies:
    def test_word_family_board(self, dawg):
        family = get_word_family(dawg, "BOARD")
        ext_words = [e["word"] for e in family["extensions"]]
        assert "BOARDS" in ext_words
        assert "BOARDED" in ext_words
        assert "BOARDING" in ext_words

    def test_word_family_prefixes(self, dawg):
        family = get_word_family(dawg, "BOARD")
        pre_words = [p["word"] for p in family["prefixes"]]
        assert "ABOARD" in pre_words

    def test_word_family_root(self, dawg):
        family = get_word_family(dawg, "BOARD")
        assert family["root"] == "BOARD"

    def test_word_family_invalid(self, dawg):
        with pytest.raises(ValueError, match="not a valid word"):
            get_word_family(dawg, "XYZQQ")

    def test_get_root_boarding(self, dawg):
        assert get_root(dawg, "BOARDING") == "BOARD"

    def test_get_root_cats(self, dawg):
        assert get_root(dawg, "CATS") == "CAT"

    def test_get_root_already_root(self, dawg):
        assert get_root(dawg, "CAT") == "CAT"

    def test_get_root_invalid(self, dawg):
        with pytest.raises(ValueError, match="not a valid word"):
            get_root(dawg, "XYZQQ")


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

class TestQueryPerformance:
    def test_query_performance(self, dawg):
        start = time.perf_counter()
        results = (
            WordQuery(dawg)
            .containing("Z")
            .not_containing("U")
            .length(min=3, max=7)
            .sort_by_score()
            .execute()
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0
        assert len(results) > 0

    def test_unfiltered_performance(self, dawg):
        """Even with no DAWG-accelerated filters, should be fast."""
        start = time.perf_counter()
        results = WordQuery(dawg).containing("X").not_containing("E").execute()
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0
        assert len(results) > 0
