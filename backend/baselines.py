"""Offline controls. Oracle is deliberately isolated from every live adapter."""
import asyncio
import random
import time
from .adapters.base import ModelAdapter
from .cube_engine import apply_move, solved_state
from .optimal import ExactSolver
from .schemas import AdapterResult


class BaselineAdapter(ModelAdapter):
    def __init__(self, policy: str, seed: int = 0, solver: ExactSolver | None = None):
        if policy not in ('oracle', 'random', 'greedy'):
            raise ValueError('Unknown baseline')
        self.policy, self.rng, self.solver = policy, random.Random(seed), solver

    async def get_move(self, state, recent_moves, allowed_moves):
        started = time.perf_counter()
        if self.policy == 'oracle':
            if self.solver is None:
                raise ValueError('Oracle requires an exact solver')
            path = await asyncio.to_thread(self.solver.solution, state)
            move = path[0]
        elif self.policy == 'random':
            move = self.rng.choice(allowed_moves)
        else:
            target = solved_state()
            scores = {m: sum(a == b for a, b in zip(apply_move(state, m), target)) for m in allowed_moves}
            best = max(scores.values())
            move = self.rng.choice([m for m in allowed_moves if scores[m] == best])
        elapsed = (time.perf_counter()-started)*1000
        return AdapterResult(move=move, valid=True, latency_ms=elapsed, latency_incl_retries_ms=elapsed)
