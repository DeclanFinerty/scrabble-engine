#!/usr/bin/env python3
"""Interactive Scrabble engine REPL.

Usage:
    uv run python scripts/repl.py
    uv run python scripts/repl.py --board path/to/board.txt --rack SATIRED
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from scrabble_engine.board import BOARD_SIZE, Board, BonusSquare, Direction
from scrabble_engine.dawg import DAWG
from scrabble_engine.engine import analyze_position, unplayed_tiles
from scrabble_engine.move_generator import Move, generate_moves
from scrabble_engine.tiles import LETTER_VALUES, Tile

# ANSI color codes
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_BLUE = "\033[34m"
_MAGENTA = "\033[35m"
_CYAN = "\033[36m"

# Bonus square display colors
_BONUS_COLORS = {
    BonusSquare.TRIPLE_WORD: _RED,
    BonusSquare.DOUBLE_WORD: _MAGENTA,
    BonusSquare.TRIPLE_LETTER: _BLUE,
    BonusSquare.DOUBLE_LETTER: _CYAN,
    BonusSquare.CENTER: _MAGENTA,
}


def _format_board(board: Board) -> str:
    """Render the board as a colorized string."""
    lines: list[str] = []
    # Each cell is 3 visible chars wide. Row prefix is " RR |" = 5 chars + "|".
    cell_w = 3
    board_w = BOARD_SIZE * cell_w + 1  # +1 for trailing |

    # Column header — center each number in a 3-char cell
    header = "     |" + "".join(f"{c:^3d}" for c in range(BOARD_SIZE)) + "|"
    lines.append(header)
    lines.append("     +" + "-" * (BOARD_SIZE * cell_w) + "+")

    for r in range(BOARD_SIZE):
        row_parts: list[str] = [f" {r:2d}  |"]
        for c in range(BOARD_SIZE):
            tile = board.get_tile(r, c)
            if tile is not None:
                if tile.is_blank:
                    letter = (tile.blank_letter or "?").lower()
                    row_parts.append(f" {_GREEN}{_BOLD}{letter}{_RESET} ")
                else:
                    row_parts.append(f" {_BOLD}{tile.letter}{_RESET} ")
            else:
                bonus = board.bonus[r][c]
                color = _BONUS_COLORS.get(bonus, "")
                if bonus == BonusSquare.CENTER:
                    row_parts.append(f" {color}*{_RESET} ")
                elif bonus == BonusSquare.TRIPLE_WORD:
                    row_parts.append(f"{color}TW{_RESET} ")
                elif bonus == BonusSquare.DOUBLE_WORD:
                    row_parts.append(f"{color}DW{_RESET} ")
                elif bonus == BonusSquare.TRIPLE_LETTER:
                    row_parts.append(f"{color}TL{_RESET} ")
                elif bonus == BonusSquare.DOUBLE_LETTER:
                    row_parts.append(f"{color}DL{_RESET} ")
                else:
                    row_parts.append(f" {_DIM}.{_RESET} ")
        row_parts.append("|")
        lines.append("".join(row_parts))

    lines.append("     +" + "-" * (BOARD_SIZE * cell_w) + "+")
    return "\n".join(lines)


def _format_rack(rack: list[str]) -> str:
    """Display rack letters with point values."""
    parts: list[str] = []
    for ch in rack:
        pts = LETTER_VALUES.get(ch, 0)
        parts.append(f"{ch}({pts})")
    return " ".join(parts)


def _format_move(move: Move, index: int) -> str:
    """Format a single move for display."""
    dir_str = "ACROSS" if move.direction == Direction.ACROSS else "DOWN  "
    r, c = move.start
    blanks = [t.blank_letter for _, _, t in move.tiles_placed if t.is_blank]
    blank_str = f" [blank={''.join(blanks)}]" if blanks else ""
    cross = ""
    if len(move.words_formed) > 1:
        cross = f" (+{', '.join(move.words_formed[1:])})"
    return (
        f"  {_BOLD}{index:3d}.{_RESET} {_YELLOW}{move.word:<15}{_RESET} "
        f"at ({r:2d},{c:2d}) {dir_str}  "
        f"{_GREEN}{move.score:4d} pts{_RESET}{blank_str}{cross}"
    )


def _parse_position(s: str) -> tuple[int, int, Direction]:
    """Parse a position string like '7,6A' or '3,7D'."""
    s = s.strip().upper()
    if s.endswith("A"):
        direction = Direction.ACROSS
        s = s[:-1]
    elif s.endswith("D"):
        direction = Direction.DOWN
        s = s[:-1]
    else:
        raise ValueError("Position must end with A (across) or D (down)")
    parts = s.split(",")
    if len(parts) != 2:
        raise ValueError("Position must be row,colA or row,colD")
    return int(parts[0]), int(parts[1]), direction


class ScrabbleREPL:
    """Interactive Scrabble engine REPL."""

    def __init__(self, dawg: DAWG) -> None:
        self.dawg = dawg
        self.board = Board()
        self.rack: list[str] = []
        self.last_moves: list[Move] = []

    def run(self) -> None:
        """Main REPL loop."""
        print(f"\n{_BOLD}Scrabble Engine REPL{_RESET}")
        print("Type 'help' for commands.\n")
        self._show_board()

        while True:
            try:
                line = input(f"\n{_CYAN}scrabble>{_RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not line:
                continue

            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            try:
                if cmd in ("q", "quit", "exit"):
                    print("Goodbye!")
                    break
                elif cmd == "help":
                    self._help()
                elif cmd == "board":
                    self._show_board()
                elif cmd == "rack":
                    self._set_rack(arg)
                elif cmd == "analyze":
                    self._analyze(arg)
                elif cmd == "play":
                    self._play(arg)
                elif cmd == "load":
                    self._load_board(arg)
                elif cmd == "save":
                    self._save_board(arg)
                elif cmd == "clear":
                    self._clear_board()
                elif cmd == "remaining":
                    self._show_remaining()
                elif cmd == "place":
                    self._place_word(arg)
                elif cmd == "json":
                    self._export_json(arg)
                else:
                    print(f"Unknown command: {cmd}. Type 'help' for commands.")
            except Exception as e:
                print(f"{_RED}Error: {e}{_RESET}")

    def _help(self) -> None:
        print(f"""
{_BOLD}Commands:{_RESET}
  rack LETTERS        Set rack (e.g., 'rack SATIRED' or 'rack SAT?RE')
  analyze [N]         Show top N moves for current rack (default 10)
  play N              Play move #N from the last analysis
  place WORD R,CA/D   Place a word manually (e.g., 'place HELLO 7,3A')
  board               Show the board
  remaining           Show unplayed tiles
  load FILE           Load board from text file
  save FILE           Save board to text file
  json [FILE]         Export board as JSON (to file or stdout)
  clear               Clear the board
  help                Show this help
  quit                Exit
        """)

    def _show_board(self) -> None:
        print()
        print(_format_board(self.board))
        if self.rack:
            print(f"\n  Rack: {_format_rack(self.rack)}")

    def _set_rack(self, arg: str) -> None:
        if not arg:
            print("Usage: rack LETTERS (e.g., 'rack SATIRED' or 'rack SAT?RE')")
            return
        self.rack = [ch.upper() if ch != "?" else "?" for ch in arg.strip()]
        print(f"  Rack set: {_format_rack(self.rack)}")

    def _analyze(self, arg: str) -> None:
        if not self.rack:
            print("Set a rack first: rack LETTERS")
            return

        n = int(arg) if arg else 10

        print(f"  Analyzing with rack [{', '.join(self.rack)}]...")
        start = time.perf_counter()
        moves = analyze_position(self.board, self.rack, self.dawg)
        elapsed = time.perf_counter() - start

        self.last_moves = moves

        if not moves:
            print("  No legal moves found.")
            return

        print(f"  Found {len(moves)} moves in {elapsed:.2f}s. Top {min(n, len(moves))}:\n")
        for i, move in enumerate(moves[:n], 1):
            print(_format_move(move, i))

        if len(moves) > n:
            print(f"\n  ... and {len(moves) - n} more. Use 'analyze {len(moves)}' to see all.")

    def _play(self, arg: str) -> None:
        if not arg:
            print("Usage: play N (play move #N from last analysis)")
            return
        idx = int(arg) - 1
        if not self.last_moves or idx < 0 or idx >= len(self.last_moves):
            print(f"Invalid move number. Run 'analyze' first.")
            return

        move = self.last_moves[idx]

        # Place tiles on the board
        for r, c, tile in move.tiles_placed:
            self.board.place_tile(r, c, tile)

        # Remove used letters from rack
        used = [tile.letter for _, _, tile in move.tiles_placed]
        for letter in used:
            if letter in self.rack:
                self.rack.remove(letter)
            elif "?" in self.rack:
                self.rack.remove("?")

        print(f"  Played: {move.word} at {move.start} "
              f"{'ACROSS' if move.direction == Direction.ACROSS else 'DOWN'} "
              f"for {move.score} pts")
        if len(move.words_formed) > 1:
            print(f"  Cross-words: {', '.join(move.words_formed[1:])}")
        self._show_board()

    def _place_word(self, arg: str) -> None:
        """Manually place a word: place WORD ROW,COL A/D"""
        parts = arg.split()
        if len(parts) != 2:
            print("Usage: place WORD ROW,COLA/D (e.g., 'place HELLO 7,3A')")
            return
        word = parts[0].upper()
        row, col, direction = _parse_position(parts[1])

        tiles = [Tile.from_letter(ch) for ch in word]
        self.board.place_word(word, (row, col), direction, tiles)
        print(f"  Placed {word} at ({row},{col}) {'ACROSS' if direction == Direction.ACROSS else 'DOWN'}")
        self._show_board()

    def _load_board(self, arg: str) -> None:
        if not arg:
            print("Usage: load FILENAME")
            return
        path = Path(arg)
        text = path.read_text()
        self.board = Board.from_text(text)
        tile_count = sum(
            1 for r in range(BOARD_SIZE) for c in range(BOARD_SIZE)
            if self.board.get_tile(r, c) is not None
        )
        print(f"  Loaded board from {path} ({tile_count} tiles)")
        self._show_board()

    def _save_board(self, arg: str) -> None:
        if not arg:
            print("Usage: save FILENAME")
            return
        path = Path(arg)
        path.write_text(self.board.to_text() + "\n")
        print(f"  Board saved to {path}")

    def _clear_board(self) -> None:
        self.board = Board()
        self.last_moves = []
        print("  Board cleared.")
        self._show_board()

    def _show_remaining(self) -> None:
        pool = unplayed_tiles(self.board)
        total = sum(pool.values())
        print(f"\n  Unplayed tiles ({total} total):")
        line_parts: list[str] = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ?":
            count = pool.get(letter, 0)
            if count > 0:
                pts = LETTER_VALUES.get(letter, 0)
                line_parts.append(f"{letter}:{count}({pts})")
        # Print in rows of 7
        for i in range(0, len(line_parts), 7):
            print("    " + "  ".join(line_parts[i:i + 7]))

    def _export_json(self, arg: str) -> None:
        """Export board state as JSON."""
        data = {
            "board": self.board.to_text(),
            "rack": self.rack,
            "tiles_on_board": sum(
                1 for r in range(BOARD_SIZE) for c in range(BOARD_SIZE)
                if self.board.get_tile(r, c) is not None
            ),
        }
        json_str = json.dumps(data, indent=2)
        if arg:
            Path(arg).write_text(json_str + "\n")
            print(f"  Exported to {arg}")
        else:
            print(json_str)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrabble Engine REPL")
    parser.add_argument("--board", "-b", help="Load initial board from text file")
    parser.add_argument("--rack", "-r", help="Set initial rack letters")
    args = parser.parse_args()

    print("Loading dictionary...", end=" ", flush=True)
    start = time.perf_counter()
    dawg = DAWG.from_file(
        str(Path(__file__).resolve().parent.parent / "src" / "scrabble_engine" / "data" / "twl06.txt")
    )
    elapsed = time.perf_counter() - start
    print(f"done ({elapsed:.1f}s)")

    repl = ScrabbleREPL(dawg)

    if args.board:
        repl._load_board(args.board)
    if args.rack:
        repl._set_rack(args.rack)

    repl.run()


if __name__ == "__main__":
    main()
