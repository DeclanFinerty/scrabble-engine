# scrabble-engine

A Python Scrabble engine for dictionary lookup, move generation, and optimal play analysis. Part of a larger project to build a "Duolingo for Scrabble" learning platform.

## What It Does

- **Word retrieval:** Find words by length, pattern, prefix, suffix, or contained letters
- **Rack solving:** Given 7 tiles, find all playable words
- **Move generation:** Given a board and rack, find all legal moves with scores
- **Best play analysis:** Rank moves by score, including cross-word scoring and bonus squares
- **Game state tracking:** Tile bag, remaining letters, score tracking

## Architecture

Built in phases, each extending the previous:

1. **Dictionary & Trie** — word list indexed for fast lookup and traversal
2. **Tiles & Rack** — tile values, bag management, anagram solving
3. **Board & Scoring** — 15x15 board with bonus squares, correct scoring rules
4. **Move Generator** — Appel & Jacobson algorithm for exhaustive legal move search
5. **Game Logic** — full state management, tile tracking, analysis mode
6. **Blank Support** — wildcard tile handling in rack and on board
7. **CLI & Integration** — interactive REPL, scrabble-vision bridge

See [SPEC.md](SPEC.md) for the full development specification.

## Integration

Designed to accept board state from [scrabble-vision](../scrabble-vision) (board scanner) as a 15x15 text grid:

```python
from scrabble_engine import Engine

board = Board.from_text(grid_from_vision)
moves = engine.analyze_position(board, rack=["S", "T", "A", "R", "E", "D"])
for move in moves[:10]:
    print(f"{move.word} at {move.start} {move.direction}: {move.score} pts")
```

## Setup

```bash
cd scrabble-engine
uv sync
uv run pytest
```

## Word List

Uses TWL06 (Tournament Word List, North American standard, ~178K words). Place `twl06.txt` in `src/scrabble_engine/data/`.