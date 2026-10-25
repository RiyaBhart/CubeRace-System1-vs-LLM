import json
import httpx
import pytest
from backend.benchmark import BenchmarkRequest,execute
from backend.config import Settings
from backend.optimal import ExactSolver
from backend.stats import aggregate,analysis_answers
from backend.storage import Store


@pytest.mark.asyncio
async def test_incremental_persistence_resume_and_stats(tmp_path):
    config=Settings(_env_file=None,mock_models=True,results_dir=tmp_path,max_moves=2,bfs_depth=1)
    request=BenchmarkRequest(set='race',puzzles=1,seed=1,length=1)
    events=[]
    async def emit(kind,payload):
        events.append(kind)
    async with httpx.AsyncClient() as client:
        store=await execute(request,config,'test',ExactSolver(1),emit,client)
        assert len(store.games)==4
        again=await execute(request,config,'test',ExactSolver(1),None,client)
        assert len(again.games)==4
        with pytest.raises(ValueError,match='differs'):
            await execute(request,config.model_copy(update={'max_moves':3}),'test',ExactSolver(1),None,client)
    assert 'game_start' in events and 'benchmark_done' in events
    assert (tmp_path/'test.csv').exists() and (tmp_path/'report.md').exists()
    assert len(json.loads((tmp_path/'test.json').read_text())['games'])==4
    rows=aggregate(store.games)
    assert len(rows)==4 and len(analysis_answers(rows))==5
    assert 'SYNTHETIC' in (tmp_path/'report.md').read_text()
    invalid=next(r for r in rows if r['model']=='clef')
    assert invalid['success_rate']==0 and invalid['gap_mean'] is None


def test_primary_minimum_and_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        BenchmarkRequest(set='primary',puzzles=4)
    with pytest.raises(ValueError):
        Store(tmp_path,'../escape')
