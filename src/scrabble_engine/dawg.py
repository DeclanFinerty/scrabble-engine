"""DAWG (Directed Acyclic Word Graph) data structure.

Two-step construction: build a Trie via insertion, then minimize to a DAWG
by merging nodes with identical subtrees (shared suffixes).
"""

from __future__ import annotations

from pathlib import Path


class DAWGNode:
    """A node in the Trie/DAWG. Each node has children keyed by letter
    and a flag indicating whether a valid word ends here."""

    __slots__ = ("children", "is_terminal")

    def __init__(self) -> None:
        self.children: dict[str, DAWGNode] = {}
        self.is_terminal: bool = False


def build_trie(words: list[str]) -> DAWGNode:
    """Insert all words into a fresh Trie and return the root node."""
    root = DAWGNode()
    for word in words:
        node = root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = DAWGNode()
            node = node.children[ch]
        node.is_terminal = True
    return root


def _signature(node: DAWGNode, sig_cache: dict[int, tuple]) -> tuple:
    """Compute a hashable signature for a node's entire subtree."""
    node_id = id(node)
    if node_id in sig_cache:
        return sig_cache[node_id]
    sig = (
        node.is_terminal,
        tuple(
            (ch, _signature(child, sig_cache))
            for ch, child in sorted(node.children.items())
        ),
    )
    sig_cache[node_id] = sig
    return sig


def minimize_to_dawg(root: DAWGNode) -> DAWGNode:
    """Minimize a Trie into a DAWG by merging nodes with identical subtrees.

    Walks bottom-up, hashing each node's signature (is_terminal + children
    signatures). Nodes with the same signature are replaced by a single
    shared instance.
    """
    sig_cache: dict[int, tuple] = {}
    canonical: dict[tuple, DAWGNode] = {}

    def _minimize(node: DAWGNode) -> DAWGNode:
        # Minimize children first (bottom-up)
        for ch in node.children:
            node.children[ch] = _minimize(node.children[ch])

        sig = _signature(node, sig_cache)
        if sig in canonical:
            return canonical[sig]
        canonical[sig] = node
        return node

    return _minimize(root)


def count_nodes(root: DAWGNode) -> int:
    """Count unique nodes reachable from root."""
    seen: set[int] = set()

    def _walk(node: DAWGNode) -> None:
        nid = id(node)
        if nid in seen:
            return
        seen.add(nid)
        for child in node.children.values():
            _walk(child)

    _walk(root)
    return len(seen)


def _collect_words(node: DAWGNode, prefix: str, results: list[str]) -> None:
    """Collect all words reachable from node with given prefix."""
    if node.is_terminal:
        results.append(prefix)
    for ch, child in sorted(node.children.items()):
        _collect_words(child, prefix + ch, results)


class DAWG:
    """Word graph built from a word list.

    Construction: builds a Trie then minimizes to a DAWG.
    Provides search and prefix-traversal operations.
    """

    def __init__(self, words: list[str]) -> None:
        trie_root = build_trie(words)
        self._root = minimize_to_dawg(trie_root)

    @classmethod
    def from_file(cls, path: str | Path) -> DAWG:
        """Load words from a text file (one word per line, skip non-alpha lines)."""
        words: list[str] = []
        with open(path) as f:
            for line in f:
                word = line.strip()
                if word and word.isalpha():
                    words.append(word.upper())
        return cls(words)

    @property
    def root(self) -> DAWGNode:
        return self._root

    def search(self, word: str) -> bool:
        """Return True if the exact word exists in the DAWG."""
        node = self._root
        for ch in word.upper():
            if ch not in node.children:
                return False
            node = node.children[ch]
        return node.is_terminal

    def starts_with(self, prefix: str) -> DAWGNode | None:
        """Return the node at the end of prefix, or None if prefix doesn't exist."""
        node = self._root
        for ch in prefix.upper():
            if ch not in node.children:
                return None
            node = node.children[ch]
        return node

    def words_from_node(self, node: DAWGNode, prefix: str) -> list[str]:
        """Collect all words reachable from a given node with the given prefix."""
        results: list[str] = []
        _collect_words(node, prefix, results)
        return results

    def __contains__(self, word: str) -> bool:
        return self.search(word)
