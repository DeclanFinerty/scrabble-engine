"""Scrabble scoring: main word, cross-words, bonuses, and bingo."""

from __future__ import annotations

from scrabble_engine.board import BOARD_SIZE, Board, BonusSquare, Direction

BINGO_BONUS = 50


def _letter_multiplier(bonus: BonusSquare) -> int:
    if bonus == BonusSquare.DOUBLE_LETTER:
        return 2
    if bonus == BonusSquare.TRIPLE_LETTER:
        return 3
    return 1


def _word_multiplier(bonus: BonusSquare) -> int:
    if bonus in (BonusSquare.DOUBLE_WORD, BonusSquare.CENTER):
        return 2
    if bonus == BonusSquare.TRIPLE_WORD:
        return 3
    return 1


def score_word(
    board: Board,
    word: str,
    start: tuple[int, int],
    direction: Direction,
    tiles_placed: list[tuple[int, int]],
) -> int:
    """Score a complete move including main word, cross-words, and bingo bonus.

    Args:
        board: The board state AFTER tiles have been placed.
        word: The main word formed.
        start: (row, col) of the first letter of the main word.
        direction: ACROSS or DOWN.
        tiles_placed: List of (row, col) positions where NEW tiles were placed this turn.

    Returns:
        Total score for the move.
    """
    placed_set = set(tiles_placed)

    # Score the main word
    main_score = _score_single_word(board, word, start, direction, placed_set)

    # Score cross-words formed by each newly placed tile
    cross_dir = Direction.DOWN if direction == Direction.ACROSS else Direction.ACROSS
    cross_score = 0

    for r, c in tiles_placed:
        cross_word, cross_start = board.read_word_at(r, c, cross_dir)
        if len(cross_word) > 1:
            cross_score += _score_single_word(
                board, cross_word, cross_start, cross_dir, placed_set
            )

    # Bingo bonus
    bingo = BINGO_BONUS if len(tiles_placed) == 7 else 0

    return main_score + cross_score + bingo


def _score_single_word(
    board: Board,
    word: str,
    start: tuple[int, int],
    direction: Direction,
    placed_positions: set[tuple[int, int]],
) -> int:
    """Score a single word (main or cross-word) with bonuses."""
    row, col = start
    dr = 1 if direction == Direction.DOWN else 0
    dc = 1 if direction == Direction.ACROSS else 0

    word_sum = 0
    word_mult = 1

    for i in range(len(word)):
        r = row + i * dr
        c = col + i * dc
        tile = board.grid[r][c]
        base_points = tile.points  # 0 for blanks

        if (r, c) in placed_positions:
            bonus = board.bonus[r][c]
            base_points *= _letter_multiplier(bonus)
            word_mult *= _word_multiplier(bonus)

        word_sum += base_points

    return word_sum * word_mult
