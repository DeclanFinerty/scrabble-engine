# Scrabble Engine - Development Specification

## Project Overview

A Python-based Scrabble engine that provides dictionary lookup, rack solving, board-aware move generation, and optimal play scoring. Designed to integrate with `scrabble-vision` (board scanner) and eventually a learning app ("Duolingo for Scrabble").

**Package manager:** uv
**Language:** Python 3.12+
**Project directory:** `scrabble-engine/`

---

## Architecture

```
scrabble-engine/
├── SPEC.md                          # This file - development reference
├── README.md                        # Project overview and usage
├── pyproject.toml
├── src/scrabble_engine/
│   ├── __init__.py
│   ├── dawg.py                      # DAWG data structure
│   ├── dictionary.py                # Word list loading, validation, querying
│   ├── tiles.py                     # Tile definitions, bag, rack management
│   ├── board.py                     # Board state, bonus squares, placement
│   ├── scoring.py                   # Word and move scoring
│   ├── move_generator.py           # Board-aware legal move generation
│   ├── engine.py                    # Top-level API tying everything together
│   └── data/
│       └── twl06.txt                # Official word list (one word per line, uppercase)
├── tests/
│   ├── test_dictionary.py
│   ├── test_dawg.py
│   ├── test_tiles.py
│   ├── test_board.py
│   ├── test_scoring.py
│   ├── test_move_generator.py
│   └── test_engine.py
└── scripts/
    └── repl.py                      # Interactive CLI for manual testing
```

---

## Data Structures

### Tile

```python
@dataclass
class Tile:
    letter: str          # A-Z or '?' for blank
    points: int          # point value (0 for blank)
    is_blank: bool       # True if this tile is a blank representing a letter
    blank_letter: str | None  # The letter a blank is representing, or None
```

### Standard tile distribution (100 tiles total)

| Letter | Count | Points |
|--------|-------|--------|
| A | 9 | 1 | B | 2 | 3 | C | 2 | 3 | D | 4 | 2 |
| E | 12 | 1 | F | 2 | 4 | G | 3 | 2 | H | 2 | 4 |
| I | 9 | 1 | J | 1 | 8 | K | 1 | 5 | L | 4 | 1 |
| M | 2 | 3 | N | 6 | 1 | O | 8 | 1 | P | 2 | 3 |
| Q | 1 | 10 | R | 6 | 1 | S | 4 | 1 | T | 6 | 1 |
| U | 4 | 1 | V | 2 | 4 | W | 2 | 4 | X | 1 | 8 |
| Y | 2 | 4 | Z | 1 | 10 | ? (blank) | 2 | 0 |

### Board (15x15)

```python
class Board:
    grid: list[list[Tile | None]]     # 15x15, None = empty
    bonus: list[list[BonusSquare]]    # 15x15, bonus type at each position

class BonusSquare(Enum):
    NONE = "."
    DOUBLE_LETTER = "DL"
    TRIPLE_LETTER = "TL"
    DOUBLE_WORD = "DW"
    TRIPLE_WORD = "TW"
    CENTER = "★"                      # Also acts as DW on first move
```

### Standard bonus square layout

The layout is symmetric across both diagonals. Define one quadrant and mirror it. The center square (7,7) is the star/DW.

```
TW .  .  DL .  .  .  TW .  .  .  DL .  .  TW
.  DW .  .  .  TL .  .  .  TL .  .  .  DW .
.  .  DW .  .  .  DL .  DL .  .  .  DW .  .
DL .  .  DW .  .  .  DL .  .  .  DW .  .  DL
.  .  .  .  DW .  .  .  .  .  DW .  .  .  .
.  TL .  .  .  TL .  .  .  TL .  .  .  TL .
.  .  DL .  .  .  DL .  DL .  .  .  DL .  .
TW .  .  DL .  .  .  ★  .  .  .  DL .  .  TW
.  .  DL .  .  .  DL .  DL .  .  .  DL .  .
.  TL .  .  .  TL .  .  .  TL .  .  .  TL .
.  .  .  .  DW .  .  .  .  .  DW .  .  .  .
DL .  .  DW .  .  .  DL .  .  .  DW .  .  DL
.  .  DW .  .  .  DL .  DL .  .  .  DW .  .
.  DW .  .  .  TL .  .  .  TL .  .  .  DW .
TW .  .  DL .  .  .  TW .  .  .  DL .  .  TW
```

### Move

```python
@dataclass
class Move:
    word: str                         # The full word formed
    start: tuple[int, int]            # (row, col) of first letter
    direction: Direction              # ACROSS or DOWN
    tiles_placed: list[tuple[int, int, Tile]]  # positions and tiles from rack
    score: int                        # total points including bonuses
    words_formed: list[str]           # all words created (main + cross-words)
```

### DAWG Node

```python
class DAWGNode:
    children: dict[str, DAWGNode]     # letter -> child node
    is_terminal: bool                 # True if a valid word ends here
```

**Construction is two explicit steps:**

1. `build_trie(words)` — Insert all words into a standard Trie (simple, incremental insertion).
2. `minimize_to_dawg(trie)` — Walk the Trie bottom-up, hash each node's subtree signature (children + is_terminal), and merge nodes with identical signatures. This shares suffix structures and significantly reduces memory usage.

This two-step approach keeps insertion logic simple and separates the optimization pass cleanly. Both the Trie and the minimized DAWG use the same `DAWGNode` structure — minimization only changes which nodes the `children` dicts point to.

---

## Development Phases

### Phase 1: Dictionary & Word Retrieval

**Goal:** Load the word list and answer queries about words.

**Files:** `dictionary.py`, `dawg.py`, `test_dictionary.py`, `test_dawg.py`

**Deliverables:**

1. Load TWL06 (or SOWPODS) word list from text file into a DAWG (built via Trie then minimized)
2. Implement these query functions:
   - `is_valid(word: str) -> bool`
   - `words_by_length(n: int) -> list[str]`
   - `words_starting_with(prefix: str) -> list[str]`
   - `words_ending_with(suffix: str) -> list[str]`
   - `words_containing(substring: str) -> list[str]`
   - `words_matching_pattern(pattern: str) -> list[str]`
     - Pattern uses `.` for any single letter: `..G` = 3-letter words ending in G
     - Pattern uses specific letters at positions: `S....` = 5-letter words starting with S

**Test cases:**
- `is_valid("QI")` → True
- `is_valid("QX")` → False
- `words_by_length(2)` → 107 words (TWL06)
- `words_matching_pattern("..G")` → includes "BAG", "BIG", "BOG", "BUG", "COG", "DIG", "DOG", "EGG", "FIG", "FOG", "GAG", "GIG", "HOG", "HUG", "JAG", "JIG", "JOG", "JUG", "KEG", "LAG", "LEG", "LOG", "LUG", "MAG", "MIG", "MOG", "MUG", "NAG", "NOG", "NUG", "PEG", "PIG", "PUG", "RAG", "RIG", "RUG", "SAG", "SEG", "SOG", "TAG", "TUG", "URG", "VEG", "WAG", "WIG", "ZAG", "ZIG"
- `words_ending_with("ING")` → large set, verify a few known ones

**Performance target:** All queries under 100ms on full dictionary.

**Getting the word list:** Search for "TWL06 word list" or "SOWPODS word list" in open-source Scrabble projects on GitHub. The file should be one uppercase word per line. Place in `src/scrabble_engine/data/twl06.txt`. If you can't find a clean copy, Collins Scrabble Words (CSW) is also fine -- just note which one you're using. The important thing is to have a single source of truth text file.

---

### Phase 2: Tiles & Rack

**Goal:** Model tiles, the bag, and rack management.

**Files:** `tiles.py`, `test_tiles.py`

**Deliverables:**

1. Define tile values and distribution (see table above)
2. `TileBag` class:
   - Initialize with standard 100-tile distribution
   - `draw(n: int) -> list[Tile]` — draw n random tiles
   - `remaining() -> dict[str, int]` — count of each letter remaining
   - `remove(letters: list[str])` — remove specific tiles (for board setup)
   - `tiles_in_bag() -> int` — total remaining
3. `Rack` class:
   - Holds up to 7 tiles
   - `add(tiles: list[Tile])`
   - `remove(tiles: list[Tile])`
   - `letters() -> list[str]` — sorted list of letters on rack
4. Anagram/rack solver:
   - `find_words(rack: list[str]) -> list[str]`
   - Given a set of letters (e.g., ["A", "E", "R", "S", "T", "I", "N"]), find ALL valid words that can be formed using subsets of those letters
   - Must handle duplicate letters correctly: if rack has one "S", can't use "S" twice

**Algorithm for rack solving:**
- Use the DAWG: traverse it, consuming letters from the rack as you go
- At each node, try each available rack letter as the next step
- If the node is terminal, record the word
- This is efficient because the DAWG prunes impossible paths early

**Test cases:**
- `find_words(["C", "A", "T"])` → includes "ACT", "AT", "CAT", "TA" (and others valid in dictionary)
- `find_words(["Q", "I"])` → includes "QI"
- `find_words(["A", "A", "R", "D", "V", "K"])` should NOT include "AARDVARK" (not enough letters)
- Standard bag has exactly 100 tiles
- After drawing 7, bag has 93

---

### Phase 3: Board State & Scoring

**Goal:** Represent the board, place words, score them correctly.

**Files:** `board.py`, `scoring.py`, `test_board.py`, `test_scoring.py`

**Deliverables:**

1. `Board` class:
   - 15x15 grid initialized to empty
   - Bonus square layout hardcoded (see layout above)
   - `place_word(word: str, start: tuple[int, int], direction: Direction, tiles: list[Tile])` — place tiles on board
   - `get_tile(row: int, col: int) -> Tile | None`
   - `is_occupied(row: int, col: int) -> bool`
   - `get_anchor_squares() -> list[tuple[int, int]]` — empty squares adjacent to occupied squares (critical for move generation)
   - `get_cross_checks(row: int, col: int, direction: Direction) -> set[str]` — which letters are valid at this position given perpendicular constraints
   - Export/import board state as 15x15 text grid (for integration with scrabble-vision)

2. Scoring:
   - `score_word(board: Board, word: str, start: tuple[int, int], direction: Direction, tiles_placed: list[tuple[int, int]]) -> int`
   - **Critical scoring rules:**
     - Letter bonuses (DL, TL) only apply to tiles placed THIS turn, not existing tiles
     - Word bonuses (DW, TW) only apply if at least one tile in the word was placed THIS turn on that bonus square
     - If multiple word bonuses apply, they multiply (e.g., DW × TW = ×6)
     - Cross-words formed by newly placed tiles are also scored (with their own bonuses)
     - **Bingo bonus:** +50 points if all 7 tiles from rack are used in a single play
     - Blank tiles contribute 0 points regardless of what letter they represent

**Scoring algorithm detail:**

```
For each newly placed tile:
  1. Score the main word:
     - For each letter in the main word:
       - base = tile.points
       - If this position was placed THIS turn AND has DL/TL: multiply base
       - Add base to word_sum
     - For each bonus square touched by a newly placed tile:
       - If DW or TW: note the word multiplier
     - main_word_score = word_sum × product(word_multipliers)

  2. Score each cross-word formed:
     - Same logic: letter bonuses only on the new tile, word bonuses only on new tile position
     - Add cross-word scores

  3. If 7 tiles placed: add 50 point bingo bonus

  total = main_word_score + sum(cross_word_scores) + bingo_bonus
```

**Test cases:**
- First word through center: "HELLO" at (7,3) ACROSS → center star acts as DW → score = (4+1+1+1+1) × 2 = 16
- Verify DL/TL only count for newly placed tiles
- Verify cross-word scoring
- Verify bingo bonus

---

### Phase 4: Move Generation

**Goal:** Given a board state and a rack, generate all legal moves.

**Files:** `move_generator.py`, `test_move_generator.py`

**This is the most complex phase.** The algorithm is based on the Appel & Jacobson approach.

**Key concepts:**

1. **Anchor squares:** Empty squares adjacent to at least one occupied square. Every new word must pass through at least one anchor. On an empty board, only the center square is an anchor.

2. **Cross-checks:** For each empty square, the set of letters that can legally go there without breaking perpendicular words. Precompute these before generating moves.

3. **Left parts and right extension:** For each anchor square in each direction:
   - Determine how far left (or up) you can extend before hitting another anchor or the board edge
   - Generate all possible left parts from the rack that form valid DAWG prefixes
   - For each left part, extend right (or down) through the anchor, consuming rack tiles and/or existing board tiles, following the DAWG and respecting cross-checks

**Algorithm (for ACROSS moves — DOWN is symmetric):**

```
For each row:
  Compute cross-checks for each empty cell in this row
  Find anchor squares in this row

  For each anchor square at column c:
    # Determine left limit
    left_limit = number of empty, non-anchor squares to the left of c

    # Generate moves by building left part then extending right
    LeftPart("", dawg.root, anchor_col=c, limit=left_limit, rack)

LeftPart(partial_word, node, anchor_col, limit, rack):
  ExtendRight(partial_word, node, anchor_col, rack)
  if limit > 0:
    for each letter L available on rack:
      if L in node.children:
        remove L from rack
        LeftPart(partial_word + L, node.children[L], anchor_col, limit - 1, rack)
        put L back on rack

ExtendRight(partial_word, node, col, rack):
  if col is off the board: return
  square = board[row][col]

  if square is empty:
    if node.is_terminal and len(partial_word) > 1:
      record_move(partial_word, ...)
    for each letter L available on rack:
      if L in node.children and L in cross_checks[col]:
        remove L from rack
        ExtendRight(partial_word + L, node.children[L], col + 1, rack)
        put L back on rack

  else:  # square is occupied with letter L
    if L in node.children:
      ExtendRight(partial_word + L, node.children[L], col + 1, rack)
```

**Deliverables:**
1. `generate_moves(board: Board, rack: list[str]) -> list[Move]`
   - Returns ALL legal moves, each with full scoring
   - Sorted by score descending
2. `best_moves(board: Board, rack: list[str], n: int = 10) -> list[Move]`
   - Top n moves by score
3. Handle the empty board case (first move must cross center square)
4. Validate that all cross-words are valid dictionary words

**Test cases:**
- Empty board + rack ["C","A","T","S","D","O","G"] → should find "CATS", "DOGS", "COATS", etc. placed through center
- Board with "CAT" placed → rack with ["S"] → should find "CATS" (hooking S)
- Board with "HELLO" → verify cross-word constraints work
- Known board positions with known best moves (find these from online Scrabble resources)

---

### Phase 5: Game Logic & Tile Tracking

**Goal:** Full game state management.

**Files:** `engine.py`, `test_engine.py`

**Deliverables:**

1. `GameState` class:
   - Board, bag, player racks, scores, move history
   - Track which tiles have been played → infer what's left in bag + opponent's possible tiles
   - `play_move(move: Move)` — validate, place tiles, score, draw new tiles
   - `remaining_tiles() -> dict[str, int]` — what's unaccounted for (bag + opponent rack)
   - `is_game_over() -> bool`
   - `exchange_tiles(tiles: list[Tile]) -> list[Tile]` — exchange tiles with bag

2. Analysis mode (no bag draw, for studying positions):
   - `analyze_position(board: Board, rack: list[str]) -> list[Move]`
   - "Given this board (from scrabble-vision) and this rack, what are the best plays?"

3. Board-only analysis:
   - `best_possible_moves(board: Board, n: int = 10) -> list[Move]`
   - "Given this board and no rack constraint, what are the highest-scoring possible plays?"
   - This uses remaining tiles (100 - tiles on board) as the pool
   - Computationally expensive — may need to limit search or accept longer runtime

**Test cases:**
- Full game simulation: play several moves, verify scores, verify tile counts
- Import board from 15x15 text grid, run analysis
- Verify remaining tile tracking after several plays

---

### Phase 6: Blank Tile Support

**Goal:** Handle blank tiles in rack and on board.

**Changes across multiple files.**

**Deliverables:**

1. Rack solver with blanks:
   - Blank ("?") can represent any letter
   - When traversing the DAWG with a blank, try ALL 26 children
   - Return results indicating which letter the blank represents
   - `find_words(["A", "?", "T"])` → includes "AAT", "ABT" (if valid), etc.

2. Board blanks:
   - When placing a blank on the board, record what letter it represents
   - Blank tiles always score 0 points regardless of letter
   - Cross-check computation must recognize blanks on the board

3. Move generation with blanks:
   - Same expansion: when rack contains "?", try all 26 possibilities at each step
   - This makes generation ~26x slower per blank — two blanks = ~676x
   - May need optimization (pruning, caching)

**Test cases:**
- Rack ["?", "A", "T"] should find more words than ["B", "A", "T"]
- Blank on board representing "S" should score 0 for that tile
- Verify blank-as-S still enables valid cross-words

---

### Phase 7: CLI & Integration

**Goal:** Usable interactive interface and scrabble-vision integration.

**Files:** `scripts/repl.py`

**Deliverables:**

1. Interactive REPL:
   - Load/display board state
   - Input rack letters
   - Show top N moves with scores
   - Place a move and update board
   - Show remaining tiles

2. Integration with scrabble-vision:
   - Accept 15x15 grid from vision pipeline (text format)
   - Parse into Board object
   - Run analysis

3. Board state I/O:
   - Text format: 15 lines of 15 characters, `.` for empty, `a-z` for blanks (lowercase), `A-Z` for regular tiles
   - JSON format for programmatic use

---

## Performance Expectations

| Operation | Target | Notes |
|-----------|--------|-------|
| Dictionary load | < 2s | One-time startup |
| Word lookup | < 1ms | DAWG traversal |
| Pattern query | < 100ms | Full dictionary scan OK |
| Rack solve (7 tiles) | < 100ms | DAWG-guided search |
| Move generation | < 2s | Full board, 7-tile rack |
| Move gen with 1 blank | < 10s | 26x expansion |
| Move gen with 2 blanks | < 60s | May need optimization |

If Python performance is insufficient for move generation (especially with blanks), the move generator inner loop is a clean candidate for Rust via PyO3. Cross that bridge if needed.

---

## Testing Strategy

- Use `pytest` (add with `uv add --dev pytest`)
- Each phase has its own test file
- Test against known Scrabble positions and scores
- Use the uploaded board images (from scrabble-vision) as integration test inputs once Phase 7 is reached
- For move generation, cross-reference against online Scrabble solvers to verify correctness

---

## Word List Note

The TWL06 (Tournament Word List, 6th edition) contains ~178,691 words and is the standard for North American Scrabble. Collins Scrabble Words (CSW, ~280,000 words) is the international standard and is a superset. Pick one and stick with it. TWL06 is recommended for simplicity and because it's the standard for competitive play in North America.

The word list file should be one word per line, all uppercase, no extra whitespace. Example:

```
AA
AAH
AAHED
AAHING
AAHS
AAL
...
```

---

## Key References

- **Appel & Jacobson (1988):** "The World's Fastest Scrabble Program" — the canonical move generation algorithm
- **GADDAG:** An alternative to DAWG that enables both left and right extension, potentially simpler move generation code (by Steven Gordon, 1994)
- **Open source Scrabble engines:** quackle (C++), elise (Rust), macondo (Go) — useful as cross-references for correctness

---

## Integration Points with scrabble-vision

The vision pipeline outputs a 15x15 grid of recognized letters. The engine should accept this as input:

```python
# From scrabble-vision
grid_text = """
...............
...............
...............
.....HELLO.....
.........E.....
.........A.....
.........R.....
.........N.....
...............
...............
...............
...............
...............
...............
...............
"""

board = Board.from_text(grid_text)
moves = engine.analyze_position(board, rack=["S", "T", "A", "R", "E", "D", "?"])
```

This is the contract between the two systems. Vision produces the grid text, engine consumes it.