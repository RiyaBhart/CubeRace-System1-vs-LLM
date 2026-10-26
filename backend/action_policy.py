"""Assisted-only visited-state filter. No search, score ranking or solver calls."""
from .cube_engine import MOVES, apply_move


def offered_moves(state: str, visited: set[str], enabled: bool) -> tuple[tuple[str, ...], bool]:
    if not enabled:
        return MOVES, False
    offered = tuple(move for move in MOVES if apply_move(state, move) not in visited)
    # Never end a game because a heuristic says it will fail. A fully explored
    # neighbourhood restores legal actions and is recorded explicitly.
    return (offered, False) if offered else (MOVES, True)
