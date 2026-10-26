"""Synthetic behaviors, deliberately not estimates of the named real models."""
import asyncio
import random
import time
from .base import ModelAdapter
from ..cube_engine import MOVES
from ..optimal import ExactSolver, SearchLimit
from ..schemas import AdapterResult


class MockAdapter(ModelAdapter):
    def __init__(self, behavior: str, seed: int, solver: ExactSolver, retries: int = 2):
        self.behavior, self.solver, self.retries = behavior, solver, retries
        self.rng = random.Random(seed)
        self.plan: list[str] = []

    async def get_move(self, state, recent_moves, allowed_moves):
        tick = time.perf_counter()
        if self.behavior in ('smart', 'mixed') and not self.plan:
            try:
                self.plan = await asyncio.to_thread(self.solver.solution, state, 8)
            except SearchLimit:
                self.plan = []
        delay = self.rng.uniform(0.25, 0.45) if self.behavior == 'smart' else self.rng.uniform(0.025, 0.06)
        await asyncio.sleep(delay)
        invalid = self.behavior == 'invalid'
        move = None if invalid else self.plan.pop(0) if self.plan else self.rng.choice(allowed_moves)
        elapsed = (time.perf_counter()-tick)*1000
        return AdapterResult(move=move, valid=not invalid, latency_ms=elapsed,
                             latency_incl_retries_ms=elapsed, raw_response={'synthetic': True, 'move': move},
                             confidence=None, error='Synthetic invalid response' if invalid else None,
                             invalid_outputs=self.retries+1 if invalid else 0, retries_used=self.retries if invalid else 0)
