"""Loopback-only local experiment server; secrets never enter frontend configuration."""
import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .benchmark import BenchmarkRequest, execute, new_run_id, run_settings
from .budget import Ledger
from .config import MODELS, ROOT, settings
from .cube_engine import self_test
from .logging_config import configure_logging
from .optimal import ExactSolver
from .scramble import puzzle
from .stats import analysis_answers
from .storage import Store
from .transport import create_client


class LiveRun:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []
        self.condition = asyncio.Condition()
        self.done = False
        self.task: asyncio.Task | None = None

    async def emit(self, kind: str, payload: dict):
        async with self.condition:
            self.events.append((kind, payload))
            self.condition.notify_all()


@asynccontextmanager
async def lifespan(app: FastAPI):
    self_test()  # fail startup rather than emit invalid benchmark data
    configure_logging(settings.results_dir)
    app.state.runs = {}
    app.state.active = None
    app.state.solver = ExactSolver(settings.bfs_depth,
        settings.results_dir / 'cache' / f'bfs-{settings.bfs_depth}.pickle', settings.exact_node_budget)
    await asyncio.to_thread(app.state.solver.build)
    app.state.client = create_client(settings)
    yield
    tasks = [run.task for run in app.state.runs.values() if run.task and not run.task.done()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await app.state.client.aclose()


app = FastAPI(title='Rubiks Cube Race', lifespan=lifespan)


@app.middleware('http')
async def local_only_mutations(request: Request, call_next):
    # Avoid cross-origin websites spending a local user's key. No permissive CORS.
    if request.method == 'POST':
        origin = request.headers.get('origin')
        expected = str(request.base_url).rstrip('/')
        if origin and origin != expected:
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail': 'Cross-origin mutation rejected'}, status_code=403)
    return await call_next(request)


@app.get('/api/config')
async def configuration():
    return {'models': [m.model_dump() for m in MODELS], 'mock': settings.mock_models,
            'student_name': settings.student_name, 'roll_number': settings.roll_number,
            'condition': settings.condition, 'history_length': settings.history_length,
            'max_moves': settings.max_moves, 'game_timeout_s': settings.game_timeout_s,
            'max_retries': settings.max_retries, 'claude_reasoning_effort': settings.claude_reasoning_effort,
            'claude_max_tokens': settings.claude_max_tokens,
            'api_key_configured': bool(settings.openrouter_api_key.get_secret_value())}


@app.get('/api/health')
async def health():
    return {'status': 'ok'}


@app.get('/api/puzzle')
async def get_puzzle(seed: int = 104729, length: int = 4):
    if not 1 <= length <= 20 or not 0 <= seed <= 2**32-1:
        raise HTTPException(422, 'Invalid seed or scramble length')
    scramble, state = puzzle(length, seed)
    return {'seed': seed, 'scramble': scramble, 'start_state': state}


@app.post('/api/runs')
async def start_run(body: BenchmarkRequest):
    try:
        run_settings(body, settings)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    if app.state.active is not None:
        raise HTTPException(409, 'An experiment is already running')
    run_id, live = new_run_id(), LiveRun()
    app.state.runs[run_id] = live
    app.state.active = run_id

    async def work():
        try:
            await execute(body, settings, run_id, app.state.solver, live.emit, app.state.client)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logging.getLogger(__name__).exception('Benchmark failed')
            await live.emit('run_error', {'message': f'{type(exc).__name__}: {exc}'})
        finally:
            app.state.active = None
            async with live.condition:
                live.done = True
                live.condition.notify_all()
            # Bound retained event streams. Persisted runs remain replayable.
            for old_id in list(app.state.runs)[:-10]:
                if app.state.runs[old_id].done:
                    del app.state.runs[old_id]

    live.task = asyncio.create_task(work())
    return {'run_id': run_id}


@app.get('/api/billing')
async def billing():
    ledger = await asyncio.to_thread(Ledger, settings.results_dir, settings.live_request_limit)
    return await asyncio.to_thread(ledger.summary)


@app.get('/api/runs/{run_id}/events')
async def stream(run_id: str, request: Request):
    live = app.state.runs.get(run_id)
    if live is None:
        raise HTTPException(404, 'Live stream expired; use saved replay')
    try:
        cursor = max(0, int(request.headers.get('last-event-id', '-1'))+1)
    except ValueError:
        cursor = 0

    async def events():
        nonlocal cursor
        while True:
            if await request.is_disconnected():
                return
            batch = []
            async with live.condition:
                if cursor >= len(live.events) and not live.done:
                    try:
                        await asyncio.wait_for(live.condition.wait(), 15)
                    except asyncio.TimeoutError:
                        pass
                batch = live.events[cursor:]
                done = live.done
            for kind, data in batch:
                yield f'id: {cursor}\nevent: {kind}\ndata: {json.dumps(data)}\n\n'
                cursor += 1
            if done:
                return
            if not batch:
                yield ': heartbeat\n\n'
    return StreamingResponse(events(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.get('/api/runs')
async def saved_runs():
    def read():
        out = []
        for path in sorted(settings.results_dir.glob('*.json'), reverse=True):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                out.append({'run_id': path.stem, **data['metadata'], 'games': len(data['games'])})
            except (ValueError, KeyError):
                continue
        return out
    return await asyncio.to_thread(read)


@app.get('/api/runs/{run_id}')
async def saved_run(run_id: str):
    try:
        store = await asyncio.to_thread(Store, settings.results_dir, run_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not store.path.exists():
        raise HTTPException(404, 'Run not found')
    data = await asyncio.to_thread(store.snapshot)
    data['answers'] = analysis_answers(data['summary'])
    return data


app.mount('/assets', StaticFiles(directory=ROOT / 'frontend'), name='assets')


@app.get('/')
async def index():
    return FileResponse(ROOT / 'frontend' / 'index.html')
