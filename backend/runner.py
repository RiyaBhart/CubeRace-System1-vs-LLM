import asyncio
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable

from .adapters.base import ModelAdapter
from .config import ModelConfig, Settings
from .cube_engine import MOVES, apply_move, is_solved, solved_state
from .schemas import AdapterResult, GameResult, MoveRecord
from .accounting import summarize_usage

EventSink = Callable[[str, dict], Awaitable[None]]


def percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered)-1)*percent/100
    lo = int(position)
    hi = min(lo+1, len(ordered)-1)
    return ordered[lo] + (ordered[hi]-ordered[lo])*(position-lo)


async def run_game(model: ModelConfig, adapter: ModelAdapter, start_state: str, *,
                   config: Settings, run_id: str, puzzle_id: str, seed: int,
                   scramble: list[str], repeat: int = 0, exact_optimal: int | None = None,
                   reference_moves: int | None = None, emit: EventSink | None = None,
                   smoke: bool = False) -> GameResult:
    result = GameResult(attempt_id=f'{puzzle_id}:{repeat}:{model.key}', run_id=run_id,
        model=model.key, model_id=model.id, model_name=model.name, category=model.category,
        mock=config.mock_models, diagnostic=smoke, puzzle_id=puzzle_id, seed=seed, scramble=scramble,
        start_state=start_state, final_state=start_state, repeat=repeat, exact_optimal=exact_optimal,
        reference_moves=reference_moves, reference_label='reference, not proven optimal' if reference_moves is not None else None,
        config={'max_moves': config.max_moves, 'time_limit_s': config.game_timeout_s,
                'recent_moves_n': config.recent_moves_n, 'max_retries': config.max_retries,
                'invalid_consumes_attempt': config.invalid_consumes_attempt,
                'history_policy': 'complete legal move history',
                'claude_reasoning_effort': config.claude_reasoning_effort,
                'claude_max_tokens': config.claude_max_tokens})

    async def event(kind, payload):
        if emit:
            await emit(kind, {'model': model.key, 'puzzle_id': puzzle_id, 'repeat': repeat, **payload})

    await event('game_start', {'game': result.model_dump()})
    began = time.perf_counter()
    state, history = start_state, []
    result.status = 'RAN_OUT_OF_MOVES'
    try:
        while not is_solved(state) and result.attempts_used < config.max_moves:
            remaining = config.game_timeout_s-(time.perf_counter()-began)
            if remaining <= 0:
                result.status = 'OUT_OF_TIME'
                break
            await event('thinking', {'elapsed_s': time.perf_counter()-began})
            call_began = time.perf_counter()
            try:
                response = await asyncio.wait_for(adapter.get_move(state, list(history), MOVES), timeout=remaining)
            except asyncio.TimeoutError:
                elapsed = (time.perf_counter()-call_began)*1000
                response = getattr(adapter, 'partial_result', None) or AdapterResult(latency_ms=elapsed)
                response.error = 'Game deadline interrupted request'
                response.fatal = True
                response.valid = False
                response.latency_incl_retries_ms = elapsed
                result.status = 'OUT_OF_TIME'
            except Exception as exc:
                response = AdapterResult(error=f'Adapter error: {type(exc).__name__}', fatal=True)
            valid = response.valid and response.move in MOVES
            if response.not_run or (response.budget_exhausted and not response.calls):
                result.status = 'BUDGET_EXHAUSTED' if result.records else 'NOT_RUN'
                result.error = response.error
                break
            if response.valid and not valid:
                response.valid = False
                response.invalid_outputs += 1
                response.error = 'Adapter returned a move outside allowed set'
            result.retry_count += response.retries_used
            result.invalid_count += response.invalid_outputs
            if response.tokens is not None:
                result.tokens = (result.tokens or 0) + response.tokens
            if response.cost is not None:
                result.cost = (result.cost or 0) + response.cost
            # Never apply a response that finished at or beyond the deadline.
            if time.perf_counter()-began >= config.game_timeout_s:
                result.status = 'OUT_OF_TIME'
                valid = False
            elif valid:
                state = apply_move(state, response.move)
                history.append(response.move)
                result.moves_used += 1
                result.attempts_used += 1
            elif config.invalid_consumes_attempt and not response.fatal:
                result.attempts_used += 1
            record = MoveRecord(index=len(result.records)+1, move=response.move, latency_ms=response.latency_ms,
                latency_incl_retries_ms=response.latency_incl_retries_ms, confidence=response.confidence,
                valid=valid, retries=response.retries_used, invalid_outputs=response.invalid_outputs,
                state_after=state, timestamp=datetime.now(timezone.utc).isoformat(),
                elapsed_s=time.perf_counter()-began, response=response)
            result.records.append(record)
            result.final_state = state
            result.error = response.error
            await event('move', {'record': record.model_dump(), 'moves_used': result.moves_used,
                                 'attempts_used': result.attempts_used})
            if result.status == 'OUT_OF_TIME':
                break
            if response.unavailable:
                result.status = 'UNAVAILABLE'
                break
            if response.fatal:
                result.status = 'BUDGET_EXHAUSTED' if response.budget_exhausted else 'ERROR'
                break
            if smoke:
                result.status = 'SMOKE_TEST' if valid else 'ERROR'
                break
        if is_solved(state):
            result.status = 'SOLVED'
    finally:
        result.total_time_s = time.perf_counter()-began
    latencies = [r.latency_ms for r in result.records]
    result.avg_latency_ms = sum(latencies)/len(latencies) if latencies else None
    result.median_latency_ms = percentile(latencies, 50)
    result.p95_latency_ms = percentile(latencies, 95)
    result.avg_latency_incl_retries_ms = (sum(r.latency_incl_retries_ms for r in result.records)/len(result.records)) if result.records else None
    billing = summarize_usage([c for r in result.records for c in r.response.calls])
    for field in ('tokens', 'cost', 'known_cost', 'unknown_cost_requests', 'requests_used', 'reasoning_tokens'):
        setattr(result, field, billing[field])
    if result.status == 'SOLVED' and exact_optimal is not None:
        result.optimality_gap = result.moves_used-exact_optimal
        if result.optimality_gap < 0:
            raise RuntimeError('Negative optimality gap: engine/search invariant violated')
    await event('game_end', {'game': result.model_dump()})
    return result


def rank_games(games: list[GameResult]) -> list[GameResult]:
    target = solved_state()
    return sorted((g for g in games if g.status != 'NOT_RUN' and not g.diagnostic), key=lambda g: (g.status != 'SOLVED',
        g.moves_used if g.status == 'SOLVED' else -sum(a == b for a, b in zip(g.final_state, target)),
        g.total_time_s, g.model))
