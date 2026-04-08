"""Tests for the DAWG (Trie + minimization) data structure."""

from scrabble_engine.dawg import DAWG, DAWGNode, build_trie, count_nodes, minimize_to_dawg


class TestTrieConstruction:
    def test_insert_and_search(self):
        dawg = DAWG(["CAT", "CAR", "CARD", "CARE", "DOG"])
        assert dawg.search("CAT")
        assert dawg.search("CAR")
        assert dawg.search("CARD")
        assert dawg.search("CARE")
        assert dawg.search("DOG")

    def test_search_not_found(self):
        dawg = DAWG(["CAT", "CAR"])
        assert not dawg.search("CA")
        assert not dawg.search("CATS")
        assert not dawg.search("DOG")
        assert not dawg.search("")

    def test_contains_operator(self):
        dawg = DAWG(["HELLO", "WORLD"])
        assert "HELLO" in dawg
        assert "WORLD" in dawg
        assert "HELL" not in dawg

    def test_case_insensitive_search(self):
        dawg = DAWG(["CAT"])
        assert dawg.search("cat")
        assert dawg.search("Cat")
        assert dawg.search("CAT")


class TestStartsWith:
    def test_valid_prefix(self):
        dawg = DAWG(["CAT", "CAR", "CARD", "DOG"])
        node = dawg.starts_with("CA")
        assert node is not None
        assert "T" in node.children
        assert "R" in node.children

    def test_invalid_prefix(self):
        dawg = DAWG(["CAT", "CAR"])
        assert dawg.starts_with("ZZ") is None
        assert dawg.starts_with("CX") is None

    def test_full_word_prefix(self):
        dawg = DAWG(["CAR", "CARD"])
        node = dawg.starts_with("CAR")
        assert node is not None
        assert node.is_terminal
        assert "D" in node.children

    def test_words_from_node(self):
        dawg = DAWG(["CAT", "CAR", "CARD", "CARE", "DOG"])
        node = dawg.starts_with("CAR")
        words = dawg.words_from_node(node, "CAR")
        assert sorted(words) == ["CAR", "CARD", "CARE"]


class TestEmptyTrie:
    def test_empty(self):
        dawg = DAWG([])
        assert not dawg.search("ANYTHING")
        assert dawg.starts_with("A") is None


class TestMinimization:
    def test_node_count_reduced(self):
        """After minimization, shared suffixes should reduce node count."""
        words = ["BAKING", "MAKING", "TAKING", "RAKING", "WAKING",
                 "BAKED", "MAKES", "TAKES", "RAKES", "WAKES"]
        trie_root = build_trie(words)
        trie_count = count_nodes(trie_root)

        dawg_root = minimize_to_dawg(trie_root)
        dawg_count = count_nodes(dawg_root)

        assert dawg_count < trie_count

    def test_all_words_survive_minimization(self):
        """All words must still be searchable after minimization."""
        words = ["CAT", "CAR", "CARD", "CARE", "BAT", "BAR", "BARD", "BARE",
                 "EATING", "BEATING", "HEATING", "SEATING"]
        dawg = DAWG(words)
        for word in words:
            assert dawg.search(word), f"{word} not found after minimization"

    def test_non_words_still_rejected(self):
        words = ["CAT", "CAR", "CARD"]
        dawg = DAWG(words)
        assert not dawg.search("CA")
        assert not dawg.search("CARDS")
        assert not dawg.search("CART")

    def test_significant_reduction_on_similar_words(self):
        """Words with shared suffixes like -ING, -ED, -ER should compress well."""
        bases = ["PLAY", "STAY", "PRAY", "SWAY", "CLAY", "GRAY", "FRAY", "SLAY"]
        words = []
        for b in bases:
            words.append(b)
            words.append(b + "S")
            words.append(b + "ED")
            words.append(b + "ING")
            words.append(b + "ER")

        trie_root = build_trie(words)
        trie_count = count_nodes(trie_root)

        dawg_root = minimize_to_dawg(trie_root)
        dawg_count = count_nodes(dawg_root)

        # With 8 bases × 5 forms, suffix sharing should be substantial
        assert dawg_count < trie_count * 0.7


class TestFromFile:
    def test_load_full_dictionary(self):
        """Load the TWL06 word list and verify basic properties."""
        dawg = DAWG.from_file("src/scrabble_engine/data/twl06.txt")
        assert dawg.search("QI")
        assert dawg.search("ZA")
        assert dawg.search("AARDVARK")
        assert not dawg.search("QX")
        assert not dawg.search("ASDFGH")
