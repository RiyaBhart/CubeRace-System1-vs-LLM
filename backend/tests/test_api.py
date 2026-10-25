import json
from fastapi.testclient import TestClient
import backend.main as main
from backend.config import Settings


def test_http_sse_and_recorded_replay(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'settings',Settings(_env_file=None,mock_models=True,
        results_dir=tmp_path,bfs_depth=1,max_moves=1,student_name='Test Student',roll_number='TEST-001'))
    with TestClient(main.app) as client:
        config=client.get('/api/config').json()
        assert config['student_name']=='Test Student'
        assert 'openrouter_api_key' not in config
        assert client.get('/').status_code==200
        assert client.get('/assets/app.js').status_code==200
        assert client.get('/api/puzzle?length=0').status_code==422
        puzzle=client.get('/api/puzzle?seed=1&length=1').json()
        assert len(puzzle['start_state'])==54
        body={'set':'race','puzzles':1,'seed':1,'length':1,'mode':'concurrent'}
        assert client.post('/api/runs',json=body,headers={'Origin':'https://untrusted.example'}).status_code==403
        started=client.post('/api/runs',json=body)
        assert started.status_code==200
        run_id=started.json()['run_id']
        response=client.get(f'/api/runs/{run_id}/events')
        assert 'event: game_start' in response.text
        assert 'event: move' in response.text
        assert 'event: game_end' in response.text
        assert 'event: benchmark_done' in response.text
        payloads=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        games=[p['game'] for p in payloads if 'game' in p and 'status' in p['game']]
        assert games and all(g['start_state']==puzzle['start_state'] for g in games)
        saved=client.get(f'/api/runs/{run_id}').json()
        assert len(saved['games'])==4 and len(saved['answers'])==5
        assert client.get('/api/runs').json()[0]['run_id']==run_id
        assert client.get('/api/runs/missing').status_code==404
        # Last-Event-ID allows reconnection without replaying already received events.
        assert 'event:' not in client.get(f'/api/runs/{run_id}/events',headers={'Last-Event-ID':'999999'}).text
