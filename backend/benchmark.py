"""CLI and web orchestration. Completed attempts survive interruption/resume."""
import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .config import MODELS, Settings, settings
from .budget import Ledger
from .cube_engine import MOVES, self_test, solved_state
from .logging_config import configure_logging
from .optimal import ExactSolver, SearchLimit, reference_solution
from .runner import EventSink, rank_games, run_game
from .scramble import puzzle
from .storage import Store
from .presentation import PRESENTATION_VERSION
from .transport import adapter_for, create_client, warmup

SEEDS = (104729, 130363, 155921, 181081, 206369, 232003, 257053, 282413, 307939, 333667)
RANGES = {'warmup': (3, 4), 'primary': (4, 5), 'extension': (15, 20)}


class BenchmarkRequest(BaseModel):
    set: Literal['warmup', 'primary', 'extension', 'race', 'smoke'] = 'primary'
    puzzles: int = Field(10, ge=1, le=100)
    repeats: int = Field(1, ge=1, le=20)
    mode: Literal['concurrent', 'sequential'] = 'concurrent'
    seed: int = Field(104729, ge=0, le=2**32-1)
    length: int = Field(4, ge=1, le=20)
    condition: Literal['pure', 'assisted'] = Field(default_factory=lambda: settings.condition)
    history_length: int = Field(default_factory=lambda: settings.history_length, ge=-1, le=30)
    max_moves: int | None = Field(None, ge=1, le=30)
    baselines: bool = False
    loop_avoidance: bool = True
    execution: Literal['simulated', 'live'] = 'simulated'
    live_approved: bool = False
    request_cap: int | None = Field(None, ge=1, le=10_000_000)

    @model_validator(mode='after')
    def check_primary(self):
        if self.set == 'primary' and self.puzzles < 5:
            raise ValueError('Primary requires at least five puzzles; use race for one puzzle')
        if self.set in ('race', 'smoke') and (self.puzzles != 1 or self.repeats != 1):
            raise ValueError('Race requires one puzzle and one repeat')
        return self


def recommended_cap(request: BenchmarkRequest, config: Settings) -> int:
    return 4 if request.set == 'smoke' else request.puzzles * request.repeats * len(MODELS) * (request.max_moves or config.max_moves) * (1+config.max_retries)


def run_settings(request: BenchmarkRequest, config: Settings) -> Settings:
    if request.execution == 'live':
        if config.mock_models:
            raise PermissionError('MOCK_MODELS=1 disables live execution')
        if not request.live_approved or request.request_cap is None:
            raise PermissionError('Explicit per-run live approval and request cap are required')
        if not config.openrouter_api_key.get_secret_value():
            raise PermissionError('No API key configured')
    return config.model_copy(update={'mock_models': request.execution != 'live',
        'max_retries': 0 if request.set == 'smoke' else config.max_retries,
        'condition': request.condition, 'history_length': request.history_length,
        'loop_avoidance': request.loop_avoidance,
        'max_moves': request.max_moves or config.max_moves})


def new_run_id() -> str:
    import uuid
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]


async def execute(request: BenchmarkRequest, config: Settings, run_id: str,
                  solver: ExactSolver, emit: EventSink | None = None, client=None) -> Store:
    config = run_settings(request, config)
    ledger = None if config.mock_models else await asyncio.to_thread(Ledger, config.results_dir, config.live_request_limit)
    permit = None if ledger is None else await asyncio.to_thread(ledger.approve, run_id, request.request_cap)
    fingerprint = {'presentation_version': PRESENTATION_VERSION, 'request': request.model_dump(), 'mock': config.mock_models,
        'models': [m.model_dump() for m in MODELS], 'max_moves': config.max_moves,
        'game_timeout_s': config.game_timeout_s, 'request_timeout_s': config.request_timeout_s,
        'recent_moves_n': config.recent_moves_n, 'max_retries': config.max_retries,
        'claude_reasoning_effort': config.claude_reasoning_effort, 'claude_max_tokens': config.claude_max_tokens,
        'history_policy': 'all' if config.history_length == -1 else str(config.history_length),
        'history_length': config.history_length, 'condition': config.condition, 'loop_avoidance': config.loop_avoidance,
        'truncation_policy': 'stop_game_error',
        'invalid_consumes_attempt': config.invalid_consumes_attempt, 'retry_backoff_s': config.retry_backoff_s,
        'bfs_depth': config.bfs_depth, 'exact_max_depth': config.exact_max_depth,
        'exact_node_budget': config.exact_node_budget, 'use_kociemba': config.use_kociemba}
    metadata = {'run_id': run_id, 'set': request.set, 'mode': request.mode,
                'mock': config.mock_models, 'condition': config.condition,
                'action_policy': 'avoid_visited' if config.condition == 'assisted' and config.loop_avoidance else 'unrestricted',
                'fingerprint': fingerprint,
                'recommended_request_cap': recommended_cap(request, config)}
    store = await asyncio.to_thread(Store, config.results_dir, run_id, metadata)
    if store.metadata.get('fingerprint') != fingerprint:
        raise ValueError('Resume configuration differs from original run')
    def persist(game=None):
        if ledger:
            store.metadata['billing'] = ledger.summary(run_id)
            store.metadata['suite_billing'] = ledger.summary()
        store.save(game)
    await asyncio.to_thread(persist)
    own_client = client is None
    client = client or create_client(config)
    try:
        await warmup(client, config)
        completed = {g.attempt_id for g in store.games}
        for i in range(request.puzzles):
            seed = request.seed if request.set in ('race', 'smoke') else SEEDS[i % len(SEEDS)] + (request.seed-SEEDS[0]) + (i//len(SEEDS))*1_000_003
            lo, hi = RANGES.get(request.set, (request.length, request.length))
            length = lo + i % (hi-lo+1)
            scramble, state = puzzle(length, seed)
            puzzle_id = f'{request.set}-{i}-{seed}-{length}'
            exact, reference = None, None
            if length <= 8:
                try:
                    exact = await asyncio.to_thread(solver.distance, state, config.exact_max_depth)
                except SearchLimit:
                    # Primary must not silently lose its required ground truth.
                    if request.set in ('primary', 'warmup'):
                        raise
                    logging.getLogger(__name__).warning('No exact optimum proven for %s', puzzle_id)
            elif config.use_kociemba:
                solution = await asyncio.to_thread(reference_solution, state)
                reference = len(solution) if solution is not None else None
            for repeat in range(request.repeats):
                pending = [m for m in MODELS if f'{puzzle_id}:{repeat}:{m.key}' not in completed]
                # Rotate sequential order deterministically to reduce systematic order bias.
                offset = (i+repeat) % len(pending) if pending else 0
                pending = pending[offset:] + pending[:offset]
                if emit:
                    await emit('puzzle', {'puzzle_id': puzzle_id, 'seed': seed, 'scramble': scramble,
                        'start_state': state, 'exact_optimal': exact, 'repeat': repeat, 'condition': config.condition,
                        'completed_games': [g.model_dump() for g in store.games if g.puzzle_id == puzzle_id and g.repeat == repeat]})

                async def play(model):
                    adapter = adapter_for(model, client, config, solver, seed+repeat, permit)
                    return await run_game(model, adapter, state, config=config, run_id=run_id,
                        puzzle_id=puzzle_id, seed=seed, scramble=scramble, repeat=repeat,
                        exact_optimal=exact, reference_moves=reference, emit=emit, smoke=request.set == 'smoke')

                if request.mode == 'concurrent':
                    tasks = [asyncio.create_task(play(m)) for m in pending]
                    try:
                        for task in asyncio.as_completed(tasks):
                            game = await task
                            await asyncio.to_thread(persist, game)
                            completed.add(game.attempt_id)
                    finally:
                        for task in tasks:
                            if not task.done():
                                task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                else:
                    for model in pending:
                        game = await play(model)
                        await asyncio.to_thread(persist, game)
                        completed.add(game.attempt_id)
                if request.baselines and request.set != 'smoke':
                    from .baselines import BaselineAdapter
                    from .config import ModelConfig
                    from .schemas import GameResult
                    for policy in ('oracle', 'random', 'greedy'):
                        if f'{puzzle_id}:{repeat}:{policy}' in completed:
                            continue
                        model = ModelConfig(key=policy, name=policy.title() + ' (offline baseline)',
                            category='DECISION MODEL', id=f'offline/{policy}', endpoint='decisions')
                        if policy == 'oracle' and exact is None:
                            game = GameResult(attempt_id=f'{puzzle_id}:{repeat}:{policy}', run_id=run_id,
                                model=policy, model_id=model.id, model_name=model.name, category='BASELINE',
                                mock=True, puzzle_id=puzzle_id, repeat=repeat, seed=seed, scramble=scramble,
                                start_state=state, final_state=state, status='NOT_RUN',
                                condition=config.condition, benchmark_set=request.set,
                                error='Exact oracle outside proven search coverage')
                        else:
                            game = await run_game(model, BaselineAdapter(policy, seed+repeat, solver), state,
                                config=config.model_copy(update={'mock_models': True}), run_id=run_id,
                                puzzle_id=puzzle_id, seed=seed, scramble=scramble, repeat=repeat, exact_optimal=exact)
                        game.agent_kind, game.category = 'baseline', 'BASELINE'
                        await asyncio.to_thread(persist, game)
                        completed.add(game.attempt_id)
                if emit:
                    ranked = rank_games([g for g in store.games if g.puzzle_id == puzzle_id and g.repeat == repeat])
                    await emit('ranking', {'ranks': {g.model: n+1 for n, g in enumerate(ranked)}})
        if emit:
            await emit('benchmark_done', {'run_id': run_id, 'summary': store.snapshot()['summary']})
        return store
    finally:
        if own_client:
            await client.aclose()


async def debug_probe(config: Settings, approved: bool = False):
    request = BenchmarkRequest(set='smoke', puzzles=1, execution='live',
                               live_approved=approved, request_cap=4)
    solver = ExactSolver(config.bfs_depth, node_budget=config.exact_node_budget)
    store = await execute(request, config, new_run_id(), solver)
    for game in store.games:
        print(json.dumps({'model': game.model_id, 'status': game.status,
                          'responses': [r.response.model_dump() for r in game.records]}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--set', choices=['warmup', 'primary', 'extension', 'race', 'smoke'], default='primary')
    parser.add_argument('--puzzles', type=int)
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--mode', choices=['concurrent', 'sequential'], default='sequential')
    parser.add_argument('--seed', type=int, default=SEEDS[0])
    parser.add_argument('--length', type=int, default=4)
    parser.add_argument('--condition', choices=['pure', 'assisted', 'both'], default=settings.condition)
    parser.add_argument('--history-length', type=int, default=settings.history_length, help='-1 all, 0 none, otherwise last N')
    parser.add_argument('--max-moves', type=int, default=None)
    parser.add_argument('--baselines', action='store_true', help='Include offline oracle/random/greedy controls')
    parser.add_argument('--no-loop-avoidance', action='store_true', help='Assisted ablation without the visited-state filter')
    parser.add_argument('--resume', metavar='RUN_ID')
    parser.add_argument('--debug-probe', action='store_true')
    parser.add_argument('--approve-live', action='store_true', help='Explicitly approve inference charges for this run')
    parser.add_argument('--request-cap', type=int, help='Approved hard request cap; required for live execution')
    parser.add_argument('--build-bfs', type=int, choices=range(7), metavar='DEPTH')
    args = parser.parse_args()
    self_test()
    configure_logging(settings.results_dir)
    if args.build_bfs is not None:
        ExactSolver(args.build_bfs, settings.results_dir / 'cache' / f'bfs-{args.build_bfs}.pickle').build()
        return
    if args.debug_probe:
        if not args.approve_live:
            parser.error('--debug-probe requires --approve-live (four real model requests)')
        asyncio.run(debug_probe(settings, approved=True))
        return
    count = args.puzzles if args.puzzles is not None else {'warmup': 2, 'primary': 10, 'extension': 5, 'race': 1, 'smoke': 1}[args.set]
    if args.condition == 'both' and args.resume:
        parser.error('Resume one condition at a time')
    request = BenchmarkRequest(condition='pure' if args.condition == 'both' else args.condition,
        history_length=args.history_length, max_moves=args.max_moves, loop_avoidance=not args.no_loop_avoidance, baselines=args.baselines, set=args.set, puzzles=count, repeats=args.repeats, mode=args.mode, seed=args.seed,
        length=args.length, execution='live' if args.approve_live else 'simulated',
        live_approved=args.approve_live, request_cap=args.request_cap)
    run_settings(request, settings)  # validate before building cache or any network access
    solver = ExactSolver(settings.bfs_depth, settings.results_dir / 'cache' / f'bfs-{settings.bfs_depth}.pickle', settings.exact_node_budget)
    run_id = args.resume or new_run_id()
    paths = []
    for condition in (('pure', 'assisted') if args.condition == 'both' else (args.condition,)):
        current = request.model_copy(update={'condition': condition})
        store = asyncio.run(execute(current, settings, run_id if args.condition != 'both' else new_run_id(), solver))
        paths.append(store.path)
        print(f'Results ({condition}): {store.path}')
    if len(paths) == 2:
        from .diagnostics import comparison_report
        print(comparison_report([g for path in paths for g in Store(settings.results_dir, path.stem).games]))


if __name__ == '__main__':
    main()
