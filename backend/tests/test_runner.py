import asyncio
import pytest
from backend.adapters.base import ModelAdapter
from backend.config import MODELS,Settings
from backend.cube_engine import apply_move,solved_state
from backend.runner import rank_games,run_game
from backend.schemas import AdapterResult


class Scripted(ModelAdapter):
    def __init__(self,moves,delay=0):
        self.moves=iter(moves);self.calls=0;self.delay=delay;self.histories=[]
    async def get_move(self,state,recent_moves,allowed_moves):
        self.calls+=1;self.histories.append(recent_moves)
        await asyncio.sleep(self.delay)
        move=next(self.moves)
        if isinstance(move,AdapterResult):
            return move
        return AdapterResult(move=move,valid=True,latency_ms=1,latency_incl_retries_ms=1)


async def play(adapter,state=None,**overrides):
    return await run_game(MODELS[0],adapter,state or apply_move(solved_state(),'R'),
        config=Settings(_env_file=None,mock_models=True,**overrides),run_id='test',
        puzzle_id='p',seed=1,scramble=['R'],exact_optimal=1)


@pytest.mark.asyncio
async def test_stop_immediately_after_solve():
    adapter=Scripted(["R'",'U'])
    result=await play(adapter)
    assert result.status=='SOLVED' and result.moves_used==1 and adapter.calls==1
    assert result.optimality_gap==0


@pytest.mark.asyncio
async def test_already_solved():
    adapter=Scripted([])
    result=await run_game(MODELS[0],adapter,solved_state(),config=Settings(_env_file=None),run_id='test',puzzle_id='p',seed=1,scramble=[],exact_optimal=0)
    assert result.status=='SOLVED' and adapter.calls==0 and result.moves_used==0


@pytest.mark.asyncio
async def test_move_limit_unsuccessful():
    result=await play(Scripted(['U']*3),max_moves=3)
    assert result.status=='RAN_OUT_OF_MOVES' and result.moves_used==3
    assert result.optimality_gap is None


@pytest.mark.asyncio
async def test_deadline_cancels_call():
    adapter=Scripted(["R'"],delay=0.15)
    result=await play(adapter,game_timeout_s=0.02)
    assert result.status=='OUT_OF_TIME' and result.moves_used==0
    assert result.total_time_s<0.12
    assert len(result.records)==1


@pytest.mark.asyncio
async def test_invalid_attempts_not_actual_moves():
    invalid=AdapterResult(error='invalid',invalid_outputs=3,retries_used=2)
    result=await play(Scripted([invalid,invalid]),max_moves=2)
    assert result.status=='RAN_OUT_OF_MOVES' and result.moves_used==0
    assert result.attempts_used==2 and result.invalid_count==6 and result.retry_count==4
    assert result.final_state==result.start_state


@pytest.mark.asyncio
async def test_invalid_nonconsuming_policy():
    result=await play(Scripted([AdapterResult(invalid_outputs=1),"R'"]),invalid_consumes_attempt=False,max_moves=1)
    assert result.status=='SOLVED' and result.attempts_used==1 and len(result.records)==2


@pytest.mark.asyncio
async def test_unavailable_and_error():
    result=await play(Scripted([AdapterResult(unavailable=True,fatal=True,error='404')]))
    assert result.status=='UNAVAILABLE' and result.moves_used==0
    result=await play(Scripted([]))
    assert result.status=='ERROR'


@pytest.mark.asyncio
async def test_invalid_move_revalidated():
    result=await play(Scripted(['R U']),max_moves=1)
    assert result.invalid_count==1 and result.moves_used==0


@pytest.mark.asyncio
async def test_complete_history_independent_of_legacy_recent_setting():
    a=Scripted(['U']*6)
    await play(a,max_moves=6,recent_moves_n=5)
    assert a.histories[-1]==['U']*5
    b=Scripted(['U']*2)
    await play(b,max_moves=2,recent_moves_n=0)
    assert b.histories==[[],['U']]


@pytest.mark.asyncio
async def test_rank_solved_first():
    good=await play(Scripted(["R'"]))
    bad=await play(Scripted(['U']),max_moves=1)
    assert rank_games([bad,good])[0].status=='SOLVED'
    not_run=bad.model_copy(update={'status':'NOT_RUN'})
    diagnostic=good.model_copy(update={'diagnostic':True})
    assert rank_games([not_run,diagnostic])==[]
