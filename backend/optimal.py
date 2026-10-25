"""Exact HTM search. Full depth-5 BFS contains 621,649 states.

Default: cache depth 5, then BFS from the puzzle and intersect complete solved
layers. The first complete intersecting puzzle layer proves shortest distance.
No heuristic is used. Exhausting the budget raises, never invents an optimum.
Pickle caches are local/trusted only; never load a user-uploaded pickle.
"""
import os
import pickle
import threading
from collections import deque
from pathlib import Path

from .cube_engine import MOVES, apply_move, deserialize, invert_moves, solved_state


class SearchLimit(RuntimeError):
    pass


class ExactSolver:
    def __init__(self, depth: int = 5, cache: Path | None = None, node_budget: int = 2_000_000):
        self.depth, self.cache, self.node_budget = depth, cache, node_budget
        self.table: dict[str, int] = {}
        self._lock = threading.Lock()

    def build(self) -> None:
        with self._lock:
            if self.table:
                return
            if self.cache and self.cache.exists():
                with self.cache.open('rb') as stream:
                    version, depth, table = pickle.load(stream)
                if version == 'urfdlb-geometry-v1' and depth == self.depth:
                    self.table = table
                    return
            table = {solved_state(): 0}
            layer = [solved_state()]
            for depth in range(1, self.depth+1):
                following = []
                for state in layer:
                    for move in MOVES:
                        nxt = apply_move(state, move)
                        if nxt not in table:
                            table[nxt] = depth
                            following.append(nxt)
                layer = following
            if self.cache:
                self.cache.parent.mkdir(parents=True, exist_ok=True)
                temp = self.cache.with_suffix('.tmp')
                with temp.open('wb') as stream:
                    pickle.dump(('urfdlb-geometry-v1', self.depth, table), stream, protocol=5)
                os.replace(temp, self.cache)
            self.table = table

    def solution(self, state: str, max_depth: int = 8) -> list[str]:
        deserialize(state)
        self.build()
        if state in self.table:
            if self.table[state] > max_depth:
                raise SearchLimit('No solution within requested depth')
            return self._descend(state)
        # Parents encode the path from the query to a state in the solved ball.
        parents: dict[str, tuple[str, str] | None] = {state: None}
        queue = deque([(state, 0, '')])
        active_depth, candidates = 0, []
        max_query_depth = max_depth - self.depth
        while queue:
            current, depth, previous = queue.popleft()
            if depth != active_depth:
                if candidates:
                    break
                active_depth = depth
            if current in self.table:
                candidates.append((depth + self.table[current], current))
                continue
            if depth >= max_query_depth or candidates:
                continue
            for move in MOVES:
                if move[0] == previous:
                    continue
                nxt = apply_move(current, move)
                if nxt in parents:
                    continue
                if len(parents) >= self.node_budget:
                    raise SearchLimit('Exact search node budget exhausted; no proven distance')
                parents[nxt] = (current, move)
                queue.append((nxt, depth+1, move[0]))
        if not candidates:
            raise SearchLimit(f'No solution proven within depth {max_depth}')
        distance, meeting = min(candidates)
        if distance > max_depth:
            raise SearchLimit('No solution within requested depth')
        path = []
        current = meeting
        while parents[current] is not None:
            prev, move = parents[current]
            path.append(move)
            current = prev
        return list(reversed(path)) + self._descend(meeting)

    def _descend(self, state: str) -> list[str]:
        path = []
        while self.table[state]:
            depth = self.table[state]
            for move in MOVES:
                nxt = apply_move(state, move)
                if self.table.get(nxt) == depth-1:
                    path.append(move)
                    state = nxt
                    break
            else:
                raise RuntimeError('Corrupt BFS table')
        return path

    def distance(self, state: str, max_depth: int = 8) -> int:
        return len(self.solution(state, max_depth))


def reference_solution(state: str) -> list[str] | None:
    """Optional two-phase reference; existence/length does not prove optimality."""
    try:
        import kociemba
    except ImportError:
        return None
    if state == solved_state():
        return []
    return kociemba.solve(state).split()
