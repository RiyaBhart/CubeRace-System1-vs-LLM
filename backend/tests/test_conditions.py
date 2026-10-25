import json
from pathlib import Path
import httpx
import pytest
from backend.adapters.chat_completions import ChatAdapter
from backend.adapters.decisions_api import DecisionsAdapter, parse_response
from backend.benchmark import BenchmarkRequest, execute, run_settings
from backend.config import MODELS, Settings
from backend.cube_engine import FACES, MOVES, apply_move, apply_moves, solved_state
from backend.diagnostics import game_diagnostics, comparison_report
from backend.optimal import ExactSolver
from backend.presentation import COLORS, ORIENTATION, shared_context
from backend.runner import run_game
from backend.schemas import AdapterResult
from backend.stats import aggregate

@pytest.mark.parametrize('condition', ['pure', 'assisted'])
def test_information_is_identical_for_four_models(condition):
    state = apply_moves(solved_state(), ['R', 'U', 'F'])
    history = ['U', 'R', 'D', 'F']
    config = Settings(_env_file=None, condition=condition, history_length=2, max_moves=20)
    client = httpx.AsyncClient()
    body = ChatAdapter(MODELS[-1], client, config).request(state, history, MOVES)[1]
    context = json.loads(body['messages'][1]['content'])
    instruction = context.pop('instructions')
    for model in MODELS[:3]:
        request = DecisionsAdapter(model, client, config).request(state, history, MOVES)[1]
        question = request['questions']['next_move']
        assert question['instructions'] == instruction
        assert dict(request['state'], criteria=question['criteria']) == context
    assert context['recent_moves'] == history[-2:]
    assert context['moves_remaining'] == 16
    assert 'Limit: 20 moves.' in instruction
    for forbidden in ('scramble', 'exact_optimal', 'bfs', 'solution'):
        assert forbidden not in context
    assert ('one_step_correct_facelets' in context) == (condition == 'assisted')
    if condition == 'assisted':
        for move, count in context['one_step_correct_facelets'].items():
            assert count == sum(a == b for a,b in zip(apply_move(state, move), solved_state()))
    # No requests are made by request builders; close the unused client.
    import asyncio
    asyncio.run(client.aclose())


def test_orientation_and_color_grids():
    # Independent physical-neighbour expectations, including easily mirrored B/U/D.
    assert ORIENTATION == {'U': ('B','R'), 'R': ('U','B'), 'F': ('U','R'),
                           'D': ('F','R'), 'L': ('U','F'), 'B': ('U','L')}
    state = apply_move(solved_state(), 'R')
    context = shared_context(state, [], MOVES)
    for i, face in enumerate(FACES):
        assert [c for row in context['faces'][face]['rows'] for c in row] == [COLORS[c] for c in state[i*9:i*9+9]]
        assert context['correct_facelets']['per_face'][face] == state[i*9:i*9+9].count(face)
    assert shared_context(solved_state(), [], MOVES)['correct_facelets']['total'] == 54
    assert len(context['net'].splitlines()) == 9
    assert shared_context(state, ['R'], MOVES, history_length=0)['recent_moves'] == []

@pytest.mark.asyncio
async def test_runner_sends_updated_state_and_full_own_history():
    seen = []
    class Spy:
        async def get_move(self, state, history, allowed):
            seen.append((state, list(history)))
            return AdapterResult(move=['U', "U'", "R'"][len(seen)-1], valid=True)
    start = apply_move(solved_state(), 'R')
    game = await run_game(MODELS[0], Spy(), start, config=Settings(_env_file=None, mock_models=True),
        run_id='test', puzzle_id='race-test', seed=1, scramble=['R'])
    assert seen == [(start, []), (apply_move(start,'U'), ['U']), (start, ['U', "U'"])]
    assert game.status == 'SOLVED'
    assert game.diagnostics['immediate_undo_loops'] == 1


def test_parser_uses_selected_option_not_first_or_max_probability():
    assert parse_response({'answers': {'next_move': {'choice': 'B2',
        'probabilities': {'U': .99, 'B2': .01}}}}, MOVES) == ('B2', .01)
    for path in Path(__file__).with_name('fixtures').glob('*-choice-recorded.json'):
        raw = json.loads(path.read_text(encoding='utf-8'))
        assert parse_response(raw, MOVES)[0] == raw['answers']['next_move']['choice']

@pytest.mark.asyncio
async def test_paired_conditions_baselines_no_network_and_no_merged_statistics(tmp_path):
    async def forbidden(request):
        raise AssertionError('Offline verification must never use network')
    config = Settings(_env_file=None, results_dir=tmp_path, bfs_depth=2, max_moves=3)
    solver = ExactSolver(2)
    games = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as client:
        for condition in ('pure', 'assisted'):
            request = BenchmarkRequest(set='race', puzzles=1, length=2, baselines=True, condition=condition)
            store = await execute(request, config, condition, solver, client=client)
            assert len(store.games) == 7
            assert len({g.start_state for g in store.games}) == 1
            oracle = next(g for g in store.games if g.model == 'oracle')
            assert oracle.status == 'SOLVED' and oracle.optimality_gap == 0 and oracle.requests_used == 0
            games.extend(store.games)
    assert len({g.start_state for g in games}) == 1
    rows = aggregate(games)
    assert len(rows) == 14 and {r['condition'] for r in rows} == {'pure','assisted'}
    assert 'OFFLINE BASELINE' in comparison_report(games)
    assert 'SIMULATED' in comparison_report(games)
    request = BenchmarkRequest(set='race', puzzles=1, condition='assisted', max_moves=12)
    assert run_settings(request, config).max_moves == 12
