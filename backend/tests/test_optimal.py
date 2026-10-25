import pytest
from backend.cube_engine import apply_moves, solved_state
from backend.optimal import ExactSolver, SearchLimit
from backend.scramble import puzzle


@pytest.fixture(scope='module')
def solver():
    obj = ExactSolver(3)
    obj.build()
    return obj


def test_known_layer_counts(solver):
    assert [sum(d == n for d in solver.table.values()) for n in range(4)] == [1,18,243,3240]
    assert solver.distance(solved_state()) == 0


def test_full_required_depth_five_table():
    obj = ExactSolver(5)
    obj.build()
    assert len(obj.table) == 621649
    assert sum(d == 5 for d in obj.table.values()) == 574908
    state = puzzle(8, 901)[1]
    solution = obj.solution(state,8)
    assert len(solution) <= 8
    assert apply_moves(state,solution) == solved_state()


@pytest.mark.parametrize('moves,expected', [(['R','R'],1),(['U','D',"U'"],1),(['R','U',"R'","U'"],4),(['R','U','R','U','R'],5)])
def test_true_distance_not_scramble_length(solver,moves,expected):
    state = apply_moves(solved_state(), moves)
    solution = solver.solution(state)
    assert len(solution) == expected
    assert apply_moves(state,solution) == solved_state()


def test_bidirectional_matches_full_bfs():
    full = ExactSolver(3)
    full.build()
    split = ExactSolver(1)
    for state in list(full.table)[::61]:
        assert split.distance(state,3) == full.table[state]


def test_disk_cache(tmp_path):
    path = tmp_path/'cache.pickle'
    first = ExactSolver(2,path)
    first.build()
    second = ExactSolver(2,path)
    second.build()
    assert first.table == second.table
    assert len(second.table) == 262


def test_budget_is_not_fake_optimum():
    with pytest.raises(SearchLimit):
        ExactSolver(0,node_budget=1).distance(puzzle(5,15)[1],8)


def test_depth_bound(solver):
    with pytest.raises(SearchLimit):
        solver.distance(puzzle(5,7)[1],4)
