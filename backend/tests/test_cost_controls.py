"""All inference here is httpx.MockTransport; these tests cannot spend credits."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.accounting import normalize_usage, summarize_usage
from backend.adapters.base import INSTRUCTIONS, shared_context
from backend.adapters.chat_completions import ChatAdapter
from backend.adapters.decisions_api import DecisionsAdapter
from backend.benchmark import BenchmarkRequest, execute, recommended_cap
from backend.budget import BudgetExhausted, Ledger
from backend.config import MODELS, Settings
from backend.cube_engine import MOVES, apply_move, solved_state
from backend.optimal import ExactSolver
from backend.stats import aggregate
from backend.storage import Store


def settings(tmp_path, **kwargs):
    return Settings(_env_file=None, openrouter_api_key='test-not-a-real-key',
                    results_dir=tmp_path, bfs_depth=2, **kwargs)


def live(set='race', **kwargs):
    return BenchmarkRequest(set=set, puzzles=5 if set == 'primary' else 1,
                            execution='live', live_approved=True, request_cap=600, **kwargs)


def response_for(body, move='R', usage=None):
    if body['model'] == MODELS[-1].id:
        return {'choices': [{'message': {'content': json.dumps({'move': move})}}], 'usage': usage}
    return {'answers': {'next_move': {'type': 'choice', 'choice': move}}, 'usage': usage}


def test_fixed_claude_contract_and_identical_information(tmp_path):
    config = settings(tmp_path)
    history = ['U', 'R', "F'", 'L', 'B2', 'D', 'U2']
    client = httpx.AsyncClient()
    chat = ChatAdapter(MODELS[-1], client, config).request(solved_state(), history, MOVES)[1]
    user = json.loads(chat['messages'][1]['content'])
    assert chat['reasoning'] == {'effort': 'low'}
    assert not {'temperature','top_p','top_k'} & set(chat)
    assert chat['max_tokens'] == 512 and chat['usage'] == {'include': True}
    assert chat['response_format']['json_schema']['strict'] is True
    assert chat['provider']['require_parameters'] is True
    assert chat['messages'][0]['content'] == 'Return one legal move as schema JSON.'
    assert user.pop('instructions') == INSTRUCTIONS
    for model in MODELS[:3]:
        body = DecisionsAdapter(model, client, config).request(solved_state(), history, MOVES)[1]
        reconstructed = dict(body['state'], criteria=body['questions']['next_move']['criteria'])
        assert reconstructed == user
        assert body['questions']['next_move']['instructions'] == INSTRUCTIONS
    assert user['recent_moves'] == history and user['moves_remaining'] == 23
    assert {'cube_facelets', 'recent_moves', 'goal_facelets', 'moves_remaining', 'metric', 'criteria', 'faces', 'net', 'correct_facelets'} <= set(user)
    assert len(user['criteria']) == 18 and user['goal_facelets'] == solved_state()
    assert 'scramble' not in json.dumps(user) and 'solution' not in json.dumps(user)
    for bad in ('none', 'disabled'):
        with pytest.raises(ValueError):
            settings(tmp_path, claude_reasoning_effort=bad)
    asyncio.run(client.aclose())


def test_recommended_caps_include_puzzles_models_actions_repeats_and_retries(tmp_path):
    assert recommended_cap(live('primary'), settings(tmp_path)) == 600
    assert recommended_cap(live('primary', repeats=3), settings(tmp_path,max_retries=2)) == 5400
    assert recommended_cap(live('smoke'), settings(tmp_path,max_retries=2)) == 4


def test_durable_atomic_budget_never_resets_or_increases(tmp_path):
    ledger = Ledger(tmp_path, 3)
    ledger.approve('r', 3)
    def reserve(_):
        try:
            return ledger.reserve('r', 'jev')
        except BudgetExhausted:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(n is not None for n in pool.map(reserve, range(20))) == 3
    restored = Ledger(tmp_path, 9999)
    assert restored.summary()['requests_used'] == 3
    assert restored.summary()['request_limit'] == 3
    assert restored.summary()['unknown_cost_requests'] == 3
    assert restored.summary()['cost'] is None
    with pytest.raises(ValueError):
        restored.approve('r', 4)
    restored.approve('new', 10)
    with pytest.raises(BudgetExhausted):
        restored.reserve('new', 'opus')
    with pytest.raises(PermissionError):
        restored.set_suite_cap(100)
    restored.set_suite_cap(4, confirmed=True)
    assert restored.summary()['requests_used']==3
    assert restored.summary()['request_limit']==4


def test_existing_recorded_requests_import_once_without_reset(tmp_path):
    record={'metadata':{'mock':False},'games':[{'model':'jev','records':[{'timestamp':'legacy',
        'response':{'calls':[{'raw_response':{'usage':{'cost':0.1,'input_tokens':2,'output_tokens':1}}}]}}]}]}
    (tmp_path/'old.json').write_text(json.dumps(record))
    first=Ledger(tmp_path,604)
    assert first.summary()['requests_used']==1 and first.summary()['cost']==0.1
    assert Ledger(tmp_path,999).summary()['requests_used']==1
    assert Ledger(tmp_path,999).summary()['request_limit']==604


def test_usage_reasoning_not_double_counted_and_unknown_cost_not_zero():
    usage = {'prompt_tokens':10,'completion_tokens':20,'completion_tokens_details':{'reasoning_tokens':15},'cost':0.05}
    assert normalize_usage(usage)['total_tokens'] == 30
    summary = summarize_usage([{'usage':usage},{'usage':{'total_tokens':2}}])
    assert summary['tokens'] == 32 and summary['cost'] is None
    assert summary['known_cost'] == 0.05 and summary['unknown_cost_requests'] == 1
    assert summary['reasoning_tokens'] is None
    assert summarize_usage([{'usage':{'cost':0}}])['cost'] == 0
    assert normalize_usage({'cost':float('nan')})['cost'] is None


@pytest.mark.asyncio
async def test_no_permit_no_request_and_simulation_cannot_call_real_adapter(tmp_path):
    seen=[]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:seen.append(r))) as client:
        config=settings(tmp_path)
        result=await DecisionsAdapter(MODELS[0],client,config).get_move(solved_state(),[],MOVES)
        assert result.not_run and not seen
        permit=Ledger(tmp_path,4).approve('r',4)
        result=await ChatAdapter(MODELS[-1],client,config.model_copy(update={'mock_models':True}),permit).get_move(solved_state(),[],MOVES)
        assert result.not_run and not seen


@pytest.mark.asyncio
@pytest.mark.parametrize('code',[429,503,200])
async def test_zero_retry_defaults_one_request_for_invalid_or_transient_output(tmp_path,code):
    seen=[]
    def handler(request):
        seen.append(request)
        return httpx.Response(code,json={'invalid':'not a choice'})
    config=settings(tmp_path)
    permit=Ledger(tmp_path,4).approve('r',4)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result=await DecisionsAdapter(MODELS[0],client,config,permit).get_move(apply_move(solved_state(),'R'),[],MOVES)
    assert len(seen)==1 and result.retries_used==0


@pytest.mark.asyncio
async def test_smoke_then_five_puzzles_with_complete_durable_billing(tmp_path):
    seen=[]
    solver=ExactSolver(2)
    usage={'input_tokens':12,'output_tokens':3,'completion_tokens_details':{'reasoning_tokens':1},'cost':0.001}
    def handler(request):
        if request.method=='GET':
            return httpx.Response(200,json={})
        body=json.loads(request.content)
        seen.append(body)
        context=body.get('state') or json.loads(body['messages'][1]['content'])
        # Test-only fake service; no solver is ever passed to real live adapters.
        move=solver.solution(context['cube_facelets'],8)[0]
        return httpx.Response(200,json=response_for(body,move,usage))
    config=settings(tmp_path)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        smoke=await execute(live('smoke',length=1),config,'smoke',solver,client=client)
        assert len(seen)==4 and len(smoke.games)==4
        assert all(len(g.records)==1 for g in smoke.games)
        assert all(g.diagnostic and g.status=='SOLVED' for g in smoke.games)
        assert all(row['attempts']==0 and row['smoke_tests']==1 for row in aggregate(smoke.games))
        count=len(seen)
        full=await execute(live('primary'),config,'primary',solver,client=client)
        assert len(full.games)==20 and all(g.status=='SOLVED' for g in full.games)
        expected=sum(g.moves_used for g in full.games)
        assert len(seen)==count+expected
        assert full.metadata['billing']['requests_used']==expected
        assert full.metadata['billing']['cost']==pytest.approx(expected*0.001)
        assert full.metadata['suite_billing']['requests_used']==len(seen)
        assert full.metadata['suite_billing']['reasoning_tokens']==len(seen)
        # Viewing, exporting and explicit resume of completed attempts never infer.
        Store(tmp_path,'primary').snapshot()
        await execute(live('primary'),config,'primary',solver,client=client)
        assert len(seen)==count+expected
    assert {b['model'] for b in seen}=={m.id for m in MODELS}


@pytest.mark.asyncio
@pytest.mark.parametrize('code',[400,401,404,422])
async def test_permanent_incompatibility_is_not_retried_across_puzzles_or_resume(tmp_path,code):
    seen=[]
    def handler(request):
        if request.method=='GET': return httpx.Response(200,json={})
        seen.append(request)
        return httpx.Response(code,json={'error':{'message':'unsupported schema or model','code':code}})
    config=settings(tmp_path,max_retries=2)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store=await execute(live('primary'),config,'r',ExactSolver(2),client=client)
        assert len(seen)==4
        assert sum(g.status=='NOT_RUN' for g in store.games)==16
        for row in aggregate(store.games):
            assert row['scheduled']==5 and row['attempts']==1 and row['not_run']==4
        await execute(live('primary'),config,'r',ExactSolver(2),client=client)
        assert len(seen)==4


@pytest.mark.asyncio
async def test_budget_exhaustion_never_dispatches_extra_call(tmp_path):
    seen=[]
    def handler(request):
        if request.method=='GET': return httpx.Response(200,json={})
        body=json.loads(request.content);seen.append(body)
        return httpx.Response(200,json=response_for(body))
    request=live().model_copy(update={'request_cap':3})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store=await execute(request,settings(tmp_path),'limited',ExactSolver(2),client=client)
    assert len(seen)==3 and sum(g.requests_used for g in store.games)==3
    assert store.metadata['billing']['requests_used']==3
    assert all(g.status in ('BUDGET_EXHAUSTED','NOT_RUN') for g in store.games)


@pytest.mark.asyncio
async def test_simulated_execution_never_uses_transport_or_live_counter(tmp_path):
    seen=[]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:seen.append(r))) as client:
        request=BenchmarkRequest(set='smoke',puzzles=1)
        store=await execute(request,settings(tmp_path),'simulated',ExactSolver(2),client=client)
    assert not seen and all(g.mock for g in store.games)
    assert Ledger(tmp_path,604).summary()['requests_used']==0


def test_page_refresh_health_stats_replay_export_and_missing_consent_never_infer(tmp_path,monkeypatch):
    seen=[]
    config=settings(tmp_path)
    monkeypatch.setattr(main,'settings',config)
    monkeypatch.setattr(main,'create_client',lambda _:httpx.AsyncClient(transport=httpx.MockTransport(lambda r:seen.append(r))))
    with TestClient(main.app) as client:
        for path in ['/', '/api/health', '/api/config', '/api/puzzle', '/api/runs', '/api/billing', '/assets/app.js']:
            assert client.get(path).status_code==200
        body=live().model_dump();body['live_approved']=False
        assert client.post('/api/runs',json=body).status_code==403
        body['live_approved']=True;body['request_cap']=None
        assert client.post('/api/runs',json=body).status_code==403
        assert client.get('/api/billing').json()['requests_used']==0
    assert not seen


@pytest.mark.asyncio
async def test_deadline_retains_reserved_request_and_unknown_billing(tmp_path):
    started=asyncio.Event()
    async def handler(request):
        started.set()
        await asyncio.sleep(1)
        return httpx.Response(200,json={})
    ledger=Ledger(tmp_path,4)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter=DecisionsAdapter(MODELS[0],client,settings(tmp_path),ledger.approve('r',4))
        task=asyncio.create_task(adapter.get_move(solved_state(),[],MOVES))
        await started.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
    assert ledger.summary()['requests_used']==1
    assert ledger.summary()['unknown_cost_requests']==1
    assert len(adapter.partial_result.calls)==1
