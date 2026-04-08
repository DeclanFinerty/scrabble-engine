"""Tests for the Dictionary query interface."""

import time

import pytest

from scrabble_engine.dictionary import Dictionary


@pytest.fixture(scope="module")
def dictionary():
    """Load the full TWL06 dictionary once for all tests."""
    return Dictionary.from_file()


class TestIsValid:
    def test_valid_two_letter_words(self, dictionary):
        assert dictionary.is_valid("QI")
        assert dictionary.is_valid("ZA")
        assert dictionary.is_valid("XI")
        assert dictionary.is_valid("AA")

    def test_invalid_words(self, dictionary):
        assert not dictionary.is_valid("QX")
        assert not dictionary.is_valid("ASDFGH")
        assert not dictionary.is_valid("ZZZZZ")

    def test_case_insensitive(self, dictionary):
        assert dictionary.is_valid("qi")
        assert dictionary.is_valid("Qi")
        assert dictionary.is_valid("QI")

    def test_common_words(self, dictionary):
        for word in ["CAT", "DOG", "HELLO", "WORLD", "SCRABBLE"]:
            assert dictionary.is_valid(word)


class TestWordsByLength:
    def test_two_letter_words(self, dictionary):
        twos = dictionary.words_by_length(2)
        assert len(twos) == 101

    def test_no_zero_length(self, dictionary):
        assert dictionary.words_by_length(0) == []

    def test_very_long(self, dictionary):
        # There shouldn't be words of length 50
        assert dictionary.words_by_length(50) == []

    def test_all_correct_length(self, dictionary):
        fives = dictionary.words_by_length(5)
        assert all(len(w) == 5 for w in fives)
        assert len(fives) > 0


class TestWordsStartingWith:
    def test_starts_with_zym(self, dictionary):
        words = dictionary.words_starting_with("ZYM")
        assert "ZYMURGY" in words
        assert all(w.startswith("ZYM") for w in words)

    def test_starts_with_q(self, dictionary):
        words = dictionary.words_starting_with("Q")
        assert "QI" in words
        assert "QUEEN" in words
        assert len(words) > 0

    def test_no_match(self, dictionary):
        assert dictionary.words_starting_with("QX") == []

    def test_case_insensitive(self, dictionary):
        upper = dictionary.words_starting_with("CAT")
        lower = dictionary.words_starting_with("cat")
        assert upper == lower


class TestWordsEndingWith:
    def test_ends_with_ing(self, dictionary):
        words = dictionary.words_ending_with("ING")
        assert "PLAYING" in words
        assert "MAKING" in words
        assert len(words) > 100
        assert all(w.endswith("ING") for w in words)

    def test_ends_with_zz(self, dictionary):
        words = dictionary.words_ending_with("ZZ")
        assert "BUZZ" in words
        assert "FIZZ" in words
        assert "JAZZ" in words


class TestWordsContaining:
    def test_contains_qu(self, dictionary):
        words = dictionary.words_containing("QU")
        assert "QUEEN" in words
        assert "QUIET" in words
        assert all("QU" in w for w in words)

    def test_contains_zz(self, dictionary):
        words = dictionary.words_containing("ZZ")
        assert "PIZZA" in words
        assert "BUZZ" in words


class TestWordsMatchingPattern:
    def test_three_letter_ending_g(self, dictionary):
        words = dictionary.words_matching_pattern("..G")
        assert all(len(w) == 3 for w in words)
        assert all(w.endswith("G") for w in words)
        for expected in ["BAG", "BIG", "BOG", "BUG", "COG", "DIG", "DOG",
                         "FIG", "FOG", "GAG", "HOG", "HUG", "JAG", "JIG",
                         "JOG", "JUG", "KEG", "LAG", "LEG", "LOG", "LUG",
                         "MUG", "NAG", "PEG", "PIG", "PUG", "RAG", "RIG",
                         "RUG", "SAG", "TAG", "TUG", "WAG", "WIG", "ZAG", "ZIG"]:
            assert expected in words, f"{expected} not found in ..G pattern"

    def test_five_letter_starting_s(self, dictionary):
        words = dictionary.words_matching_pattern("S....")
        assert all(len(w) == 5 for w in words)
        assert all(w.startswith("S") for w in words)
        assert "START" in words
        assert "STARE" in words

    def test_exact_match(self, dictionary):
        words = dictionary.words_matching_pattern("CAT")
        assert words == ["CAT"]

    def test_all_wildcards(self, dictionary):
        words = dictionary.words_matching_pattern("..")
        assert len(words) == 101  # same as words_by_length(2)


class TestPerformance:
    """All queries should complete in under 100ms on the full dictionary."""

    def test_is_valid_speed(self, dictionary):
        start = time.perf_counter()
        for _ in range(10000):
            dictionary.is_valid("SCRABBLE")
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0  # 10K lookups in under 1s

    def test_words_by_length_speed(self, dictionary):
        start = time.perf_counter()
        dictionary.words_by_length(5)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1

    def test_pattern_match_speed(self, dictionary):
        start = time.perf_counter()
        dictionary.words_matching_pattern("..G")
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1

    def test_starts_with_speed(self, dictionary):
        start = time.perf_counter()
        dictionary.words_starting_with("S")
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1

    def test_ends_with_speed(self, dictionary):
        start = time.perf_counter()
        dictionary.words_ending_with("ING")
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1

    def test_contains_speed(self, dictionary):
        start = time.perf_counter()
        dictionary.words_containing("QU")
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1
