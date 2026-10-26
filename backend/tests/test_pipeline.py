import pytest
from backend.baselines import BaselineAdapter
from backend.config import ROOT, ModelConfig, Settings
from backend.cube_engine import apply_move, MOVES, solved_state, self_test
from backend.optimal import ExactSolver
from backend.runner import run_game
from backend.scramble import puzzle

@pytest.fixture(scope='module')
def solver():
    solver = ExactSolver(5, ROOT / 'results/cache/bfs-5.pickle')
    solver.build()
    return solver

@pytest.mark.asyncio
@pytest.mark.parametrize('length', [3, 4, 5])
@pytest.mark.parametrize('condition', ['pure', 'assisted'])
async def test_oracle_exact_scrambles(solver, length, condition):
    self_test()
    # All generated scrambles in this fixed reproducible test corpus, including
    # cancellations: optimal distance is measured, never assumed from length.
    for seed in range(40):
        scramble, state = puzzle(length, seed)
        optimal = solver.distance(state)
        model = ModelConfig(key='oracle', name='Oracle', category='DECISION MODEL', id='offline/oracle', endpoint='decisions')
        result = await run_game(model, BaselineAdapter('oracle', seed, solver), state,
            config=Settings(_env_file=None, mock_models=True, condition=condition), run_id='test', puzzle_id=str(seed),
            seed=seed, scramble=scramble, exact_optimal=optimal)
        assert result.status == 'SOLVED'
        assert result.moves_used == optimal and result.optimality_gap == 0
        assert result.final_state == solved_state()
        if condition == 'assisted':
            assert result.diagnostics['state_revisits'] == 0
            assert result.diagnostics['loop_filter_fallbacks'] == 0
        current = state
        for record in result.records:
            current = apply_move(current, record.move)
            assert record.state_after == current

@pytest.mark.asyncio
@pytest.mark.parametrize('policy', ['random', 'greedy'])
async def test_baselines_legal(policy):
    result = await BaselineAdapter(policy, 1).get_move(apply_move(solved_state(), 'R'), [], MOVES)
    assert result.valid and result.move in MOVES
