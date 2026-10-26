import json
import httpx
import pytest
from backend.action_policy import offered_moves
from backend.adapters.base import ModelAdapter
from backend.adapters.chat_completions import ChatAdapter
from backend.adapters.decisions_api import DecisionsAdapter
from backend.config import MODELS, Settings
from backend.cube_engine import MOVES, apply_move, apply_moves, solved_state
from backend.presentation import shared_context
from backend.runner import run_game
from backend.schemas import AdapterResult
from backend.stats import aggregate


def test_filter_blocks_inverse_half_turn_and_four_quarter_turn_cycles():
    start = apply_move(solved_state(), 'F')
    for moves, blocked in [(['R'], "R'"), (['R2'], 'R2'), (['R','R','R'], 'R')]:
        state, visited = start, {start}
        for move in moves:
            state = apply_move(state, move)
            visited.add(state)
        allowed, fallback = offered_moves(state, visited, True)
        assert not fallback and blocked not in allowed
        assert all(apply_move(state, move) not in visited for move in allowed)
        assert offered_moves(state, visited, False) == (MOVES, False)


def test_full_neighbourhood_is_explicit_fallback_not_early_stop():
    state = apply_move(solved_state(), 'R')
    visited = {state} | {apply_move(state, move) for move in MOVES}
    assert offered_moves(state, visited, True) == (MOVES, True)


@pytest.mark.asyncio
@pytest.mark.parametrize('model', MODELS)
async def test_same_guard_for_every_model_no_automatic_replacement(model):
    class Repeat(ModelAdapter):
        def __init__(self): self.seen = []
        async def get_move(self, state, history, allowed):
            self.seen.append(allowed)
            return AdapterResult(move='R2', valid=True)
    adapter = Repeat()
    result = await run_game(model, adapter, apply_move(solved_state(), 'F'),
        config=Settings(_env_file=None, condition='assisted', max_moves=2),
        run_id='test', puzzle_id='race-test', seed=1, scramble=['F'])
    assert 'R2' in adapter.seen[0] and 'R2' not in adapter.seen[1]
    assert result.moves_used == 1 and result.attempts_used == 2
    assert result.invalid_count == 1 and result.action_policy == 'avoid_visited'
    assert not result.records[1].valid
    assert result.records[1].state_after == result.records[0].state_after
    assert result.diagnostics['state_revisits'] == 0


@pytest.mark.asyncio
async def test_pure_does_not_filter_or_rewrite_model_moves():
    class Repeat(ModelAdapter):
        async def get_move(self, state, history, allowed):
            assert allowed == MOVES
            return AdapterResult(move='R2', valid=True)
    result = await run_game(MODELS[0], Repeat(), apply_move(solved_state(), 'F'),
        config=Settings(_env_file=None, condition='pure', max_moves=2),
        run_id='test', puzzle_id='race-test', seed=1, scramble=['F'])
    assert result.moves_used == 2 and result.invalid_count == 0
    assert result.diagnostics['state_revisits'] == 1
    assert result.action_policy == 'unrestricted'


@pytest.mark.asyncio
async def test_invalid_output_reduces_prompt_budget_identically(tmp_path):
    from backend.budget import Ledger
    captured = []
    def handler(request):
        body = json.loads(request.content)
        context = body.get('state') or json.loads(body['messages'][1]['content'])
        captured.append(context)
        if context['attempts_used'] == 0:
            return httpx.Response(200, json={'choices': [{'message': {'content': 'bad'}}]} if 'messages' in body else {'answers': {'next_move': {'choice': 'bad'}}})
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"move":"R"}'}}]} if 'messages' in body else {'answers': {'next_move': {'choice': 'R'}}})
    config = Settings(_env_file=None, results_dir=tmp_path, max_moves=2)
    ledger = Ledger(tmp_path, 20)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        for model in MODELS:
            permit = ledger.approve(model.key, 2)
            cls = ChatAdapter if model.endpoint == 'chat' else DecisionsAdapter
            result = await run_game(model, cls(model, client, config, permit), apply_move(solved_state(), 'F'),
                config=config, run_id=model.key, puzzle_id='race-test', seed=1, scramble=['F'])
            assert result.attempts_used == 2 and result.moves_used == 1
    assert len(captured) == 8
    for first, second in zip(captured[::2], captured[1::2]):
        assert first['moves_remaining'] == 2 and second['moves_remaining'] == 1
        assert second['recent_moves'] == [] and second['moves_applied'] == 0
        assert second['attempts_used'] == 1


def test_assisted_payloads_share_same_offered_moves_and_no_solution():
    state = apply_moves(solved_state(), ['F', 'R'])
    allowed, _ = offered_moves(state, {apply_move(solved_state(), 'F'), state}, True)
    context = shared_context(state, ['R'], allowed, condition='assisted')
    assert "R'" not in context['criteria']
    assert set(context['one_step_correct_facelets']) == set(MOVES)
    assert context['offered_moves'] == list(allowed)
    assert not {'scramble', 'solution', 'exact_optimal', 'bfs'} & set(context)


@pytest.mark.asyncio
@pytest.mark.parametrize('model', MODELS)
async def test_explicit_truncation_is_a_technical_stop_for_every_model(model):
    class Truncated(ModelAdapter):
        def __init__(self): self.calls = 0
        async def get_move(self, state, history, allowed):
            self.calls += 1
            return AdapterResult(output_truncated=True, invalid_outputs=1,
                                 error='Completion token ceiling reached', valid=False)
    adapter = Truncated()
    result = await run_game(model, adapter, apply_move(solved_state(), 'F'),
        config=Settings(_env_file=None), run_id='test', puzzle_id='race-test', seed=1, scramble=['F'])
    assert adapter.calls == 1 and result.status == 'ERROR'
    assert result.attempts_used == 1 and result.moves_used == 0 and result.invalid_count == 1
    assert result.config['truncation_policy'] == 'stop_game_error'


@pytest.mark.asyncio
async def test_claude_truncation_does_not_use_configured_retry_budget(tmp_path):
    from backend.budget import Ledger
    config = Settings(_env_file=None, max_retries=2, retry_backoff_s=0)
    permit = Ledger(tmp_path, 3).approve('test', 3)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'length', 'message': {'content': None}}],
                                       'usage': {'total_tokens': 512, 'cost': .01}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ChatAdapter(MODELS[-1], client, config, permit).get_move(solved_state(), [], MOVES)
    assert len(calls) == 1 and result.output_truncated and result.retries_used == 0
    assert result.cost == .01 and result.invalid_outputs == 1


@pytest.mark.asyncio
async def test_provider_key_limit_has_clear_safe_error(tmp_path):
    from backend.budget import Ledger
    permit = Ledger(tmp_path, 4).approve('test', 4)
    payload = {'error': {'code': 403, 'message': 'Key limit exceeded with private management path',
                         'metadata': {'scope': 'key_limit', 'limit_usd': 2}}}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(403, json=payload))) as client:
        response = await ChatAdapter(MODELS[-1], client, Settings(_env_file=None), permit).get_move(solved_state(), [], MOVES)
    assert response.unavailable and response.permanent
    assert 'spending limit reached' in response.error
    assert 'private management path' not in response.error


@pytest.mark.asyncio
async def test_guard_protocols_do_not_merge_with_old_assisted_results():
    class One(ModelAdapter):
        async def get_move(self, state, history, allowed):
            return AdapterResult(move="R'", valid=True)
    original = await run_game(MODELS[0], One(), apply_move(solved_state(), 'R'),
        config=Settings(_env_file=None, condition='assisted'), run_id='test',
        puzzle_id='race-test', seed=1, scramble=['R'], exact_optimal=1)
    old = original.model_copy(deep=True)
    old.config['presentation_version'] = 'oriented-color-net-v3'
    old.action_policy = 'unrestricted'
    rows = aggregate([old, original])
    assert len(rows) == 2 and {r['action_policy'] for r in rows} == {'unrestricted','avoid_visited'}
