"""Seeded scrambles, avoiding repeated faces and reducible commuting triples."""
import random
from .cube_engine import MOVES, apply_moves, solved_state

OPPOSITE = dict(zip('UDLRFB', 'DURLBF'))


def generate_scramble(length: int, seed: int) -> list[str]:
    if length < 0:
        raise ValueError('length must be nonnegative')
    rng = random.Random(seed)
    moves: list[str] = []
    for _ in range(length):
        choices = [m for m in MOVES if not moves or (
            m[0] != moves[-1][0] and not (
                len(moves) >= 2 and m[0] == moves[-2][0]
                and moves[-1][0] == OPPOSITE[m[0]]))]
        moves.append(rng.choice(choices))
    return moves


def puzzle(length: int, seed: int) -> tuple[list[str], str]:
    moves = generate_scramble(length, seed)
    return moves, apply_moves(solved_state(), moves)
