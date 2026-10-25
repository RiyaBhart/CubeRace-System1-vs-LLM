import json
from pathlib import Path
import httpx
import pytest
from backend.adapters.base import shared_context
from backend.adapters.chat_completions import ChatAdapter, parse_response as parse_chat
from backend.adapters.decisions_api import DecisionsAdapter, build_request, parse_response
from backend.config import MODELS, Settings
from backend.cube_engine import MOVES, solved_state
from backend.budget import Ledger

FIXTURES = json.loads((Path(__file__).parent/'fixtures'/'decisions.json').read_text())


@pytest.fixture
def approved(tmp_path):
    permit = Ledger(tmp_path, 200).approve('test', 200)
    def factory(cls, model, client, config):
        return cls(model, client, config, permit=permit)
    return factory


@pytest.mark.parametrize('raw', FIXTURES['valid'])
def test_choice_shapes(raw):
    move, confidence = parse_response(raw, MOVES)
    assert move in MOVES


@pytest.mark.parametrize('raw', FIXTURES['invalid'])
def test_invalid_choices_not_repaired(raw):
    with pytest.raises((ValueError,TypeError)):
        parse_response(raw,MOVES)


@pytest.mark.parametrize('content', ['R', '```json\n{"move":"R"}\n```','{"move":" R "}','{"move":"R U"}','{"move":"R","why":"yes"}','null','{"move":["R"]}'])
def test_chat_strict_json(content):
    with pytest.raises((ValueError,TypeError)):
        parse_chat({'choices':[{'message':{'content':content}}]},MOVES)


def test_same_information():
    request = build_request(MODELS[0].id,solved_state(),['R'],MOVES)
    chat_context = shared_context(solved_state(),['R'],MOVES)
    definitions = chat_context.pop('criteria')
    assert request['state'] == chat_context
    assert request['questions']['next_move']['criteria'] == definitions


@pytest.mark.asyncio
async def test_retry_invalid_and_capture_usage(approved):
    payloads = [{'answers':{'next_move':{'choice':'bad'}},'usage':{'total_tokens':2,'cost':0.1}},
                {'answers':{'next_move':{'choice':'R'}},'usage':{'total_tokens':3,'cost':0.2}}]
    def handler(request):
        return httpx.Response(200,json=payloads.pop(0))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await approved(DecisionsAdapter,MODELS[0],client,Settings(_env_file=None,retry_backoff_s=0,max_retries=2)).get_move(solved_state(),[],MOVES)
    assert result.valid and result.move == 'R'
    assert result.invalid_outputs == 1 and result.retries_used == 1
    assert result.tokens == 5 and result.cost == pytest.approx(0.3)
    assert len(result.calls) == 2
    assert result.latency_incl_retries_ms >= result.latency_ms


@pytest.mark.asyncio
@pytest.mark.parametrize('code', [401,403,404])
async def test_unavailable_no_retry(code,approved):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(code,json={'error':'missing'}))) as client:
        result=await approved(DecisionsAdapter,MODELS[0],client,Settings(_env_file=None)).get_move(solved_state(),[],MOVES)
    assert result.unavailable and result.fatal and result.retries_used == 0


@pytest.mark.asyncio
async def test_transient_retry_and_strict_schema_failure(approved):
    statuses=[429,503,200]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(statuses.pop(0),json={'answers':{'next_move':{'choice':'U'}}}))) as client:
        result=await approved(DecisionsAdapter,MODELS[0],client,Settings(_env_file=None,retry_backoff_s=0,max_retries=2)).get_move(solved_state(),[],MOVES)
    assert result.valid and result.retries_used == 2 and not statuses
    seen=[]
    def handler(request):
        data=json.loads(request.content);seen.append(data.get('response_format',{}).get('type','plain'))
        if len(seen)<3:
            return httpx.Response(400,json={'error':'response_format not supported'})
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"move":"U"}'}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result=await approved(ChatAdapter,MODELS[-1],client,Settings(_env_file=None)).get_move(solved_state(),[],MOVES)
    assert not result.valid and result.permanent and result.retries_used == 0
    assert seen == ['json_schema']
    assert result.invalid_outputs == 0


@pytest.mark.asyncio
async def test_network_retry_exhaustion(approved):
    def handler(request):
        raise httpx.ConnectError('test',request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result=await approved(DecisionsAdapter,MODELS[0],client,Settings(_env_file=None,retry_backoff_s=0,max_retries=2)).get_move(solved_state(),[],MOVES)
    assert not result.valid and result.retries_used == 2 and len(result.calls)==3


@pytest.mark.asyncio
async def test_recorded_authentication_failure(approved):
    fixture=json.loads((Path(__file__).parent/'fixtures'/'openrouter-auth-recorded.json').read_text())
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(fixture['http_status'],json=fixture['raw']))) as client:
        result=await approved(DecisionsAdapter,MODELS[0],client,Settings(_env_file=None)).get_move(solved_state(),[],MOVES)
    assert result.unavailable and result.retries_used==0 and result.invalid_outputs==0
